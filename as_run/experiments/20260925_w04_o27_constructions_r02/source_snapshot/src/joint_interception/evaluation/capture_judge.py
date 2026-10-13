"""Independent capture judge.

Decides whether a physical trace contains a valid operational-contact witness under the
frozen capture contract. It is INDEPENDENT of the selector: it receives a trace and the
contract, never a policy, a reward or an opportunity.

Trivalent. A missing frame makes the verdict UNKNOWN rather than 0: an incomplete trace
is unresolved evidence, not observed failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.contracts import CaptureParameters
from ..domain.geometry import Rectangle, body_separation_m, heading_difference_rad
from ..opportunities.types import Verdict


@dataclass(frozen=True)
class VehicleFrame:
    vehicle_id: str
    x: float
    y: float
    heading_rad: float
    speed_mps: float
    length_m: float
    width_m: float

    def rectangle(self) -> Rectangle:
        return Rectangle(self.x, self.y, self.heading_rad, self.length_m, self.width_m)


@dataclass(frozen=True)
class TraceFrame:
    time_s: float
    vehicles: dict[str, VehicleFrame]


@dataclass
class CaptureVerdict:
    verdict: Verdict
    reason: str
    finisher: str | None = None
    witness_start_s: float | None = None
    witness_end_s: float | None = None
    witness_duration_s: float = 0.0
    longest_run_s: float = 0.0
    per_pursuer_longest_run_s: dict[str, float] = field(default_factory=dict)
    detail: dict = field(default_factory=dict)


def _conditions_hold(
    pursuer: VehicleFrame, evader: VehicleFrame, params: CaptureParameters
) -> tuple[bool, str]:
    """Every condition of the operational-contact predicate, at one frame."""
    gap = body_separation_m(pursuer.rectangle(), evader.rectangle())
    if gap <= params.geometry_tolerance_m:
        return False, "body_overlap_or_within_tolerance"
    if gap < params.contact_gap_min_m:
        return False, "separation_below_contact_gap_min"
    if gap > params.contact_gap_max_m:
        return False, "separation_above_contact_gap_max"
    if evader.speed_mps > params.capture_speed_max_mps:
        return False, "evader_speed_above_capture_speed_max"
    if pursuer.speed_mps > params.capture_speed_max_mps:
        return False, "pursuer_speed_above_capture_speed_max"
    if abs(pursuer.speed_mps - evader.speed_mps) > params.relative_speed_max_mps:
        return False, "relative_speed_above_max"
    if (
        heading_difference_rad(pursuer.heading_rad, evader.heading_rad)
        > params.orientation_tolerance_rad
    ):
        return False, "relative_orientation_outside_tolerance"
    return True, "all_conditions_hold"


def judge_capture(
    trace: list[TraceFrame],
    evader_id: str,
    params: CaptureParameters,
    physical_step_s: float,
    safety_failure_times_s: frozenset[float] = frozenset(),
    trace_is_complete: bool = True,
) -> CaptureVerdict:
    """Judge one trace.

    The witness must be held by a SINGLE pursuer continuously. Allowing the role to pass
    between pursuers mid-interval would let a sequence of brief proximities masquerade as
    one sustained containment.
    """
    if not trace:
        return CaptureVerdict(Verdict.UNKNOWN, "empty_trace")

    times = [frame.time_s for frame in trace]
    gaps = [
        round(times[i + 1] - times[i], 9) != round(physical_step_s, 9)
        for i in range(len(times) - 1)
    ]
    if any(gaps):
        return CaptureVerdict(
            Verdict.UNKNOWN,
            "trace_has_missing_frames",
            detail={"expected_step_s": physical_step_s},
        )
    if not trace_is_complete:
        return CaptureVerdict(Verdict.UNKNOWN, "trace_declared_incomplete")

    pursuer_ids = sorted({vid for frame in trace for vid in frame.vehicles if vid != evader_id})

    best: CaptureVerdict | None = None
    longest_overall = 0.0
    per_pursuer: dict[str, float] = {}

    for pursuer_id in pursuer_ids:
        run_start_index: int | None = None
        longest_for_pursuer = 0.0
        for index, frame in enumerate(trace):
            evader = frame.vehicles.get(evader_id)
            pursuer = frame.vehicles.get(pursuer_id)
            holds = False
            if evader is not None and pursuer is not None:
                holds, _ = _conditions_hold(pursuer, evader, params)
            if holds and frame.time_s in safety_failure_times_s:
                holds = False

            if holds and run_start_index is None:
                run_start_index = index
            closing = not holds or index == len(trace) - 1
            if closing and run_start_index is not None:
                end_index = index if holds else index - 1
                duration = trace[end_index].time_s - trace[run_start_index].time_s
                longest_for_pursuer = max(longest_for_pursuer, duration)
                if duration + 1e-9 >= params.dwell_time_s and best is None:
                    best = CaptureVerdict(
                        Verdict.SUPPORTED,
                        "continuous_witness_satisfies_dwell",
                        finisher=pursuer_id,
                        witness_start_s=trace[run_start_index].time_s,
                        witness_end_s=trace[end_index].time_s,
                        witness_duration_s=duration,
                    )
                run_start_index = None
        per_pursuer[pursuer_id] = longest_for_pursuer
        longest_overall = max(longest_overall, longest_for_pursuer)

    if best is not None:
        best.longest_run_s = longest_overall
        best.per_pursuer_longest_run_s = per_pursuer
        return best

    return CaptureVerdict(
        Verdict.REJECTED,
        "no_continuous_run_reaches_dwell",
        longest_run_s=longest_overall,
        per_pursuer_longest_run_s=per_pursuer,
        detail={"dwell_required_s": params.dwell_time_s},
    )
