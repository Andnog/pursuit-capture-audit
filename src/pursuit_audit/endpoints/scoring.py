"""Score one episode under every endpoint, so that a study can report them side by side."""

from __future__ import annotations

from ..domain.trace import Frame
from .operational import CaptureParameters, operational_capture
from .proximity import DISTANCES, ProximityRule, proximity

DEFAULT_THRESHOLDS_M = (5.0, 10.0)


def score_trace(
    frames: list[Frame],
    evader: str,
    pursuers: list[str] | None = None,
    params: CaptureParameters | None = None,
    thresholds_m: tuple[float, ...] = DEFAULT_THRESHOLDS_M,
) -> dict:
    """Return one flat row for a results table: operational capture and every proximity rule.

    Args:
        frames: The trace of the episode.
        evader: Identifier of the evader.
        pursuers: Identifiers of the pursuers; by default every other vehicle.
        params: Thresholds of operational capture.
        thresholds_m: Thresholds of the proximity rules; one rule per threshold and distance.
    """
    capture = operational_capture(frames, evader, pursuers, params)
    row = {
        "oc": capture.captured,
        "oc_time_s": capture.capture_time_s,
        "oc_pursuer": capture.pursuer,
        "oc_longest_run_s": round(capture.longest_run_s, 3),
        "oc_closest_failure": capture.closest_failure,
    }
    for threshold in thresholds_m:
        for kind in ("body", "centre", "front"):
            if kind not in DISTANCES:
                continue
            rule = ProximityRule(threshold, kind)
            outcome = proximity(frames, evader, rule, pursuers)
            row[rule.name], row[f"{rule.name}_time_s"] = outcome.reached, outcome.time_s
    return row
