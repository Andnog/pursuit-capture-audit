"""Native construction search: every plan is executed and judged in SUMO (no declared model).

docs/PLAN_NATIVE_CONTROLLED_EN.md. The W4 candidate generator proposes plans; SUMO executes them:
pursuers follow plan segments (route to a target edge, hold there as a SUMO stop), the evader
decides in closed loop with the scripted policy from SUMO's positions. The capture judge, the
D12 helper and both contrasts are evaluated on SUMO traces; every construction found is then
re-run under several SUMO seeds with driver imperfection.
"""

from __future__ import annotations

import contextlib
import resource
import time
from dataclasses import dataclass, field

from ..domain.contracts import CaptureParameters, min_gap_for, simulator_arguments
from ..domain.geometry import body_separation_m
from ..evaluation.capture_judge import TraceFrame, VehicleFrame, judge_capture
from ..opportunities.types import Verdict
from ..simulator.evader import ScriptedEvader
from ..simulator.sumo_adapter import TraciBackend
from ..world.construction import (
    RELEASE_OFFSETS,
    Constructor,
    Plan,
    Scenario,
    Segment,
    settling_time_s,
)
from ..world.network import GraphNetwork

HOLD_END_MARGIN_M = 0.5
ORDINARY_DECEL = 4.5
ADMISSION_MARGIN_M = 5.0
HARD_BRAKE_MPS_PER_STEP = 0.5  # 5.0 m/s^2 at 0.1 s; ordinary deceleration is 4.5

# A-119 (second review, R9): command dispatch bookkeeping.
# "checked": an order is recorded as applied only if it was installed ("accepted"). An order
#            without a route is "no_route"; a TraCI failure that fell back to a default stop is
#            "fallback". Neither is recorded as the requested command, so it can be requested again.
# "legacy":  the behaviour of every run sealed before A-119 ("no_route" and "fallback" were
#            recorded as applied). Set it to reproduce historical episodes exactly.
DISPATCH_MODE = "checked"


def record_dispatch(status, vid, pending, applied, mode=None):
    """Update `pending`/`applied` after a dispatch attempt; returns the status (A-119)."""
    mode = mode or DISPATCH_MODE
    command = pending.pop(vid)
    if mode == "legacy":
        if status != "rejected":
            applied[vid] = command
        return status
    if status == "accepted":
        applied[vid] = command
    elif status == "fallback":
        applied[vid] = ("fallback", *command)
    return status


@dataclass
class NativeRun:
    trace: list[TraceFrame] = field(default_factory=list)
    decisions: list = field(default_factory=list)
    collisions: list[dict] = field(default_factory=list)
    hard_braking: list[dict] = field(default_factory=list)
    refused: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)  # applied commands and evader decisions
    verdict: object = None


