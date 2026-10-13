"""A-55 metrics: the declared model's predictions against SUMO, item by item.

Every prediction is RE-INITIALISED from SUMO's own state, so a metric measures the model's
dynamics over its horizon, not drift accumulated since t = 0:

- M4 position: from SUMO's state at each decision, the model's LONGITUDINAL advance over 1.0 s
  against SUMO's (the model has no lateral dimension, so an x-y error would be lane geometry);
- M1 junction entry: each edge entry SUMO records, predicted from SUMO's state at the decision
  5 s before it;
- M2 hold stop: where a pursuer comes to rest while a hold is in force, over the whole replay;
- M3 blocking: a model capture is reproduced when SUMO's own trace, judged by the same capture
  judge, shows a capture by the same finisher starting within 5 s of the model's.

An item touched by a SUMO lane change of the vehicle concerned within the 10 s before it is
`UNKNOWN`: the model has no lanes (A-55).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..domain.contracts import CaptureParameters
from ..evaluation.capture_judge import judge_capture
from ..opportunities.types import Verdict
from ..world.construction import Constructor
from ..world.network import GraphNetwork
from ..world.simulation import World
from .diagnostic_set import ModelRun
from .sumo_replay import SumoRecord

LANE_CHANGE_WINDOW_S = 10.0
M1_LEAD_S = 5.0
M1_SLACK_S = 6.0
M3_WINDOW_S = 5.0
REST_MPS = 0.05
REST_STEPS = 10


@dataclass
class Items:
    m1: list[dict] = field(default_factory=list)
    m2: list[dict] = field(default_factory=list)
    m3: list[dict] = field(default_factory=list)
    m4: list[dict] = field(default_factory=list)


def _lane_changed(rec: SumoRecord, vid: str, t_from: float, t_to: float) -> bool:
    return any(t_from - 1e-9 <= t <= t_to + 1e-9 for t in rec.lane_changes.get(vid, []))


def _edge_end_odometers(rec: SumoRecord) -> list[dict[str, float]]:
    """For each step, each vehicle's odometer at the end of the last NORMAL edge it was on."""
    out: list[dict[str, float]] = []
    last: dict[str, float] = {}
    for states in rec.states:
        for vid, s in states.items():
            road, _, lane_pos, _, odo, _, _, _, lane_id = s
            if not road.startswith(":"):
                last[vid] = odo - lane_pos + rec.lane_lengths[lane_id]
        out.append(dict(last))
    return out


def reinit(
    run: ModelRun,
    net: GraphNetwork,
    domain: dict,
    rec: SumoRecord,
    k: int,
    ends: list[dict[str, float]],
) -> World | None:
    """A model world in SUMO's state at model index k, on the replay's routes and holds."""
    c = Constructor(net, run.scenario, domain, 10**9, 1e12)
    w = c.world(record=False)
    states = rec.states[k]
    if set(states) != set(w.vehicles):
        return None
    decision = k // int(round(w.decision_s / w.step_s))
    for vid, v in w.vehicles.items():
        road, _, lane_pos, speed, odo, ri, _, _, lane_id = states[vid]
        route = rec.routes[vid]
        if ri < 0 or ri >= len(route):
            return None
        v.speed = speed
        v.stuck = False
        if road.startswith(":"):
            if ri + 1 >= len(route):
                return None
            link = net.links.get((route[ri], route[ri + 1]))
            if link is None or vid not in ends[k]:
                return None
            v.edge = route[ri]
            v.in_link = link
            v.offset = max(0.0, min(odo - ends[k][vid], link.via_length_m))
            v.route = list(route[ri + 1 :])
            v.entered_via = (route[ri - 1], route[ri]) if ri > 0 else None
        else:
            if road != route[ri]:
                return None
            info = net.edges[road]
            v.edge = road
            v.in_link = None
            v.offset = lane_pos * info.length_m / rec.lane_lengths[lane_id]
            v.route = list(route[ri + 1 :])
            v.entered_via = (route[ri - 1], road) if ri > 0 else None
        if v.klass == "pursuer":
            v.hold = _hold_at(run, decision, vid)
        else:
            v.decided_on = v.edge
    w.time_s = round(k * w.step_s, 9)
    w.step_index = k
    return w


def _hold_at(run: ModelRun, decision: int, vid: str):
    known = [d for d in run.holds if d <= decision]
    return run.holds[max(known)].get(vid) if known else None


