"""Replay a declared-model run in SUMO, under the same commands, and record what SUMO does.

OPEN LOOP (the gate, A-55): every vehicle follows the edge sequence it realised in the model;
each pursuer's holds are SUMO stops, placed and released at the decisions where the model's
hold changed. SUMO's own dynamics decide everything else - car following, signals, junction
right of way, lane changes.

CLOSED LOOP (reported only): the pursuers as above; the evader chooses each continuation with
the scripted policy from SUMO's positions, at the model's lookahead.

Model and SUMO differ in one declared respect the replay cannot remove: the model has no lanes,
SUMO does. A lane change is recorded and makes the items it touches UNKNOWN.
"""

from __future__ import annotations

import resource
from dataclasses import dataclass, field

from ..domain.contracts import min_gap_for, simulator_arguments
from ..evaluation.capture_judge import TraceFrame, VehicleFrame
from ..simulator.evader import ScriptedEvader
from ..simulator.sumo_adapter import TraciBackend
from ..world.network import GraphNetwork
from .diagnostic_set import ModelRun

END_STOP_MARGIN_M = 0.1


@dataclass
class SumoRecord:
    """SUMO's state at every physical step, aligned to model time: `states[k]` is model index k."""

    # states[k][vid] = (road_id, lane_index, lane_pos, speed, odometer, route_index, x, y, heading)
    states: list[dict[str, tuple]] = field(default_factory=list)
    times: list[float] = field(default_factory=list)
    lane_changes: dict[str, list[float]] = field(default_factory=dict)
    lane_lengths: dict[str, float] = field(default_factory=dict)
    routes: dict[str, list[str]] = field(default_factory=dict)
    stop_errors: list[dict] = field(default_factory=list)
    inserted_late: list[str] = field(default_factory=list)
    trace: list[TraceFrame] = field(default_factory=list)
    evader_route: list[str] = field(default_factory=list)
    child_cpu_s: float = 0.0
    collisions: list[dict] = field(default_factory=list)


def _stop_lane(sumo_net, route: list[str], edge: str, position: int) -> int:
    """Lane index for a stop on `edge`: one that continues to the next route edge, else 0."""
    e = sumo_net.getEdge(edge)
    if position + 1 < len(route):
        nxt = sumo_net.getEdge(route[position + 1])
        conns = e.getOutgoing().get(nxt, [])
        if conns:
            return min(c.getFromLane().getIndex() for c in conns)
    return 0