def run_plan(
    net: GraphNetwork,
    net_file: str,
    scenario: Scenario,
    plan: Plan,
    domain: dict,
    sumo_binary: str,
    b1: tuple[str, int, int] | None = None,
    sigma: float = 0.0,
    seed: int | None = None,
    horizon_s: float = 300.0,
    label: str = "native",
    controller=None,
    evader_speed_factor: float = 1.0,
    stop_when=None,
    stop_on_capture: bool = True,
    admission: bool = False,
    extra_sumo_args: list[str] | None = None,
    pursuer_speed_factor: float = 1.0,
) -> NativeRun:
    """`controller(decision, t, states, conn)` (F1 caging strategies), if given, returns each
    pursuer's command `("seg", target_edge, hold)` at every decision instead of the plan; all
    pursuers may then be credited. `stop_when(t)` ends the run early when it returns True."""
    import traci.constants as tc

    out = NativeRun()
    step_s = domain["timing"]["physical_step_s"]
    decision_s = domain["timing"]["decision_interval_s"]
    per = int(round(decision_s / step_s))
    length = domain["vehicle"]["body_length_m"]
    width = domain["vehicle"]["body_width_m"]
    params = CaptureParameters.from_domain(domain)
    backend = TraciBackend(
        net_file,
        seed=(scenario.seed if seed is None else seed) % (2**31),
        step_s=step_s,
        sumo_binary=sumo_binary,
        label=label,
        # A-92: optional extra SUMO arguments (background-traffic route files).
        extra_args=simulator_arguments(domain) + list(extra_sumo_args or []),
    )
    conn = backend.connection
    starts = {"e1": scenario.evader_start, **scenario.pursuer_starts}
    for vid in sorted(starts):
        klass = "evader" if vid == "e1" else "pursuer"
        edge, offset, speed = starts[vid]
        backend.add_route(f"r_{vid}", [edge])
        backend.add_vehicle(
            vid,
            f"r_{vid}",
            type_id="DEFAULT_VEHTYPE",
            depart_position_m=offset,
            depart_speed_mps=speed,
            body_length_m=length,
            body_width_m=width,
            min_gap_m=min_gap_for(klass, domain),
            imperfection=sigma,
            depart_lane="best",
        )
    evader = ScriptedEvader(
        scenario.level,
        scenario.seed,
        net.topology(),
        input_mode=domain["evader"].get("input_mode", {}).get("value", "node"),
        # A-112: destinations for the goal-directed evader only; other levels are unchanged.
        goal_nodes=_outer_nodes(net_file) if scenario.level.name == "GOAL_DIRECTED" else (),
    )
    if controller is not None:
        # A-100: expose the evader to oracle planners (upper-bound experiments only).
        with contextlib.suppress(AttributeError):
            controller.evader = evader
            controller.decision_s = domain["timing"]["decision_interval_s"]
    variables = [
        tc.VAR_ROAD_ID,
        tc.VAR_LANE_ID,
        tc.VAR_LANEPOSITION,
        tc.VAR_SPEED,
        tc.VAR_POSITION,
        tc.VAR_ANGLE,
    ]
    pursuers = sorted(scenario.pursuer_starts)
    # A-68: only the plan's pursuers may be credited with a capture.
    allowed = {"e1", *plan.segments} if controller is None else {"e1", *scenario.pursuer_starts}
    applied: dict[str, tuple] = {}
    pending: dict[str, tuple] = {}
    lane_len: dict[str, float] = {}
    evader_route = [scenario.evader_start[0]]
    decided_on: str | None = None
    last_speed: dict[str, float] = {}
    states: dict[str, tuple] = {}
    step = 0

    def clear_stops(vid):
        for _ in range(8):
            stops = conn.vehicle.getStops(vid)
            if not stops:
                return
            if conn.vehicle.isStopped(vid):
                conn.vehicle.resume(vid)
            else:
                conn.vehicle.replaceStop(vid, 0, "")

    def place_stop(vid, edge, pos, parking=False, lane=0):
        lane_id = f"{edge}_{lane}"
        if lane_id not in lane_len:
            lane_len[lane_id] = conn.lane.getLength(lane_id)
        scaled = min(pos * lane_len[lane_id] / net.edges[edge].length_m, lane_len[lane_id] - 0.1)
        conn.vehicle.setStop(
            vid,
            edge,
            pos=scaled,
            laneIndex=lane,
            duration=1e7,
            flags=tc.STOP_PARKING if parking else tc.STOP_DEFAULT,
            startPos=max(0.0, scaled - 0.1),
        )

    def apply(vid, command, road):
        # A-94: an optional 4th element selects the stop lane (lane-level blocking).
        kind, target, hold = command[:3]
        lane = command[3] if len(command) > 3 else 0
        route = net.route(road, target)
        if route is None:
            out.refused.append({"t": t_now, "vid": vid, "why": "no route"})
            return "no_route"
        end = net.edges[target].length_m - HOLD_END_MARGIN_M
        wanted = end if hold is None else min(hold, end)
        if admission:
            # A-76: an order the vehicle cannot follow at ordinary deceleration is adapted or
            # refused, as the declared model did (A-51). 41 of F3's emergencies followed one.
            v = conn.vehicle.getSpeed(vid)
            pos = conn.vehicle.getLanePosition(vid)
            lane_id = conn.vehicle.getLaneID(vid)
            # A parked pursuer (off the lane, A-68) has no lane: use the edge's length.
            lane_length = conn.lane.getLength(lane_id) if lane_id else net.edges[road].length_m
            remaining = lane_length - pos
            braking = v * v / (2 * ORDINARY_DECEL) + v * step_s + ADMISSION_MARGIN_M
            if target == road and (wanted * lane_length / net.edges[road].length_m) - pos < braking:
                out.refused.append({"t": t_now, "vid": vid, "why": "stop too close"})
                return "rejected"
            current = conn.vehicle.getRoute(vid)
            idx = conn.vehicle.getRouteIndex(vid)
            committed = current[idx + 1] if 0 <= idx < len(current) - 1 else None
            if (
                committed is not None
                and len(route) > 1
                and route[1] != committed
                and remaining < braking
            ):
                onward = net.route(committed, target)
                if onward is None:
                    out.refused.append({"t": t_now, "vid": vid, "why": "committed, no route"})
                    return "rejected"
                route = [road, *onward]
        out.events.append(
            {"t": t_now, "vid": vid, "kind": "command", "road": road, "target": target}
        )
        try:
            clear_stops(vid)
            conn.vehicle.setRoute(vid, route)
            place_stop(vid, target, wanted, lane=lane)
        except Exception as error:  # noqa: BLE001 - TraCIException
            out.refused.append({"t": t_now, "vid": vid, "why": str(error)[:120]})
            with contextlib.suppress(Exception):
                place_stop(vid, target, net.edges[target].length_m - 0.1)
            return "fallback"
        return "accepted"

    t_now = 0.0
    watch_from = None
    while True:
        conn.simulationStep()
        step += 1
        t_now = round((step - 1) * step_s, 6)
        if step == 1:
            for vid in sorted(starts):
                conn.vehicle.subscribe(vid, variables)
            if evader_speed_factor != 1.0:
                conn.vehicle.setSpeedFactor("e1", evader_speed_factor)
            if pursuer_speed_factor != 1.0:  # A-101 sensitivity
                for vid in pursuers:
                    conn.vehicle.setSpeedFactor(vid, pursuer_speed_factor)
            for vid in pursuers:
                e = scenario.pursuer_starts[vid][0]
                try:
                    # A-68: a pursuer without orders parks OFF the lane. Parked in its lane it was
                    # a free roadblock: the best B4 case's captures were all made by one.
                    place_stop(vid, e, net.edges[e].length_m - HOLD_END_MARGIN_M, parking=True)
                except Exception as error:  # noqa: BLE001
                    out.refused.append({"t": 0.0, "vid": vid, "why": str(error)[:120]})
        results = conn.vehicle.getAllSubscriptionResults()
        frames = {}
        states = {}
        for vid, r in results.items():
            road = r[tc.VAR_ROAD_ID]
            lane_id = r[tc.VAR_LANE_ID]
            if lane_id == "":
                # Parked off the lane (A-68): use the edge's length for fractions. A vehicle
                # momentarily on no road at all (parking transition) is skipped this step.
                if road not in net.edges:
                    continue
                lane_id = f"{road}_0"
            if lane_id not in lane_len:
                lane_len[lane_id] = conn.lane.getLength(lane_id)
            fx, fy = r[tc.VAR_POSITION]
            heading = TraciBackend.heading_rad_from_sumo_angle(r[tc.VAR_ANGLE])
            x, y = TraciBackend.centre_from_front(fx, fy, heading, length)
            speed = r[tc.VAR_SPEED]
            frames[vid] = VehicleFrame(vid, x, y, heading, speed, length, width)
            states[vid] = (road, lane_id, r[tc.VAR_LANEPOSITION], speed)
            if vid in last_speed and last_speed[vid] - speed > HARD_BRAKE_MPS_PER_STEP:
                out.hard_braking.append({"t": t_now, "vid": vid})
            last_speed[vid] = speed
        out.trace.append(TraceFrame(t_now, frames))
        for c in conn.simulation.getCollisions():
            out.collisions.append({"t": t_now, "vehicles": [c.collider, c.victim]})

        # Pursuer commands, decided at each decision and applied once on a normal edge.
        if (step - 1) % per == 0:
            d = (step - 1) // per
            e_state = states.get("e1")
            if controller is not None:
                for vid, command in controller(d, t_now, states, conn).items():
                    if command is not None and command != applied.get(vid):
                        pending[vid] = command
            for vid in pursuers if controller is None else ():
                if b1 is not None and vid == b1[0] and b1[1] <= d < b1[2] and e_state:
                    e_road = e_state[0]
                    if e_road.startswith(":"):
                        e_road = evader_route[-1]
                    command = ("b1", e_road, None)
                else:
                    seg = plan.active(vid, d)
                    command = ("seg", seg.target_edge, seg.hold_offset) if seg else None
                if command is not None and command != applied.get(vid):
                    pending[vid] = command
        for vid in list(pending):
            st = states.get(vid)
            if st and not st[0].startswith(":"):
                # A-119: a refused order keeps the previous command in force; see record_dispatch.
                status = record_dispatch(apply(vid, pending[vid], st[0]), vid, pending, applied)
                if status != "accepted":
                    out.events.append(
                        {"t": t_now, "vid": vid, "kind": "dispatch", "status": status}
                    )

        # Evader: closed loop at the lookahead, as in the replay harness.
        es = states.get("e1")
        if es and not es[0].startswith(":") and decided_on != es[0] and es[0] == evader_route[-1]:
            remaining = lane_len[es[1]] - es[2]
            v = es[3]
            if remaining <= v**2 / (2 * 4.5) + v * step_s + 1.0:
                nodes, positions = {}, {}
                for pid in pursuers:
                    ps = states.get(pid)
                    if ps is None:
                        continue
                    if ps[0].startswith(":"):
                        route = conn.vehicle.getRoute(pid)
                        idx = conn.vehicle.getRouteIndex(pid)
                        nxt = route[min(idx + 1, len(route) - 1)]
                        node = net.edges[nxt].from_node
                        nodes[pid], positions[pid] = node, (node, node, 0.0)
                    else:
                        info = net.edges[ps[0]]
                        nodes[pid] = info.to_node
                        positions[pid] = (
                            info.from_node,
                            info.to_node,
                            min(1.0, ps[2] / lane_len[ps[1]]),
                        )
                choice = evader.choose(int(round(t_now / decision_s)), es[0], nodes, positions)
                decided_on = es[0]
                out.events.append(
                    {
                        "t": t_now,
                        "vid": "e1",
                        "kind": "decision",
                        "road": es[0],
                        "chosen": choice.chosen,
                        "remaining": round(remaining, 2),
                        "speed": round(v, 2),
                    }
                )
                if choice.chosen is not None:
                    evader_route.append(choice.chosen)
                    ahead = [es[0], choice.chosen]
                    # A-76: a continuation shorter than the lookahead is followed by an immediate
                    # second choice, so SUMO knows the turn after it in time (33 of F3's
                    # emergencies were the evader deciding 17-19 m before a turn at 16.5 m/s).
                    top = net.edges[choice.chosen].speed_cap_mps * evader_speed_factor
                    while (
                        admission
                        and net.edges[ahead[-1]].length_m
                        < top**2 / (2 * ORDINARY_DECEL) + top * step_s + 1.0
                        and len(ahead) < 6
                    ):
                        extra = evader.choose(
                            int(round(t_now / decision_s)), ahead[-1], nodes, positions
                        )
                        if extra.chosen is None:
                            break
                        ahead.append(extra.chosen)
                        evader_route.append(extra.chosen)
                    try:
                        conn.vehicle.setRoute("e1", ahead)
                    except Exception as error:  # noqa: BLE001
                        out.refused.append({"t": t_now, "vid": "e1", "why": str(error)[:120]})

        # Early stop once a witness is complete (checked cheaply, confirmed by the judge).
        if es and es[3] < params.capture_speed_max_mps:
            watch_from = watch_from if watch_from is not None else t_now
        else:
            watch_from = None
        if (
            stop_on_capture
            and watch_from is not None
            and t_now - watch_from >= params.dwell_time_s + 0.5
        ):
            # Judge only the recent window here (a full-trace judge every half second was
            # quadratic in a long wait); the final verdict is always on the whole trace.
            recent = out.trace[-int(round((params.dwell_time_s + 1.0) / step_s)) :]
            if judge_capture(_only(recent, allowed), "e1", params, step_s).verdict is (
                Verdict.SUPPORTED
            ):
                out.verdict = judge_capture(_only(out.trace, allowed), "e1", params, step_s)
                break
            watch_from = t_now - params.dwell_time_s  # keep checking while it stays slow
        if t_now >= horizon_s - 1e-9 or "e1" not in results:
            break
        if stop_when is not None and stop_when(t_now):
            break
    backend.close()
    out.decisions = list(evader.decisions)
    if out.verdict is None:
        out.verdict = judge_capture(_only(out.trace, allowed), "e1", params, step_s)
    return out


