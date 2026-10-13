"""Earliest operational-capture instant of a trace (A-137, fifth review, finding F5-2).

The capture instant is the first frame at which some pursuer has satisfied every condition of the
operational-capture predicate continuously for the dwell time. Continuity is per pursuer and is
broken by ANY frame in which the predicate cannot be asserted for that pursuer: the predicate
fails, the pursuer is absent, the evader is absent, or a value is invalid.

The earlier helpers (`scripts/run_test_confirmation._capture_time` and
`scripts/audit_d06_persistence._witness`, both kept unchanged) reset a pursuer's run only when the
pursuer was present and the predicate failed. A pursuer missing from some frames therefore kept its
run open, and two separate fragments could be joined into one witness. `earliest_capture` replaces
them. `judge_earliest_capture` computes the same instant through the independent judge, one
pursuer at a time, and is used to cross-check it.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.contracts import CaptureParameters
from ..opportunities.types import Verdict
from .capture_judge import TraceFrame, _conditions_hold, judge_capture, trace_defect


class TraceIntegrityError(ValueError):
    """The trace cannot support a capture instant: irregular cadence or invalid values."""


@dataclass(frozen=True)
class CaptureInstant:
    time_s: float
    pursuer_id: str
    run_start_s: float


def check_trace(trace: list[TraceFrame], physical_step_s: float) -> None:
    """Raise TraceIntegrityError unless the trace is regular and every value is valid."""
    for a, b in zip(trace, trace[1:], strict=False):
        if round(b.time_s - a.time_s, 9) != round(physical_step_s, 9):
            raise TraceIntegrityError(f"irregular cadence between {a.time_s!r} and {b.time_s!r}")
    defect = trace_defect(trace)
    if defect is not None:
        raise TraceIntegrityError(f"invalid value: {defect}")


def earliest_capture(
    trace: list[TraceFrame],
    evader_id: str,
    params: CaptureParameters,
    physical_step_s: float,
) -> CaptureInstant | None:
    """The earliest capture instant, or None if no pursuer's continuous run reaches the dwell."""
    check_trace(trace, physical_step_s)
    since: dict[str, float] = {}
    for frame in trace:
        evader = frame.vehicles.get(evader_id)
        holding = set()
        if evader is not None:
            for pursuer_id in sorted(frame.vehicles):
                if pursuer_id == evader_id:
                    continue
                if _conditions_hold(frame.vehicles[pursuer_id], evader, params)[0]:
                    holding.add(pursuer_id)
        # A pursuer that is absent, or for which the predicate does not hold, loses its run.
        for pursuer_id in [p for p in since if p not in holding]:
            del since[pursuer_id]
        for pursuer_id in sorted(holding):
            start = since.setdefault(pursuer_id, frame.time_s)
            if frame.time_s - start + 1e-9 >= params.dwell_time_s:
                return CaptureInstant(frame.time_s, pursuer_id, start)
    return None


def judge_earliest_capture(
    trace: list[TraceFrame],
    evader_id: str,
    params: CaptureParameters,
    physical_step_s: float,
) -> CaptureInstant | None:
    """The same instant through the independent judge: its first witness for each pursuer alone,
    then the earliest over pursuers (ties broken by pursuer id, as in `earliest_capture`)."""
    pursuers = sorted({v for frame in trace for v in frame.vehicles if v != evader_id})
    best: CaptureInstant | None = None
    for pursuer_id in pursuers:
        own = [
            TraceFrame(
                frame.time_s,
                {v: f for v, f in frame.vehicles.items() if v in (evader_id, pursuer_id)},
            )
            for frame in trace
        ]
        verdict = judge_capture(own, evader_id, params, physical_step_s)
        if verdict.verdict is Verdict.UNKNOWN:
            raise TraceIntegrityError(verdict.reason)
        if verdict.verdict is not Verdict.SUPPORTED:
            continue
        instant = CaptureInstant(
            round(verdict.witness_start_s + params.dwell_time_s, 6),
            pursuer_id,
            verdict.witness_start_s,
        )
        if best is None or instant.time_s < best.time_s - 1e-9:
            best = instant
    return best


def absent_frames(trace: list[TraceFrame], vehicle_ids) -> dict[str, dict]:
    """For each vehicle: frames in which it is absent, and how many absences are followed by a
    later presence (a gap inside its record, the pattern that broke the earlier helpers)."""
    out = {}
    for vehicle_id in sorted(vehicle_ids):
        present = [vehicle_id in frame.vehicles for frame in trace]
        if True not in present:
            out[vehicle_id] = {"absent": len(present), "inner_gap_frames": 0, "never_present": True}
            continue
        first = present.index(True)
        last = len(present) - 1 - present[::-1].index(True)
        out[vehicle_id] = {
            "absent": present.count(False),
            "inner_gap_frames": present[first : last + 1].count(False),
            "never_present": False,
        }
    return out


__all__ = [
    "CaptureInstant",
    "TraceIntegrityError",
    "absent_frames",
    "check_trace",
    "earliest_capture",
    "judge_earliest_capture",
]
