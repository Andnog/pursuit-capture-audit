"""O27: search for complete offline assisted-capture constructions in the declared model.

The only capture pattern this model admits against an evader that reads pursuer positions
is INTERCEPTION AT A JUNCTION. A pursuer already on the evader's chosen edge makes that edge
score zero, so the evader avoids it. The finisher therefore waits short of the junction,
enters the evader's edge just ahead of it, and stops; helpers cover the alternative exits so
the evader chooses that edge. Everything here is deterministic.

D12 is applied exactly as frozen and never tuned: helper = nearest non-finisher at the
witness start; intervention = the 5 decisions before it; `b1` = shortest-path pursuit of
the evader's current public position, then return to the plan.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field

from ..domain.contracts import CaptureParameters
from ..domain.geometry import body_separation_m
from ..evaluation.capture_judge import judge_capture
from ..opportunities.types import Verdict
from ..simulator.evader import EvaderLevel, ScriptedEvader
from .network import GraphNetwork
from .simulation import Vehicle, World

FINISHER_HOLDS_M = (6.0, 10.0, 16.0, 25.0)
RELEASE_OFFSETS = (-3, -2, -1, 0, 1)


@dataclass(frozen=True)
class Segment:
    """From decision `start`, drive to `target_edge` and hold at `hold_offset` (or its end)."""

    start: int
    target_edge: str
    hold_offset: float | None


@dataclass
class Plan:
    segments: dict[str, list[Segment]] = field(default_factory=dict)

    def active(self, vid: str, decision: int) -> Segment | None:
        chosen = None
        for segment in self.segments.get(vid, []):
            if segment.start <= decision:
                chosen = segment
        return chosen


@dataclass
class Scenario:
    map_id: str
    level: EvaderLevel
    seed: int
    evader_start: tuple[str, float, float]
    pursuer_starts: dict[str, tuple[str, float, float]]


def scenario_seed(map_id: str, level: EvaderLevel, salt: str = "") -> int:
    """Frozen per protocol. The empty salt reproduces r01 exactly; r02 uses fresh seeds,
    because development scans had already been run on r01's scenarios."""
    return int(hashlib.sha256(f"{map_id}{int(level)}{salt}".encode()).hexdigest()[:12], 16)


def _route_length(net: GraphNetwork, route: list[str]) -> float:
    total = 0.0
    for a, b in zip(route, route[1:], strict=False):
        total += net.edges[a].length_m + net.links[(a, b)].via_length_m
    return total


ORDINARY_DECEL = 4.5


def _moving_start(info, salt: str) -> tuple[str, float, float]:
    """Start position and speed. r01: half the edge's cap, as frozen then.

    From r02 the speed is also capped at what lets the vehicle stop by the edge's end with
    ordinary braking: r01's rule placed a pursuer on a 30.9 m edge at 13.9 m/s with 20.4 m
    to stop, an inadmissible INITIAL state. Declared in r02's pre-registration.
    """
    offset = min(10.0, info.length_m / 3)
    speed = 0.5 * info.speed_cap_mps
    if salt:
        room = max(0.0, info.length_m - offset - 0.5)
        speed = min(speed, 0.9 * math.sqrt(2.0 * ORDINARY_DECEL * room))
    return (info.edge_id, offset, speed)


