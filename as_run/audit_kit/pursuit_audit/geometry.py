"""Oriented-rectangle geometry for vehicle bodies.

A body is a rectangle given by its CENTRE, its heading in radians (0 = +x, counter-clockwise), its
length along the heading and its width across it. Distances between centres, or between front
bumpers, are not distances between bodies: two 5 m cars stopped bumper to bumper are 5 m apart
centre to centre.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]


@dataclass(frozen=True)
class Body:
    x: float
    y: float
    heading_rad: float
    speed_mps: float
    length_m: float
    width_m: float

    def corners(self) -> tuple[Point, Point, Point, Point]:
        c, s = math.cos(self.heading_rad), math.sin(self.heading_rad)
        hl, hw = self.length_m / 2.0, self.width_m / 2.0
        return tuple(
            (self.x + a * hl * c - b * hw * s, self.y + a * hl * s + b * hw * c)
            for a, b in ((1, 1), (-1, 1), (-1, -1), (1, -1))
        )  # type: ignore[return-value]

    def front(self) -> Point:
        """The front-bumper centre (the point most simulators report as the position)."""
        return (
            self.x + self.length_m / 2.0 * math.cos(self.heading_rad),
            self.y + self.length_m / 2.0 * math.sin(self.heading_rad),
        )

    def is_valid(self) -> bool:
        values = (self.x, self.y, self.heading_rad, self.speed_mps, self.length_m, self.width_m)
        return (
            all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)
            and self.speed_mps >= 0.0
            and self.length_m > 0.0
            and self.width_m > 0.0
        )


def centre_from_front(x: float, y: float, heading_rad: float, length_m: float) -> Point:
    """Body centre from a front-bumper position (for simulators that report the front)."""
    return (
        x - length_m / 2.0 * math.cos(heading_rad),
        y - length_m / 2.0 * math.sin(heading_rad),
    )


def heading_from_compass_deg(angle_deg: float) -> float:
    """Radians (0 = +x, counter-clockwise) from a compass angle (0 = north, clockwise)."""
    return math.radians(90.0 - angle_deg)


def _project(corners, axis) -> tuple[float, float]:
    values = [p[0] * axis[0] + p[1] * axis[1] for p in corners]
    return min(values), max(values)


def bodies_overlap(a: Body, b: Body) -> bool:
    """Separating-axis test for two rectangles."""
    ca, cb = a.corners(), b.corners()
    for body in (a, b):
        c, s = math.cos(body.heading_rad), math.sin(body.heading_rad)
        for axis in ((c, s), (-s, c)):
            lo_a, hi_a = _project(ca, axis)
            lo_b, hi_b = _project(cb, axis)
            if hi_a < lo_b or hi_b < lo_a:
                return False
    return True


def _point_segment(p: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    squared = dx * dx + dy * dy
    if squared == 0.0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / squared))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def body_gap_m(a: Body, b: Body) -> float:
    """Minimum distance between the boundaries of two bodies; 0 if they overlap."""
    if bodies_overlap(a, b):
        return 0.0
    ca, cb = a.corners(), b.corners()
    best = math.inf
    for source, target in ((ca, cb), (cb, ca)):
        for point in source:
            for i in range(4):
                best = min(best, _point_segment(point, target[i], target[(i + 1) % 4]))
    return best


def heading_difference_rad(first: float, second: float) -> float:
    """Absolute difference between two headings, wrapped into [0, pi]."""
    return abs((first - second + math.pi) % (2.0 * math.pi) - math.pi)