_OUTER: dict[str, tuple[str, ...]] = {}


def _outer_nodes(net_file: str, band: float = 0.10) -> tuple[str, ...]:
    """A-112: nodes within `band` of the network's bounding box (passenger edges only), sorted."""
    if net_file not in _OUTER:
        import sumolib

        snet = sumolib.net.readNet(net_file)
        nodes = set()
        for e in snet.getEdges():
            if not e.isSpecial() and e.allows("passenger"):
                nodes.update((e.getFromNode(), e.getToNode()))
        xs = [n.getCoord() for n in nodes]
        x0, x1 = min(p[0] for p in xs), max(p[0] for p in xs)
        y0, y1 = min(p[1] for p in xs), max(p[1] for p in xs)
        margin = band * min(x1 - x0, y1 - y0)
        _OUTER[net_file] = tuple(
            sorted(
                n.getID()
                for n in nodes
                if min(
                    n.getCoord()[0] - x0,
                    x1 - n.getCoord()[0],
                    n.getCoord()[1] - y0,
                    y1 - n.getCoord()[1],
                )
                <= margin
            )
        )
    return _OUTER[net_file]


def _only(frames: list[TraceFrame], allowed: set[str]) -> list[TraceFrame]:
    """The trace restricted to the evader and the plan's pursuers, for the capture judge."""
    return [
        TraceFrame(f.time_s, {k: v for k, v in f.vehicles.items() if k in allowed}) for f in frames
    ]