def replay(
    run: ModelRun,
    net: GraphNetwork,
    sumo_net,
    net_file: str,
    domain: dict,
    sumo_binary: str,
    closed_loop: bool = False,
    extra_s: float = 10.0,
    label: str = "validation",
    imperfection: float = 0.0,
    seed: int | None = None,
) -> SumoRecord:
    rec = SumoRecord()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    backend = TraciBackend(
        net_file,
        seed=(run.scenario.seed if seed is None else seed) % (2**31),
        step_s=domain["timing"]["physical_step_s"],
        sumo_binary=sumo_binary,
        label=label,
        extra_args=simulator_arguments(domain),
    )
    conn = backend.connection
    import traci.constants as tc

    step_s = domain["timing"]["physical_step_s"]
    decision_s = domain["timing"]["decision_interval_s"]
    length = domain["vehicle"]["body_length_m"]
    width = domain["vehicle"]["body_width_m"]
    starts = {"e1": run.scenario.evader_start, **run.scenario.pursuer_starts}
    routes = {vid: list(r) for vid, r in run.routes.items()}
    if closed_loop:
        routes["e1"] = [run.scenario.evader_start[0]]
    rec.routes = {vid: list(r) for vid, r in routes.items()}
    for vid in sorted(starts):
        klass = "evader" if vid == "e1" else "pursuer"
        edge, offset, speed = starts[vid]
        backend.add_route(f"r_{vid}", routes[vid])
        backend.add_vehicle(
            vid,
            f"r_{vid}",
            type_id="DEFAULT_VEHTYPE",
            depart_position_m=offset,
            depart_speed_mps=speed,
            body_length_m=length,
            body_width_m=width,
            min_gap_m=min_gap_for(klass, domain),
            imperfection=imperfection,
            depart_lane="best",
        )
        backend.assign_class(vid, klass)
    variables = [
        tc.VAR_ROAD_ID,
        tc.VAR_LANE_INDEX,
        tc.VAR_LANEPOSITION,
        tc.VAR_SPEED,
        tc.VAR_DISTANCE,
        tc.VAR_ROUTE_INDEX,
        tc.VAR_POSITION,
        tc.VAR_ANGLE,
        tc.VAR_LANE_ID,
    ]

    # Which stop each pursuer currently has from a hold: (edge, pos) or None.
    placed: dict[str, tuple[str, float] | None] = {vid: None for vid in run.scenario.pursuer_starts}
    in_sumo: dict[str, bool] = {vid: False for vid in run.scenario.pursuer_starts}
    evader = ScriptedEvader(
        run.scenario.level,
        run.scenario.seed,
        net.topology(),
        input_mode=domain["evader"].get("input_mode", {}).get("value", "node"),
    )
    decided_on: str | None = None
    subscribed: set[str] = set()
    horizon = run.end_s + extra_s
    last_lane: dict[str, tuple[str, int]] = {}
    end_stops_added: set[str] = set()

    def set_hold(vid: str, hold: tuple[str, float] | None) -> None:
        old = placed[vid]
        if old == hold:
            return
        if old is not None and in_sumo[vid]:
            try:
                if conn.vehicle.isStopped(vid):
                    conn.vehicle.resume(vid)
                else:
                    conn.vehicle.replaceStop(vid, 0, "")
            except Exception as error:  # noqa: BLE001 - SUMO raises TraCIException
                rec.stop_errors.append({"t": t_now, "vid": vid, "op": "release", "e": str(error)})
        placed[vid] = None
        in_sumo[vid] = False
        if hold is None:
            return
        edge, pos = hold
        route = routes[vid]
        here = conn.vehicle.getRouteIndex(vid)
        positions = [i for i, e in enumerate(route) if e == edge and i >= max(here, 0)]
        if not positions:
            # The model run ended before this vehicle reached the hold's edge; its SUMO route
            # (the realised one) ends earlier. Recorded once, not retried.
            rec.stop_errors.append({"t": t_now, "vid": vid, "op": "place", "e": "not on route"})
            placed[vid] = hold
            return
        lane = _stop_lane(sumo_net, route, edge, positions[0])
        lane_len = conn.lane.getLength(f"{edge}_{lane}")
        pos_sumo = min(pos * lane_len / net.edges[edge].length_m, lane_len - END_STOP_MARGIN_M)
        try:
            # startPos explicitly: SUMO's default start lies before a hold near the edge's
            # start and is refused ("End position on lane must be after start position").
            conn.vehicle.setStop(
                vid,
                edge,
                pos=pos_sumo,
                laneIndex=lane,
                duration=1e7,
                startPos=max(0.0, pos_sumo - 0.1),
            )
            placed[vid] = hold
            in_sumo[vid] = True
        except Exception as error:  # noqa: BLE001
            rec.stop_errors.append({"t": t_now, "vid": vid, "op": "place", "e": str(error)})
            placed[vid] = hold  # recorded once, not retried every decision

    t_now = 0.0
    step = 0
    while True:
        # SUMO inserts at its first step without moving, so the state after SUMO step n is
        # the model's state n-1 (checked: identical offsets and speeds over the first steps).
        # Model time is therefore SUMO time minus one step, and the model's decision d, which
        # acts before model step 10d -> 10d+1, acts here before SUMO step 10d+2.
        t_now = round((step - 1) * step_s, 6)
        per = int(round(decision_s / step_s))
        if step >= 1 and (step - 1) % per == 0:
            decision = (step - 1) // per
            live = set(conn.vehicle.getIDList())
            for vid in sorted(placed):
                if vid in live and decision in run.holds:
                    set_hold(vid, run.holds[decision].get(vid))
        conn.simulationStep()
        step += 1
        for c in conn.simulation.getCollisions():
            rec.collisions.append(
                {"t": round((step - 1) * step_s, 6), "vehicles": [c.collider, c.victim]}
            )
        t_now = round((step - 1) * step_s, 6)
        live = set(conn.vehicle.getIDList())
        for vid in live - subscribed:
            conn.vehicle.subscribe(vid, variables)
            subscribed.add(vid)
            if step > 1:
                rec.inserted_late.append(vid)  # model time t_now; inserted after model t=0
        results = conn.vehicle.getAllSubscriptionResults()
        frame_states: dict[str, tuple] = {}
        frames: dict[str, VehicleFrame] = {}
        for vid, r in results.items():
            road = r[tc.VAR_ROAD_ID]
            lane_id = r[tc.VAR_LANE_ID]
            lane_index = r[tc.VAR_LANE_INDEX]
            if lane_id not in rec.lane_lengths:
                rec.lane_lengths[lane_id] = conn.lane.getLength(lane_id)
            if not road.startswith(":"):
                previous = last_lane.get(vid)
                if previous is not None and previous[0] == road and previous[1] != lane_index:
                    rec.lane_changes.setdefault(vid, []).append(t_now)
                last_lane[vid] = (road, lane_index)
            fx, fy = r[tc.VAR_POSITION]
            heading = TraciBackend.heading_rad_from_sumo_angle(r[tc.VAR_ANGLE])
            x, y = TraciBackend.centre_from_front(fx, fy, heading, length)
            frame_states[vid] = (
                road,
                lane_index,
                r[tc.VAR_LANEPOSITION],
                r[tc.VAR_SPEED],
                r[tc.VAR_DISTANCE],
                r[tc.VAR_ROUTE_INDEX],
                x,
                y,
                lane_id,
            )
            frames[vid] = VehicleFrame(vid, x, y, heading, r[tc.VAR_SPEED], length, width)
        rec.states.append(frame_states)
        rec.times.append(t_now)
        rec.trace.append(TraceFrame(t_now, frames))
        # Keep every vehicle in the network at its route's end, as the model does.
        for vid, st in frame_states.items():
            if vid in end_stops_added or st[0].startswith(":"):
                continue
            if closed_loop and vid == "e1":
                continue
            route = routes[vid]
            if st[5] == len(route) - 1:
                last = route[-1]
                try:
                    lane_len = conn.lane.getLength(st[8])
                    conn.vehicle.setStop(
                        vid, last, pos=lane_len - END_STOP_MARGIN_M, laneIndex=st[1], duration=1e7
                    )
                except Exception as error:  # noqa: BLE001
                    rec.stop_errors.append({"t": t_now, "vid": vid, "op": "end", "e": str(error)})
                end_stops_added.add(vid)
        if closed_loop and "e1" in frame_states:
            st = frame_states["e1"]
            road = st[0]
            if not road.startswith(":") and decided_on != road and st[5] == len(routes["e1"]) - 1:
                remaining = rec.lane_lengths[st[8]] - st[2]
                v = st[3]
                lookahead = v**2 / (2 * 4.5) + v * step_s + 1.0
                if remaining <= lookahead:
                    nodes = {}
                    positions = {}
                    for pid, pst in frame_states.items():
                        if pid == "e1":
                            continue
                        if pst[0].startswith(":"):
                            nxt = routes[pid][min(pst[5] + 1, len(routes[pid]) - 1)]
                            nodes[pid] = net.edges[nxt].from_node
                            positions[pid] = (nodes[pid], nodes[pid], 0.0)
                        else:
                            info = net.edges[pst[0]]
                            nodes[pid] = info.to_node
                            fraction = pst[2] / rec.lane_lengths[pst[8]]
                            positions[pid] = (info.from_node, info.to_node, min(1.0, fraction))
                    choice = evader.choose(int(round(t_now / decision_s)), road, nodes, positions)
                    decided_on = road
                    if choice.chosen is not None:
                        routes["e1"] = [*routes["e1"], choice.chosen]
                        end_stops_added.discard("e1")
                        try:
                            conn.vehicle.setRoute("e1", [road, choice.chosen])
                        except Exception as error:  # noqa: BLE001
                            rec.stop_errors.append(
                                {"t": t_now, "vid": "e1", "op": "route", "e": str(error)}
                            )
        if t_now >= horizon - 1e-9:
            break
    rec.evader_route = list(routes["e1"])
    backend.close()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    rec.child_cpu_s = (after.ru_utime + after.ru_stime) - (before.ru_utime + before.ru_stime)
    return rec


def nearest_index(times: list[float], t: float) -> int:
    """Index of the recorded time closest to t (records are at every physical step)."""
    if not times:
        return -1
    step = times[1] - times[0] if len(times) > 1 else 0.1
    k = int(round((t - times[0]) / step))
    return max(0, min(len(times) - 1, k))