def make_scenario(
    net: GraphNetwork, map_id: str, level: EvaderLevel, pursuers: list[str], salt: str = ""
):
    """Frozen rule from the protocol. Moving starts at half each edge's cap."""
    seed = scenario_seed(map_id, level, salt)
    ids = sorted(net.edges)
    evader_edges = [
        e
        for e in ids
        if net.edges[e].length_m > 40.0
        and len(net.successors(e)) >= 2
        and all(len(net.successors(n)) >= 1 for n in net.successors(e))
    ]
    e_edge = evader_edges[seed % len(evader_edges)]
    e_info = net.edges[e_edge]
    evader_start = _moving_start(e_info, salt)

    starts: dict[str, tuple[str, float, float]] = {}
    step = 0
    used = {e_edge}
    for vid in pursuers:
        for _ in range(len(ids)):
            step += 1
            candidate = ids[(seed // 7 + step * 7919) % len(ids)]
            if candidate in used or net.edges[candidate].length_m < 30.0:
                continue
            route = net.route(candidate, e_edge)
            if route is None:
                continue
            length = _route_length(net, route)
            if 100.0 <= length <= 800.0:
                info = net.edges[candidate]
                starts[vid] = _moving_start(info, salt)
                used.add(candidate)
                break
    return Scenario(map_id, level, seed, evader_start, starts)


class Constructor:
    """Runs one scenario's search under a fixed expansion and wall-time budget."""

    def __init__(
        self,
        net: GraphNetwork,
        scenario: Scenario,
        domain: dict,
        max_expansions: int,
        max_seconds: float,
        horizon_s: float = 300.0,
    ):
        self.net = net
        self.sc = scenario
        self.domain = domain
        self.params = CaptureParameters.from_domain(domain)
        self.capture = {k: v["value"] for k, v in domain["capture_predicate"]["parameters"].items()}
        self.step_s = domain["timing"]["physical_step_s"]
        self.decision_s = domain["timing"]["decision_interval_s"]
        gaps = domain["vehicle"]["min_gap_m_by_class"]
        self.gap = {"pursuer": gaps["pursuer"], "evader": gaps["evader"]}
        self.length = domain["vehicle"]["body_length_m"]
        self.width = domain["vehicle"]["body_width_m"]
        self.max_expansions = max_expansions
        self.max_seconds = max_seconds
        self.horizon_s = horizon_s
        self.expansions = 0
        self.started = time.process_time()
        self.log: list[dict] = []
        self.captures: list[dict] = []
        self.failures: list[dict] = []
        self.refused_commands = 0
        self.rejected: list[dict] = []

    # -- world construction ---------------------------------------------------------------

    def world(self, record: bool = False) -> World:
        vehicles: dict[str, Vehicle] = {}
        edge, offset, speed = self.sc.evader_start
        vehicles["e1"] = Vehicle(
            "e1", "evader", self.length, self.width, self.gap["evader"], edge, offset, speed
        )
        for vid, (edge, offset, speed) in self.sc.pursuer_starts.items():
            vehicles[vid] = Vehicle(
                vid,
                "pursuer",
                self.length,
                self.width,
                self.gap["pursuer"],
                edge,
                offset,
                speed,
                hold=(edge, self.net.edges[edge].length_m - 0.5),
            )
        evader = ScriptedEvader(self.sc.level, self.sc.seed, self.net.topology())
        return World(
            self.net,
            vehicles,
            evader,
            "e1",
            self.step_s,
            self.decision_s,
            2.6,
            4.5,
            self.capture,
            record_trace=record,
        )

    def _apply(self, world: World, vid: str, segment: Segment, hold_wanted: bool = True) -> None:
        """Issue a plan segment to a pursuer, through physical admission.

        A command that would need emergency braking is inadmissible. Plans that switched
        route or set a hold at a decision boundary without this check demanded it 238 times
        across two scenarios. Order of remedies: keep the edge the vehicle is already
        committed to and re-route from it (too late to turn); move the hold to the nearest
        point reachable by ordinary braking; and if the command is still inadmissible,
        REFUSE it and leave the vehicle's current command in force. Refusals are counted.
        """
        v = world.vehicles[vid]
        current = v.in_link.to_edge if v.in_link else v.edge
        route = self.net.route(current, segment.target_edge)
        if route is None:
            return
        new_route = route[1:]
        end = self.net.edges[segment.target_edge].length_m - 0.5
        wanted = end if segment.hold_offset is None else min(segment.hold_offset, end)
        hold = (segment.target_edge, wanted) if hold_wanted else None
        if not world.admissible(v, new_route, hold):
            if not v.in_link and v.route:
                committed = v.route[0]
                onward = self.net.route(committed, segment.target_edge)
                if onward is not None:
                    new_route = [committed, *onward[1:]]
            if hold is not None and not world.admissible(v, new_route, hold):
                hold = (
                    segment.target_edge,
                    world.reachable_hold(v, new_route, segment.target_edge, wanted),
                )
        if not world.admissible(v, new_route, hold):
            self.refused_commands += 1
            return
        v.route = new_route
        v.hold = hold

    def controller(self, plan: Plan, b1: tuple[str, int, int] | None = None):
        applied: dict[str, Segment | None] = {}

        def control(world: World, decision: int) -> None:
            for vid in sorted(self.sc.pursuer_starts):
                if b1 is not None and vid == b1[0] and b1[1] <= decision < b1[2]:
                    e = world.vehicles["e1"]
                    target = e.in_link.to_edge if e.in_link else e.edge
                    self._apply(world, vid, Segment(decision, target, None), hold_wanted=False)
                    applied[vid] = None
                    continue
                segment = plan.active(vid, decision)
                if segment is not None and applied.get(vid) != segment:
                    self._apply(world, vid, segment)
                    applied[vid] = segment

        return control

    def simulate(self, plan: Plan, record: bool = False, b1=None) -> World:
        self.expansions += 1
        w = self.world(record)
        w.run(self.horizon_s, self.controller(plan, b1))
        return w

    def eta_s(self, vid: str, edge: str) -> float:
        """Free-flow lower bound on the time for pursuer `vid` to reach the END of `edge`.

        A screen only - optimistic by construction, like the declared model - used to skip
        finishers that cannot possibly be in place. Never used to accept anything.
        """
        start, offset, _ = self.sc.pursuer_starts[vid]
        route = self.net.route(start, edge)
        if route is None:
            return float("inf")
        total = (self.net.edges[start].length_m - offset) / self.net.edges[start].speed_cap_mps
        for a, b in zip(route, route[1:], strict=False):
            link = self.net.links[(a, b)]
            if link.via_length_m > 0:
                total += link.via_length_m / max(link.via_speed_mps, 1e-6)
            total += self.net.edges[b].length_m / self.net.edges[b].speed_cap_mps
        return total

    def assign_cover(self, helpers: list[str], alternatives: list[str]) -> dict[str, str]:
        """Each alternative exit to the helper that can reach it soonest, greedily, by ETA.

        Replaces a fixed-order pairing in which the helper sent to an exit did not depend on
        whether it could get there. Ties by id; deterministic.
        """
        cover: dict[str, str] = {}
        free = list(helpers)
        for alt in alternatives:
            if not free:
                break
            best = min(free, key=lambda h: (self.eta_s(h, alt), h))
            cover[best] = alt
            free.remove(best)
        return cover

    def budget_left(self) -> bool:
        return (
            self.expansions < self.max_expansions
            and time.process_time() - self.started < self.max_seconds
        )

    # -- candidate generation -------------------------------------------------------------

    def evader_path(self, world: World) -> list[dict]:
        """Decisions the evader took: where, when, what it chose, and what else it could."""
        out = []
        for d in world.evader.decisions:
            if d.chosen is None:
                continue
            out.append(
                {
                    "from_edge": d.current_edge,
                    "chosen": d.chosen,
                    "alternatives": [a for a in d.admissible if a != d.chosen],
                    "decision": d.decision_index,
                }
            )
        return out

    def candidates(self, path: list[dict]):
        """Interception candidates: (decision step, target edge, finisher approach, hold).

        Every ADMISSIBLE edge at each evader decision is a target - not only the one the
        evader chose. The first version targeted only the chosen edge, and there covering
        the alternatives is redundant by construction: the evader was going that way anyway,
        so every capture it found was correctly judged a single-pursuer capture. A capture
        that needs a helper has to steer the evader onto an edge it would NOT have taken, so
        unchosen targets are tried first.
        """
        ordered = []
        for step in path:
            admissible = [step["chosen"], *step["alternatives"]]
            for target in admissible:
                ordered.append((0 if target != step["chosen"] else 1, step, target, admissible))
        ordered.sort(key=lambda item: item[0])
        for _, step, target, admissible in ordered:
            info = self.net.edges[target]
            if not info.single_lane or info.length_m < 12.0:
                continue
            approaches = [f for (f, t) in self.net.links if t == target and f != step["from_edge"]]
            for hold in FINISHER_HOLDS_M:
                if hold > info.length_m - 1.0:
                    continue
                for approach in sorted(approaches):
                    yield step, target, [a for a in admissible if a != target], approach, hold

    # -- the search -----------------------------------------------------------------------

    def search(self, accept=None) -> dict:
        """`accept(result, plan) -> (ok, detail)`, if given, must also hold for a CONSTRUCTED to
        end the search (A-58's native-replication prerequisite); a model construction it rejects
        is logged as `CONSTRUCTED_NOT_ACCEPTED` and the search goes on."""
        idle = Plan()
        baseline = self.simulate(idle)
        queue = [self.evader_path(baseline)]
        seen: set = set()
        pursuers = sorted(self.sc.pursuer_starts)
        while queue and self.budget_left():
            path = queue.pop(0)
            for step, target, alternatives, approach, hold in self.candidates(path):
                if not self.budget_left():
                    break
                key = (step["decision"], target, approach, hold)
                if key in seen:
                    continue
                seen.add(key)
                if len(alternatives) > len(pursuers) - 1:
                    continue
                t_d = step["decision"]
                finishers = [p for p in pursuers if self.eta_s(p, approach) <= t_d + 1.0]
                if not finishers:
                    # Keep exploration alive. When no finisher can be in place, a screen that
                    # drops every candidate also stops new evader paths from being generated:
                    # toronto's search died after its baseline. Try the nearest one.
                    finishers = [min(pursuers, key=lambda p: (self.eta_s(p, approach), p))]
                for finisher in finishers:
                    if not self.budget_left():
                        break
                    helpers = [p for p in pursuers if p != finisher]
                    cover = self.assign_cover(helpers, alternatives)
                    for release_offset in RELEASE_OFFSETS:
                        plan = Plan()
                        plan.segments[finisher] = [
                            Segment(0, approach, None),
                            Segment(max(0, t_d + release_offset), target, hold),
                        ]
                        for helper, alt in cover.items():
                            plan.segments[helper] = [Segment(0, alt, 12.0)]
                        w = self.simulate(plan)
                        if w.captured_at_s is not None:
                            result = self.verify(plan)
                            self.log.append(
                                {
                                    "key": list(key),
                                    "finisher": finisher,
                                    "release": release_offset,
                                    "verdict": result["verdict"],
                                    "why": _why(result),
                                }
                            )
                            if result["verdict"] == "CONSTRUCTED" and accept is not None:
                                ok, detail = accept(result, plan)
                                result = {**result, "acceptance": detail}
                                if not ok:
                                    self.log[-1]["verdict"] = "CONSTRUCTED_NOT_ACCEPTED"
                                    self.log[-1]["acceptance"] = detail
                                    self.rejected.append(result)
                                    continue
                            if result["verdict"] == "CONSTRUCTED":
                                return {**result, "tally": self._tally()}
                            if (
                                result["verdict"] != "FACTUAL_FAILED_VERIFICATION"
                                and len(self.captures) < 2000
                            ):
                                self.captures.append(result)
                            elif (
                                result["verdict"] == "FACTUAL_FAILED_VERIFICATION"
                                and len(self.failures) < 200
                            ):
                                self.failures.append(result)
                            if result["verdict"] in (
                                "CAPTURE_NOT_COORDINATED",
                                "B1_CONTRAST_WITHOUT_NECESSITY",
                                "NECESSARY_BUT_B1_NULL",
                            ) and not hasattr(self, "_first_uncoordinated"):
                                self._first_uncoordinated = result
                        elif len(queue) < 200:
                            queue.append(self.evader_path(w))
                        if not self.budget_left():
                            break
        tally = self._tally()
        if hasattr(self, "_first_uncoordinated"):
            return {**self._first_uncoordinated, "tally": tally}
        # A factual capture that FAILED verification is not the same as no capture. The
        # first version returned NO_WITNESS_WITHIN_CAP and hid it; the tally shows it.
        return {
            "verdict": "NO_WITNESS_WITHIN_CAP",
            "expansions": self.expansions,
            "cpu_seconds": round(time.process_time() - self.started, 3),
            "tally": tally,
        }

    def _tally(self) -> dict:
        counts: dict[str, int] = {}
        for entry in self.log:
            counts[entry["verdict"]] = counts.get(entry["verdict"], 0) + 1
        return counts

    # -- verification: judge, D12 helper, counterfactual, determinism ---------------------

    def verify(self, plan: Plan) -> dict:
        factual = self.simulate(plan, record=True)
        again = self.simulate(plan, record=True)
        verdict = judge_capture(factual.trace, "e1", self.params, self.step_s)
        digest = _trace_digest(factual)
        deterministic = digest == _trace_digest(again)
        base = {
            "expansions": self.expansions,
            "cpu_seconds": round(time.process_time() - self.started, 3),
            "plan": {vid: [s.__dict__ for s in segs] for vid, segs in plan.segments.items()},
            "factual": {
                "judge": verdict.verdict.value,
                "reason": verdict.reason,
                "finisher": verdict.finisher,
                "witness_start_s": verdict.witness_start_s,
                "witness_duration_s": verdict.witness_duration_s,
                "collisions": factual.collisions,
                "safety_failures": len(factual.safety_failures),
                "trace_sha256": digest,
                "deterministic": deterministic,
                "evader_decisions": len(factual.evader.decisions),
            },
        }
        if (
            verdict.verdict is not Verdict.SUPPORTED
            or factual.collisions
            or factual.safety_failures
            or not deterministic
        ):
            return {**base, "verdict": "FACTUAL_FAILED_VERIFICATION"}

        start_frame = next(
            f for f in factual.trace if abs(f.time_s - verdict.witness_start_s) < 1e-6
        )
        evader_body = start_frame.vehicles["e1"].rectangle()
        candidates = sorted(
            (body_separation_m(start_frame.vehicles[p].rectangle(), evader_body), p)
            for p in sorted(self.sc.pursuer_starts)
            if p != verdict.finisher
        )
        if not candidates:
            return {
                **base,
                "verdict": "CAPTURE_NOT_COORDINATED",
                "helper": None,
                "reason": "no eligible helper; assistance UNRESOLVED",
            }
        helper = candidates[0][1]
        settle_s = settling_time_s(factual.trace, helper, verdict.witness_start_s)
        settle_decision = int(settle_s // self.decision_s)
        begin = settle_decision - 5
        truncated = begin < 0
        begin = max(0, begin)
        counterfactual = self.simulate(plan, record=True, b1=(helper, begin, begin + 5))
        cf = judge_capture(counterfactual.trace, "e1", self.params, self.step_s)
        b1_positive = cf.verdict is Verdict.REJECTED

        # Necessity check (A-49, the Research lead's decision): the same plan with the helper
        # NEVER acting - physically present, holding at its start, no teleport. D06 asks
        # whether the capture was produced by more than one pursuer's decisions. The b1
        # contrast alone cannot answer that: on a synthetic control the b1 substitute cut in
        # and blocked the evader, so a capture one pursuer achieved alone looked coordinated.
        absent = Plan({vid: segs for vid, segs in plan.segments.items() if vid != helper})
        without = self.simulate(absent, record=True)
        wo = judge_capture(without.trace, "e1", self.params, self.step_s)
        necessary = wo.verdict is Verdict.REJECTED

        if b1_positive and necessary:
            label = "CONSTRUCTED"
        elif b1_positive:
            label = "B1_CONTRAST_WITHOUT_NECESSITY"
        elif necessary:
            # The helper was needed, but D12's window did not see its contribution.
            label = "NECESSARY_BUT_B1_NULL"
        else:
            label = "CAPTURE_NOT_COORDINATED"
        return {
            **base,
            "verdict": label,
            "d12": {
                "rule": "revised 2026-09-25 (A-51): window ends at the helper's settling time",
                "helper": helper,
                "helper_separation_m": round(candidates[0][0], 4),
                "settling_time_s": settle_s,
                "witness_start_s": verdict.witness_start_s,
                "reduces_to_original": settle_s == verdict.witness_start_s,
                "intervention_decisions": [begin, begin + 5],
                "truncated": truncated,
            },
            "counterfactual": {
                "judge": cf.verdict.value,
                "reason": cf.reason,
                "collisions": counterfactual.collisions,
                "safety_failures": len(counterfactual.safety_failures),
            },
            "necessity": {
                "helper_never_acts_judge": wo.verdict.value,
                "reason": wo.reason,
                "collisions": without.collisions,
                "safety_failures": len(without.safety_failures),
            },
        }


SETTLE_RADIUS_M = 1.0
MOVING_MPS = 0.1


def settling_time_s(trace, helper: str, witness_start_s: float) -> float:
    """D12, revised (A-51): when the helper took the position it holds at the witness start.

    The earliest time from which, until the witness start, the helper stays within 1.0 m of
    its witness-start position. A helper still MOVING at the witness start (> 0.1 m/s) has
    not settled, and its settling time is the witness start itself - which makes the rule
    reduce exactly to the original D12 for helpers that act until the capture. Without that
    clause a helper at 5 m/s would 'settle' 0.2 s early and could shift the window by one
    decision.
    """
    frames = [f for f in trace if f.time_s <= witness_start_s + 1e-9]
    if not frames or helper not in frames[-1].vehicles:
        return witness_start_s
    final = frames[-1].vehicles[helper]
    if final.speed_mps > MOVING_MPS:
        return witness_start_s
    settle = witness_start_s
    for frame in reversed(frames):
        body = frame.vehicles.get(helper)
        if body is None:
            break
        if ((body.x - final.x) ** 2 + (body.y - final.y) ** 2) ** 0.5 > SETTLE_RADIUS_M:
            break
        settle = frame.time_s
    return settle


def _why(result: dict) -> dict:
    factual = result.get("factual", {})
    return {
        "judge": factual.get("judge"),
        "collisions": len(factual.get("collisions", [])),
        "safety_failures": factual.get("safety_failures"),
        "deterministic": factual.get("deterministic"),
    }


def _trace_digest(world: World) -> str:
    rows = [
        (
            f.time_s,
            sorted(
                (k, round(v.x, 9), round(v.y, 9), round(v.speed_mps, 9))
                for k, v in f.vehicles.items()
            ),
        )
        for f in world.trace
    ]
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()
