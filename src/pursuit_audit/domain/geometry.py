"""Oriented-rectangle geometry for vehicle bodies.

A body is a rectangle given by its centre, its heading in radians (0 = +x, counter-clockwise), its
length along the heading and its width across it. Distances between centres, or between front
bumpers, are not distances between bodies: two 5 m cars stopped bumper to bumper are 5 m apart
centre to centre.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]
_CORNER_SIGNS = ((1, 1), (-1, 1), (-1, -1), (1, -1))


@dataclass(frozen=True)
class Body:
    """The state of one vehicle at one instant.

    Attributes:
        x: Abscissa of the body centre, in metres.
        y: Ordinate of the body centre, in metres.
        heading_rad: Heading, measured from +x counter-clockwise.
        speed_mps: Speed along the heading; never negative.
        length_m: Extent along the heading.
        width_m: Extent across the heading.
    """

    x: float
    y: float
    heading_rad: float
    speed_mps: float
    length_m: float
    width_m: float

    def corners(self) -> tuple[Point, Point, Point, Point]:
        """Return the four corners, counter-clockwise in the vehicle frame."""
        cos_h, sin_h = math.cos(self.heading_rad), math.sin(self.heading_rad)
        half_l, half_w = self.length_m / 2.0, self.width_m / 2.0
        return tuple(
            (
                self.x + along * half_l * cos_h - across * half_w * sin_h,
                self.y + along * half_l * sin_h + across * half_w * cos_h,
            )
            for along, across in _CORNER_SIGNS
        )  # type: ignore[return-value]

    def front(self) -> Point:
        """Return the front-bumper centre, the point most simulators report as the position."""
        return (
            self.x + self.length_m / 2.0 * math.cos(self.heading_rad),
            self.y + self.length_m / 2.0 * math.sin(self.heading_rad),
        )

    def is_valid(self) -> bool:
        """Tell whether every value is a finite number in its physical range."""
        values = (self.x, self.y, self.heading_rad, self.speed_mps, self.length_m, self.width_m)
        return (
            all(isinstance(v, (int, float)) and math.isfinite(v) for v in values)
            and self.speed_mps >= 0.0
            and self.length_m > 0.0
            and self.width_m > 0.0
        )


def centre_from_front(x: float, y: float, heading_rad: float, length_m: float) -> Point:
    """Return the body centre of a vehicle whose front bumper is at ``(x, y)``."""
    return (
        x - length_m / 2.0 * math.cos(heading_rad),
        y - length_m / 2.0 * math.sin(heading_rad),
    )


def heading_from_compass_deg(angle_deg: float) -> float:
    """Convert a compass angle (0 = north, clockwise) to radians from +x, counter-clockwise."""
    return math.radians(90.0 - angle_deg)


def heading_difference_rad(first: float, second: float) -> float:
    """Return the absolute difference between two headings, wrapped into ``[0, pi]``.

    Wrapping matters: headings near +pi and -pi describe almost the same direction.
    """
    return abs((first - second + math.pi) % (2.0 * math.pi) - math.pi)


def _projection(corners: tuple[Point, ...], axis: Point) -> tuple[float, float]:
    values = [p[0] * axis[0] + p[1] * axis[1] for p in corners]
    return min(values), max(values)


def bodies_overlap(first: Body, second: Body) -> bool:
    """Tell whether two bodies intersect, with the separating-axis test."""
    corners_a, corners_b = first.corners(), second.corners()
    for body in (first, second):
        cos_h, sin_h = math.cos(body.heading_rad), math.sin(body.heading_rad)
        for axis in ((cos_h, sin_h), (-sin_h, cos_h)):
            low_a, high_a = _projection(corners_a, axis)
            low_b, high_b = _projection(corners_b, axis)
            if high_a < low_b or high_b < low_a:
                return False
    return True


def _point_to_segment_m(point: Point, start: Point, end: Point) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    squared = dx * dx + dy * dy
    if squared == 0.0:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    t = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / squared
    t = max(0.0, min(1.0, t))
    return math.hypot(point[0] - (start[0] + t * dx), point[1] - (start[1] + t * dy))


def body_gap_m(first: Body, second: Body) -> float:
    """Return the smallest distance between the boundaries of two bodies; 0 if they overlap."""
    if bodies_overlap(first, second):
        return 0.0
    corners_a, corners_b = first.corners(), second.corners()
    best = math.inf
    for source, target in ((corners_a, corners_b), (corners_b, corners_a)):
        for point in source:
            for i in range(4):
                best = min(best, _point_to_segment_m(point, target[i], target[(i + 1) % 4]))
    return best


def centre_distance_m(first: Body, second: Body) -> float:
    """Return the distance between the two body centres."""
    return math.hypot(first.x - second.x, first.y - second.y)


def front_distance_m(first: Body, second: Body) -> float:
    """Return the distance between the two front-bumper centres."""
    (ax, ay), (bx, by) = first.front(), second.front()
    return math.hypot(ax - bx, ay - by)