def _clean(run: NativeRun, witness_start: float | None) -> bool:
    """No collision at all; no hard braking by anyone before the witness ends."""
    if run.collisions:
        return False
    if witness_start is None:
        return not run.hard_braking
    return not [h for h in run.hard_braking if h["t"] <= witness_start + 2.0]


@dataclass
class ScenarioResult:
    map_id: str
    scenario_seed: int
    plans_tried: int = 0
    captures: int = 0
    coordinated: list[dict] = field(default_factory=list)
    robust: list[dict] = field(default_factory=list)
    # A-66: plans whose capture needs the helper (COORDINATED or NECESSARY_BUT_B1_NULL).
    necessary: list[dict] = field(default_factory=list)
    labels: dict = field(default_factory=dict)
    cpu_seconds: float = 0.0
    stopped_by: str = ""
    best_traces: dict | None = None


def search_scenario(
    net: GraphNetwork,
    net_file: str,
    scenario: Scenario,
    domain: dict,
    sumo_binary: str,
    cpu_budget_s: float,
    robustness_seeds: int = 5,
    robustness_sigma: float = 0.5,
    label: str = "ns",
    generator: str = "exact",
    margin_s: float = 10.0,
) -> ScenarioResult:
    """`generator="exact"`: W4's plans (finisher released onto the target just before the
    evader's decision). `generator="margin"` (A-65): finisher sent straight to its hold on the
    target and helpers to their covers from t = 0, and only plans in which every one of them
    can arrive (free-flow) at least `margin_s` before the evader's decision."""
    params = CaptureParameters.from_domain(domain)
    res = ScenarioResult(scenario.map_id, scenario.seed)
    c0 = time.process_time()
    ch0 = resource.getrusage(resource.RUSAGE_CHILDREN)

    def cpu():
        ch = resource.getrusage(resource.RUSAGE_CHILDREN)
        return (time.process_time() - c0) + (
            ch.ru_utime + ch.ru_stime - ch0.ru_utime - ch0.ru_stime
        )

    ctor = Constructor(net, scenario, domain, 10**9, 1e12)
    pursuers = sorted(scenario.pursuer_starts)
    n = [0]

    def run(plan, **kw):
        n[0] += 1
        return run_plan(
            net, net_file, scenario, plan, domain, sumo_binary, label=f"{label}{n[0]}", **kw
        )

    def path_of(r):
        return [
            {
                "from_edge": d.current_edge,
                "chosen": d.chosen,
                "alternatives": [a for a in d.admissible if a != d.chosen],
                "decision": d.decision_index,
            }
            for d in r.decisions
            if d.chosen is not None
        ]

    def tally(key):
        res.labels[key] = res.labels.get(key, 0) + 1

    seen_witness: set = set()
    baseline = run(Plan())
    queue = [path_of(baseline)]
    seen: set = set()
    while queue and cpu() < cpu_budget_s:
        path = queue.pop(0)
        for step, target, alternatives, approach, hold in ctor.candidates(path):
            if cpu() >= cpu_budget_s:
                break
            key = (step["decision"], target, approach, hold)
            if key in seen or len(alternatives) > len(pursuers) - 1:
                continue
            seen.add(key)
            t_d = step["decision"]
            if generator == "margin":
                finishers = [p for p in pursuers if ctor.eta_s(p, target) <= t_d - margin_s]
            else:
                finishers = [p for p in pursuers if ctor.eta_s(p, approach) <= t_d + 1.0] or [
                    min(pursuers, key=lambda p: (ctor.eta_s(p, approach), p))
                ]
            for finisher in finishers:
                helpers = [p for p in pursuers if p != finisher]
                cover = ctor.assign_cover(helpers, alternatives)
                if generator == "margin" and (
                    len(cover) < len(alternatives)
                    or any(ctor.eta_s(h, alt) > t_d - margin_s for h, alt in cover.items())
                ):
                    continue
                releases = (None,) if generator == "margin" else RELEASE_OFFSETS
                for release in releases:
                    if cpu() >= cpu_budget_s:
                        break
                    plan = Plan()
                    if release is None:
                        plan.segments[finisher] = [Segment(0, target, hold)]
                    else:
                        plan.segments[finisher] = [
                            Segment(0, approach, None),
                            Segment(max(0, t_d + release), target, hold),
                        ]

                    for helper, alt in cover.items():
                        plan.segments[helper] = [Segment(0, alt, 12.0)]
                    r = run(plan)
                    res.plans_tried += 1
                    v = r.verdict
                    if v.verdict is not Verdict.SUPPORTED:
                        if len(queue) < 200:
                            queue.append(path_of(r))
                        continue
                    res.captures += 1
                    if not _clean(r, v.witness_start_s):
                        tally("CAPTURE_NOT_CLEAN")
                        continue
                    wkey = (v.finisher, round(v.witness_start_s))
                    if wkey in seen_witness:
                        tally("DUPLICATE_SITUATION")
                        continue
                    seen_witness.add(wkey)
                    outcome = _coordination(r, plan, v, pursuers, run, params, domain)
                    tally(outcome["label"])
                    if outcome["label"] in ("COORDINATED", "NECESSARY_BUT_B1_NULL"):
                        res.necessary.append(outcome)
                    if outcome["label"] != "COORDINATED" or robustness_seeds == 0:
                        continue
                    res.coordinated.append(outcome)
                    rob = _robustness(
                        plan, outcome, run, params, robustness_seeds, robustness_sigma
                    )
                    outcome["robustness"] = rob
                    if rob["robust"]:
                        res.robust.append(outcome)
                    # Keep traces for the GIF: the first robust construction, else the first
                    # coordinated one (flagged), so fragile cases can be seen too.
                    if res.best_traces is None or (rob["robust"] and not res.best_traces["robust"]):
                        absent = run(
                            Plan({k: s for k, s in plan.segments.items() if k != outcome["helper"]})
                        )
                        res.best_traces = {
                            "factual": r.trace,
                            "helper_never_acts": absent.trace,
                            "finisher": v.finisher,
                            "helper": outcome["helper"],
                            "witness_start_s": v.witness_start_s,
                            "robust": rob["robust"],
                        }
    res.cpu_seconds = round(cpu(), 1)
    res.stopped_by = "CPU budget" if cpu() >= cpu_budget_s else "candidates exhausted"
    return res