def _advance(w: World, steps: int, run: ModelRun, until_edge: dict | None = None) -> dict:
    """Step the re-initialised world; apply the model's holds at decision boundaries.

    Returns each vehicle's longitudinal advance and, if `until_edge` maps a vehicle to
    `(edge, entries_needed)`, the model time at which it entered that edge.
    """
    per = int(round(w.decision_s / w.step_s))
    advance = {vid: 0.0 for vid in w.vehicles}
    last_edge = {vid: (v.edge, v.in_link is None) for vid, v in w.vehicles.items()}
    entries = {vid: 0 for vid in w.vehicles}
    entered: dict[str, float] = {}
    for _ in range(steps):
        if w.step_index % per == 0:
            decision = w.step_index // per
            for vid, v in w.vehicles.items():
                if v.klass == "pursuer" and decision in run.holds:
                    v.hold = run.holds[decision].get(vid)
        w.step()
        for vid, v in w.vehicles.items():
            advance[vid] += v.speed * w.step_s
            now = (v.edge, v.in_link is None)
            if now[1] and now != last_edge[vid]:
                entries[vid] += 1
                if until_edge and vid in until_edge and vid not in entered:
                    edge, needed = until_edge[vid]
                    if v.edge == edge and entries[vid] == needed:
                        entered[vid] = round(w.time_s, 6)
            last_edge[vid] = now
        if w.captured_at_s is not None:
            break
    return {"advance": advance, "entered": entered}


def score(run: ModelRun, net: GraphNetwork, domain: dict, rec: SumoRecord) -> Items:
    items = Items()
    step_s = domain["timing"]["physical_step_s"]
    per = int(round(domain["timing"]["decision_interval_s"] / step_s))
    last_k = min(len(run.states), len(rec.states)) - 1
    ends = _edge_end_odometers(rec)

    # M4: 1 s longitudinal advance from every decision.
    for k in range(per, last_k - per + 1, per):
        w = reinit(run, net, domain, rec, k, ends)
        if w is None:
            continue
        result = _advance(w, per, run)
        t = k * step_s
        for vid, adv in result["advance"].items():
            if vid not in rec.states[k + per]:
                continue
            observed = rec.states[k + per][vid][4] - rec.states[k][vid][4]
            items.m4.append(
                {
                    "vid": vid,
                    "t": round(t, 6),
                    "error_m": abs(adv - observed),
                    "unknown": _lane_changed(rec, vid, t - LANE_CHANGE_WINDOW_S, t + 1.0),
                }
            )

    # M1: every SUMO edge entry before the model run ended.
    for j in range(1, last_k + 1):
        for vid, s in rec.states[j].items():
            prev = rec.states[j - 1].get(vid)
            if prev is None or s[0].startswith(":") or s[5] == prev[5]:
                continue
            t_s = j * step_s
            d0 = max(0, math.floor(t_s - M1_LEAD_S))
            k0 = d0 * per
            w = reinit(run, net, domain, rec, k0, ends)
            unknown = _lane_changed(rec, vid, k0 * step_s - LANE_CHANGE_WINDOW_S, t_s)
            if w is None:
                continue
            needed = s[5] - rec.states[k0][vid][5]
            steps = int(round((t_s - k0 * step_s + M1_SLACK_S) / step_s))
            result = _advance(w, steps, run, {vid: (s[0], needed)})
            predicted = result["entered"].get(vid)
            items.m1.append(
                {
                    "vid": vid,
                    "edge": s[0],
                    "t_sumo": round(t_s, 6),
                    "t_model": predicted,
                    "error_s": abs(predicted - t_s) if predicted is not None else math.inf,
                    "unknown": unknown,
                }
            )

    # M2: rest positions while a hold is in force.
    decisions = sorted(run.holds)
    for vid in sorted(run.scenario.pursuer_starts):
        intervals: list[tuple[int, int, tuple]] = []
        for i, d in enumerate(decisions):
            hold = run.holds[d].get(vid)
            end = decisions[i + 1] if i + 1 < len(decisions) else d + 1
            if hold is None:
                continue
            if intervals and intervals[-1][2] == hold and intervals[-1][1] == d:
                intervals[-1] = (intervals[-1][0], end, hold)
            else:
                intervals.append((d, end, hold))
        for d_a, d_b, (edge, _pos) in intervals:
            k_a, k_b = d_a * per, min(d_b * per, last_k)
            m_rest = _rest(
                [
                    (s[vid][0] if s[vid][1] is None else None, s[vid][2], s[vid][3])
                    for s in run.states[k_a : k_b + 1]
                ],
                edge,
            )
            s_rest = _rest(
                [
                    (
                        st[vid][0] if vid in st and not st[vid][0].startswith(":") else None,
                        st[vid][2] * net.edges[edge].length_m / rec.lane_lengths[st[vid][8]]
                        if vid in st and st[vid][0] == edge
                        else 0.0,
                        st[vid][3] if vid in st else 0.0,
                    )
                    for st in rec.states[k_a : k_b + 1]
                ],
                edge,
            )
            if m_rest is None and s_rest is None:
                continue
            t_rest = (k_a + (s_rest or m_rest)[0]) * step_s
            items.m2.append(
                {
                    "vid": vid,
                    "edge": edge,
                    "model_rest_m": m_rest[1] if m_rest else None,
                    "sumo_rest_m": s_rest[1] if s_rest else None,
                    "error_m": abs(m_rest[1] - s_rest[1]) if m_rest and s_rest else math.inf,
                    "unknown": _lane_changed(rec, vid, t_rest - LANE_CHANGE_WINDOW_S, t_rest),
                }
            )

    # M3: model captures reproduced by SUMO's own trace.
    if run.capture is not None:
        verdict = judge_capture(rec.trace, "e1", CaptureParameters.from_domain(domain), step_s)
        t_m = run.capture["witness_start_s"]
        reproduced = (
            verdict.verdict is Verdict.SUPPORTED
            and verdict.finisher == run.capture["finisher"]
            and abs(verdict.witness_start_s - t_m) <= M3_WINDOW_S
        )
        items.m3.append(
            {
                "model_finisher": run.capture["finisher"],
                "model_witness_start_s": t_m,
                "sumo_verdict": verdict.verdict.value,
                "sumo_finisher": verdict.finisher,
                "sumo_witness_start_s": verdict.witness_start_s,
                "reproduced": reproduced,
                "unknown": _lane_changed(rec, "e1", t_m - LANE_CHANGE_WINDOW_S, t_m),
            }
        )
    return items


