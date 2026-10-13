"""Capture endpoints: operational capture and proximity rules, scored on the same trace.

Operational capture (OC): for at least `dwell_s`, continuously and for one and the same pursuer,
- the body gap is within [gap_min_m, gap_max_m];
- both speeds are at most `speed_max_mps` and they differ by at most `relative_speed_max_mps`;
- the headings differ by at most `heading_tolerance_rad`;
- the evader is behind the pursuer, within `lateral_max_m` of the pursuer's axis.
The witness cannot pass from one pursuer to another, and it is broken by any frame in which the
pursuer or the evader is missing.

Proximity rules declare success at the first instant a distance falls to a threshold. Which
distance is part of the rule: between bodies, between centres, or between front bumpers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .geometry import Body, body_gap_m, heading_difference_rad
from .trace import Frame, validate_trace


@dataclass(frozen=True)
class CaptureParameters:
    gap_min_m: float = 0.3
    gap_max_m: float = 2.0
    speed_max_mps: float = 1.0
    relative_speed_max_mps: float = 1.0
    heading_tolerance_rad: float = 0.2618  # 15 degrees
    lateral_max_m: float = 1.0
    dwell_s: float = 2.0
    overlap_tolerance_m: float = 0.01


@dataclass
class CaptureResult:
    captured: bool
    pursuer: str | None = None
    witness_start_s: float | None = None
    capture_time_s: float | None = None  # the first instant at which the dwell is complete
    longest_run_s: float = 0.0
    closest_failure: str | None = None  # why the frame with the smallest body gap did not qualify
    reasons: dict[str, int] = field(default_factory=dict)


@dataclass
class ProximityResult:
    reached: bool
    time_s: float | None = None
    pursuer: str | None = None
    minimum_m: float = math.inf


def conditions(pursuer: Body, evader: Body, p: CaptureParameters) -> tuple[bool, str]:
    """Whether the OC conditions hold at one instant, and the first one that fails."""
    if not (pursuer.is_valid() and evader.is_valid()):
        return False, "invalid_values"
    gap = body_gap_m(pursuer, evader)
    if gap <= p.overlap_tolerance_m:
        return False, "bodies_overlap"
    if gap < p.gap_min_m:
        return False, "gap_below_minimum"
    if gap > p.gap_max_m:
        return False, "gap_above_maximum"
    if evader.speed_mps > p.speed_max_mps:
        return False, "evader_moving"
    if pursuer.speed_mps > p.speed_max_mps:
        return False, "pursuer_moving"
    if abs(pursuer.speed_mps - evader.speed_mps) > p.relative_speed_max_mps:
        return False, "relative_speed"
    if heading_difference_rad(pursuer.heading_rad, evader.heading_rad) > p.heading_tolerance_rad:
        return False, "headings_differ"
    dx, dy = pursuer.x - evader.x, pursuer.y - evader.y
    c, s = math.cos(pursuer.heading_rad), math.sin(pursuer.heading_rad)
    if dx * c + dy * s <= 0.0:
        return False, "evader_not_behind_pursuer"
    if abs(-dx * s + dy * c) > p.lateral_max_m:
        return False, "lateral_offset"
    return True, "all_conditions_hold"


def operational_capture(
    frames: list[Frame],
    evader: str,
    pursuers: list[str] | None = None,
    params: CaptureParameters | None = None,
    step_s: float | None = None,
) -> CaptureResult:
    """Score one trace under OC. The earliest completed dwell of any pursuer is the capture."""
    params = params or CaptureParameters()
    validate_trace(frames, step_s)
    if pursuers is None:
        pursuers = sorted({v for f in frames for v in f.vehicles if v != evader})
    result = CaptureResult(captured=False)
    closest = (math.inf, None)
    best_time = math.inf
    for pid in pursuers:
        start = None
        for frame in frames:
            e, q = frame.vehicles.get(evader), frame.vehicles.get(pid)
            holds, why = (
                (False, "vehicle_missing") if e is None or q is None else conditions(q, e, params)
            )
            if not holds:
                result.reasons[why] = result.reasons.get(why, 0) + 1
                if e is not None and q is not None and e.is_valid() and q.is_valid():
                    gap = body_gap_m(q, e)
                    if gap < closest[0]:
                        closest = (gap, why)
                start = None
                continue
            if start is None:
                start = frame.time_s
            run = frame.time_s - start
            result.longest_run_s = max(result.longest_run_s, run)
            # The scan continues after a capture so that `longest_run_s` describes the whole trace.
            if run + 1e-9 >= params.dwell_s and frame.time_s < best_time:
                best_time = frame.time_s
                result.captured, result.pursuer = True, pid
                result.witness_start_s, result.capture_time_s = start, frame.time_s
    if not result.captured:
        result.closest_failure = closest[1]
    return result


def _distance(kind: str, a: Body, b: Body) -> float:
    if kind == "body":
        return body_gap_m(a, b)
    if kind == "centre":
        return math.hypot(a.x - b.x, a.y - b.y)
    if kind == "front":
        (ax, ay), (bx, by) = a.front(), b.front()
        return math.hypot(ax - bx, ay - by)
    raise ValueError(f"unknown distance kind {kind!r}; use 'body', 'centre' or 'front'")


def proximity(
    frames: list[Frame],
    evader: str,
    threshold_m: float,
    kind: str = "body",
    pursuers: list[str] | None = None,
) -> ProximityResult:
    """First instant at which a pursuer is within `threshold_m` of the evader, for one distance."""
    out = ProximityResult(reached=False)
    for frame in frames:
        e = frame.vehicles.get(evader)
        if e is None or not e.is_valid():
            continue
        for pid, q in sorted(frame.vehicles.items()):
            if pid == evader or (pursuers is not None and pid not in pursuers) or not q.is_valid():
                continue
            d = _distance(kind, q, e)
            out.minimum_m = min(out.minimum_m, d)
            if d <= threshold_m and not out.reached:
                out.reached, out.time_s, out.pursuer = True, frame.time_s, pid
    return out


def score_trace(
    frames: list[Frame],
    evader: str,
    pursuers: list[str] | None = None,
    params: CaptureParameters | None = None,
    thresholds_m: tuple[float, ...] = (5.0, 10.0),
) -> dict:
    """One episode under every endpoint, as a flat dictionary ready for a results table."""
    oc = operational_capture(frames, evader, pursuers, params)
    row = {
        "oc": oc.captured,
        "oc_time_s": oc.capture_time_s,
        "oc_pursuer": oc.pursuer,
        "oc_longest_run_s": round(oc.longest_run_s, 3),
        "oc_closest_failure": oc.closest_failure,
    }
    for threshold in thresholds_m:
        for kind in ("body", "centre", "front"):
            r = proximity(frames, evader, threshold, kind, pursuers)
            name = f"{kind}_{threshold:g}m"
            row[name], row[f"{name}_time_s"] = r.reached, r.time_s
    return row
