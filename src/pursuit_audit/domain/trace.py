"""Traces: what an episode has to provide to be scored.

A trace is a list of frames at a constant step. Each frame gives, for every vehicle present, the
body centre, heading, speed and body dimensions. On disk a trace is JSON Lines, one frame per line:

    {"t": 12.3, "vehicles": {"e1": {"x": 1.0, "y": 2.0, "heading_rad": 0.0, "speed": 3.1,
                                    "length": 5.0, "width": 1.8}, "p1": {...}}}

``heading_deg`` (compass: 0 = north, clockwise) may be given instead of ``heading_rad``, and
``front_x``/``front_y`` (front-bumper position) instead of ``x``/``y``.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .geometry import Body, centre_from_front, heading_from_compass_deg

_MINIMUM_FRAMES = 2


class TraceError(ValueError):
    """The trace cannot be used as evidence: missing fields, bad values or an irregular step."""


@dataclass(frozen=True)
class Frame:
    """The vehicles present at one instant."""

    time_s: float
    vehicles: Mapping[str, Body]


def body_from_record(record: Mapping[str, float]) -> Body:
    """Build a body from one vehicle record of a trace file.

    Raises:
        TraceError: If a field is missing or is not a number.
    """
    try:
        if "heading_rad" in record:
            heading = float(record["heading_rad"])
        else:
            heading = heading_from_compass_deg(float(record["heading_deg"]))
        length, width = float(record["length"]), float(record["width"])
        if "x" in record:
            x, y = float(record["x"]), float(record["y"])
        else:
            x, y = centre_from_front(
                float(record["front_x"]), float(record["front_y"]), heading, length
            )
        return Body(x, y, heading, float(record["speed"]), length, width)
    except (KeyError, TypeError, ValueError) as error:
        raise TraceError(f"vehicle record is incomplete or not numeric: {error}") from error


def parse_trace(lines: Iterable[str], source: str = "<trace>") -> list[Frame]:
    """Parse the lines of a JSON Lines trace."""
    frames = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            vehicles = {vid: body_from_record(r) for vid, r in raw["vehicles"].items()}
            frames.append(Frame(float(raw["t"]), vehicles))
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise TraceError(f"{source}, line {number}: {error}") from error
    return frames


def load_trace(path: str) -> list[Frame]:
    """Read a trace from a JSON Lines file."""
    with open(path, encoding="utf-8") as handle:
        return parse_trace(handle, source=path)


def validate_trace(frames: list[Frame], step_s: float | None = None) -> float:
    """Check values and cadence, and return the step.

    An incomplete or irregular trace is unresolved evidence, not an observed failure, so it is
    refused instead of being scored.

    Raises:
        TraceError: On any defect.
    """
    if len(frames) < _MINIMUM_FRAMES:
        raise TraceError("a trace needs at least two frames")
    for frame in frames:
        if not math.isfinite(frame.time_s):
            raise TraceError("non-finite time")
        for vehicle_id, body in frame.vehicles.items():
            if not body.is_valid():
                raise TraceError(f"invalid values for {vehicle_id} at t={frame.time_s}")
    steps = [round(b.time_s - a.time_s, 9) for a, b in zip(frames, frames[1:], strict=False)]
    step = steps[0] if step_s is None else round(step_s, 9)
    if step <= 0 or any(s != step for s in steps):
        raise TraceError(f"frames are not at a constant step of {step} s")
    return step
