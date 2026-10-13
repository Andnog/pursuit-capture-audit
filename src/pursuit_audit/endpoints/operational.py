"""Operational capture (OC): a pursuer directly ahead of a nearly stopped evader, held.

For at least ``dwell_s``, continuously and for one and the same pursuer:

- the body gap is within ``[gap_min_m, gap_max_m]``;
- both speeds are at most ``speed_max_mps`` and they differ by at most ``relative_speed_max_mps``;
- the headings differ by at most ``heading_tolerance_rad``;
- the evader is behind the pursuer, within ``lateral_max_m`` of the pursuer's axis.

The witness cannot pass from one pursuer to another, and any frame in which the pursuer or the
evader is missing breaks it. The rule has no condition on lane identity: the lateral bound is what
excludes two vehicles stopped side by side.

This endpoint measures operational close stopping behind a pursuer. It does not prove that escape
is impossible, and it requires no rear blocker.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..domain.trace import Frame, validate_trace
from .specification import AllOf, Condition, PairState

_TIME_TOLERANCE_S = 1e-9


@dataclass(frozen=True)
class CaptureParameters:
    """Thresholds of the operational capture rule, as registered for the article."""

    gap_min_m: float = 0.3
    gap_max_m: float = 2.0
    speed_max_mps: float = 1.0
    relative_speed_max_mps: float = 1.0
    heading_tolerance_rad: float = 0.2618  # 15 degrees
    lateral_max_m: float = 1.0
    dwell_s: float = 2.0
    overlap_tolerance_m: float = 0.01


def contact_specification(params: CaptureParameters) -> AllOf:
    """Build the instantaneous part of the rule: the conditions that must all hold at one frame."""
    return AllOf(
        (
            Condition("invalid_values", lambda s: s.valid),
            Condition("bodies_overlap", lambda s: s.gap_m > params.overlap_tolerance_m),
            Condition("gap_below_minimum", lambda s: s.gap_m >= params.gap_min_m),
            Condition("gap_above_maximum", lambda s: s.gap_m <= params.gap_max_m),
            Condition("evader_moving", lambda s: s.evader_speed_mps <= params.speed_max_mps),
            Condition("pursuer_moving", lambda s: s.pursuer_speed_mps <= params.speed_max_mps),
            Condition(
                "relative_speed",
                lambda s: (
                    abs(s.pursuer_speed_mps - s.evader_speed_mps) <= params.relative_speed_max_mps
                ),
            ),
            Condition(
                "headings_differ",
                lambda s: s.heading_difference_rad <= params.heading_tolerance_rad,
            ),
            Condition("evader_not_behind_pursuer", lambda s: s.along_m > 0.0),
            Condition("lateral_offset", lambda s: s.lateral_m <= params.lateral_max_m),
        )
    )


@dataclass
class CaptureResult:
    """The verdict of the rule on one trace.

    Attributes:
        captured: Whether some pursuer completed the dwell.
        pursuer: The pursuer of the earliest completed dwell.
        witness_start_s: First instant of that dwell.
        capture_time_s: First instant at which that dwell is complete.
        longest_run_s: Longest continuous run of the contact conditions, for any pursuer.
        closest_failure: Why the frame with the smallest body gap did not qualify.
        reasons: Count of failing frames by condition, over all pursuers.
    """

    captured: bool
    pursuer: str | None = None
    witness_start_s: float | None = None
    capture_time_s: float | None = None
    longest_run_s: float = 0.0
    closest_failure: str | None = None
    reasons: dict[str, int] = field(default_factory=dict)


def operational_capture(
    frames: list[Frame],
    evader: str,
    pursuers: list[str] | None = None,
    params: CaptureParameters | None = None,
    step_s: float | None = None,
) -> CaptureResult:
    """Score one trace under operational capture.

    The earliest completed dwell of any pursuer is the capture. The scan continues after it, so
    that ``longest_run_s`` describes the whole trace.

    Args:
        frames: The trace, at a constant step.
        evader: Identifier of the evader.
        pursuers: Identifiers of the pursuers; by default every other vehicle of the trace.
        params: Thresholds of the rule; by default those of the article.
        step_s: Expected step; by default the step of the trace itself.

    Raises:
        TraceError: If the trace is incomplete or irregular.
    """
    params = params or CaptureParameters()
    validate_trace(frames, step_s)
    rule = contact_specification(params)
    if pursuers is None:
        pursuers = sorted({v for f in frames for v in f.vehicles if v != evader})
    result = CaptureResult(captured=False)
    closest_gap, closest_reason = math.inf, None
    best_time = math.inf
    for pursuer_id in pursuers:
        run_start = None
        for frame in frames:
            evader_body = frame.vehicles.get(evader)
            pursuer_body = frame.vehicles.get(pursuer_id)
            if evader_body is None or pursuer_body is None:
                failure, state = "vehicle_missing", None
            else:
                state = PairState.measure(pursuer_body, evader_body)
                failure = rule.first_failure(state)
            if failure is not None:
                result.reasons[failure] = result.reasons.get(failure, 0) + 1
                if state is not None and state.valid and state.gap_m < closest_gap:
                    closest_gap, closest_reason = state.gap_m, failure
                run_start = None
                continue
            if run_start is None:
                run_start = frame.time_s
            run = frame.time_s - run_start
            result.longest_run_s = max(result.longest_run_s, run)
            if run + _TIME_TOLERANCE_S >= params.dwell_s and frame.time_s < best_time:
                best_time = frame.time_s
                result.captured, result.pursuer = True, pursuer_id
                result.witness_start_s, result.capture_time_s = run_start, frame.time_s
    if not result.captured:
        result.closest_failure = closest_reason
    return result