def _rest(samples: list[tuple], edge: str) -> tuple[int, float] | None:
    """First index at which the vehicle is on `edge` below REST_MPS for REST_STEPS steps."""
    run_start = None
    for i, (on, _pos, speed) in enumerate(samples):
        if on == edge and speed < REST_MPS:
            if run_start is None:
                run_start = i
            if i - run_start + 1 >= REST_STEPS:
                return run_start, samples[run_start][1]
        else:
            run_start = None
    return None


THRESHOLDS = {
    "m1_error_s": 1.0,
    "m1_share": 0.90,
    "m2_error_m": 1.0,
    "m2_share": 0.90,
    "m3_share": 0.80,
    "m4_p95_m": 2.0,
}
MINIMUM_SCORED = {"m1": 100, "m2": 30, "m3": 20, "m4": 500}


def _p95(values: list[float]) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)]


def summarise(all_items: list[Items]) -> dict:
    """Pool items over the diagnostic set and apply the frozen A-55 thresholds."""
    pooled = Items()
    for it in all_items:
        pooled.m1 += it.m1
        pooled.m2 += it.m2
        pooled.m3 += it.m3
        pooled.m4 += it.m4
    t = THRESHOLDS
    scored = {
        "m1": [i for i in pooled.m1 if not i["unknown"]],
        "m2": [i for i in pooled.m2 if not i["unknown"]],
        "m3": [i for i in pooled.m3 if not i["unknown"]],
        "m4": [i for i in pooled.m4 if not i["unknown"]],
    }
    m1 = sum(i["error_s"] <= t["m1_error_s"] for i in scored["m1"]) / max(1, len(scored["m1"]))
    m2 = sum(i["error_m"] <= t["m2_error_m"] for i in scored["m2"]) / max(1, len(scored["m2"]))
    m3 = sum(i["reproduced"] for i in scored["m3"]) / max(1, len(scored["m3"]))
    m4 = _p95([i["error_m"] for i in scored["m4"]])
    passes = {
        "m1": m1 >= t["m1_share"],
        "m2": m2 >= t["m2_share"],
        "m3": m3 >= t["m3_share"],
        "m4": m4 <= t["m4_p95_m"],
    }
    enough = {k: len(v) >= MINIMUM_SCORED[k] for k, v in scored.items()}
    if not all(enough.values()):
        verdict = "INCONCLUSIVE_INSUFFICIENT_SAMPLE"
    elif all(passes.values()):
        verdict = "EMPIRICALLY_COVERED"
    else:
        verdict = "NOT_COVERED"
    return {
        "verdict": verdict,
        "m1_share_within_1s": round(m1, 4),
        "m2_share_within_1m": round(m2, 4),
        "m3_share_reproduced": round(m3, 4),
        "m4_p95_m": round(m4, 4),
        "passes": passes,
        "scored": {k: len(v) for k, v in scored.items()},
        "unknown": {
            k: sum(i["unknown"] for i in getattr(pooled, k)) for k in ("m1", "m2", "m3", "m4")
        },
        "enough": enough,
        "thresholds": THRESHOLDS,
        "minimum_scored": MINIMUM_SCORED,
    }