def _coordination(r, plan, v, pursuers, run, params, domain) -> dict:
    start = next(f for f in r.trace if abs(f.time_s - v.witness_start_s) < 1e-6)
    body = start.vehicles["e1"].rectangle()
    others = sorted(
        (body_separation_m(start.vehicles[p].rectangle(), body), p)
        for p in pursuers
        if p != v.finisher and p in start.vehicles
    )
    if not others:
        return {"label": "NO_HELPER"}
    helper = others[0][1]
    settle = settling_time_s(r.trace, helper, v.witness_start_s)
    begin = max(0, int(settle // domain["timing"]["decision_interval_s"]) - 5)
    cf = run(plan, b1=(helper, begin, begin + 5))
    absent = run(Plan({k: s for k, s in plan.segments.items() if k != helper}))
    b1_rejects = cf.verdict.verdict is not Verdict.SUPPORTED
    nec_rejects = absent.verdict.verdict is not Verdict.SUPPORTED
    label = (
        "COORDINATED"
        if b1_rejects and nec_rejects
        else "B1_CONTRAST_WITHOUT_NECESSITY"
        if b1_rejects
        else "NECESSARY_BUT_B1_NULL"
        if nec_rejects
        else "CAPTURE_NOT_COORDINATED"
    )
    return {
        "label": label,
        "plan": {k: [s.__dict__ for s in segs] for k, segs in plan.segments.items()},
        "finisher": v.finisher,
        "witness_start_s": v.witness_start_s,
        "helper": helper,
        "helper_separation_m": round(others[0][0], 2),
        "b1_window": [begin, begin + 5],
    }


def _robustness(plan, outcome, run, params, seeds, sigma) -> dict:
    helper = outcome["helper"]
    b1 = (helper, *outcome["b1_window"])
    absent_plan = Plan({k: s for k, s in plan.segments.items() if k != helper})
    tally = {"factual": 0, "b1_rejects": 0, "absent_rejects": 0}
    for k in range(1, seeds + 1):
        f = run(plan, sigma=sigma, seed=1000 + k)
        if f.verdict.verdict is Verdict.SUPPORTED and f.verdict.finisher == outcome["finisher"]:
            tally["factual"] += 1
        if run(plan, b1=b1, sigma=sigma, seed=1000 + k).verdict.verdict is not Verdict.SUPPORTED:
            tally["b1_rejects"] += 1
        if run(absent_plan, sigma=sigma, seed=1000 + k).verdict.verdict is not Verdict.SUPPORTED:
            tally["absent_rejects"] += 1
    need = seeds - 1
    return {
        **tally,
        "seeds": seeds,
        "sigma": sigma,
        "robust": all(v >= need for v in tally.values()),
    }
