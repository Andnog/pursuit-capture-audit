"""Oriented-rectangle geometry for vehicle bodies.

NOTE ON THE MODULE TREE: the master plan's directory listing names `domain/contracts.py`,
`domain/observations.py`, `domain/actions.py`, `safety/admission.py` and
`evaluation/capture_judge.py`. This module is an addition, not a substitution: body
geometry is needed by BOTH the safety admission interface and the capture judge, and
duplicating it in each would let the two drift apart and disagree about whether two
vehicles touch.

Centre distance is NOT a substitute for body separation. The master plan says so
explicitly, and the historical obligation O22 recorded a native collision at a reported
positive body gap of 1.959 m precisely because separation was computed from station
arithmetic rather than from geometry.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]


@dataclass(frozen=True)
class Rectangle:
    """An oriented rectangle: centre, heading, length along heading, width across it."""

    x: float
    y: float
    heading_rad: float
    length_m: float
    width_m: float

    def corners(self) -> tuple[Point, Point, Point, Point]:
        """Corners in order, counter-clockwise in the vehicle frame."""
        cos_h, sin_h = math.cos(self.heading_rad), math.sin(self.heading_rad)
        half_l, half_w = self.length_m / 2.0, self.width_m / 2.0
        out = []
        for along, across in ((+1, +1), (-1, +1), (-1, -1), (+1, -1)):
            dx = along * half_l
            dy = across * half_w
            out.append((self.x + dx * cos_h - dy * sin_h, self.y + dx * sin_h + dy * cos_h))
        return tuple(out)  # type: ignore[return-value]


def _project(corners, axis) -> tuple[float, float]:
    values = [c[0] * axis[0] + c[1] * axis[1] for c in corners]
    return min(values), max(values)


def rectangles_overlap(a: Rectangle, b: Rectangle, tolerance: float = 0.0) -> bool:
    """Separating-axis test. Two convex rectangles overlap iff no axis separates them.

    A positive `tolerance` shrinks the overlap decision: bodies closer than the tolerance
    are still reported as non-overlapping.
    """
    corners_a, corners_b = a.corners(), b.corners()
    for rect in (a, b):
        for axis in (
            (math.cos(rect.heading_rad), math.sin(rect.heading_rad)),
            (-math.sin(rect.heading_rad), math.cos(rect.heading_rad)),
        ):
            min_a, max_a = _project(corners_a, axis)
            min_b, max_b = _project(corners_b, axis)
            if max_a < min_b - tolerance or max_b < min_a - tolerance:
                return False
    return True


def _point_segment_distance(point: Point, start: Point, end: Point) -> float:
    px, py = point
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    squared = dx * dx + dy * dy
    if squared == 0.0:
        return math.hypot(px - sx, py - sy)
    t = ((px - sx) * dx + (py - sy) * dy) / squared
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (sx + t * dx), py - (sy + t * dy))


def body_separation_m(a: Rectangle, b: Rectangle) -> float:
    """Minimum distance between two rectangle BOUNDARIES.

    Returns 0.0 when the bodies overlap. For disjoint convex polygons the minimum distance
    is attained at a vertex of one and an edge of the other, so enumerating both directions
    is exact, not an approximation.
    """
    if rectangles_overlap(a, b):
        return 0.0
    corners_a, corners_b = a.corners(), b.corners()
    best = math.inf
    for source, target in ((corners_a, corners_b), (corners_b, corners_a)):
        for point in source:
            for index in range(4):
                best = min(
                    best,
                    _point_segment_distance(point, target[index], target[(index + 1) % 4]),
                )
    return best


def heading_difference_rad(first: float, second: float) -> float:
    """Absolute difference between two headings, wrapped into [0, pi].

    Wrapping matters: headings near +pi and -pi describe almost the same direction, and an
    unwrapped comparison would report a difference of nearly 2*pi and reject a valid
    alignment.
    """
    delta = (first - second + math.pi) % (2.0 * math.pi) - math.pi
    return abs(delta)
