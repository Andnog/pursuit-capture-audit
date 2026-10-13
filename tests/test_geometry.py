import math

import pytest

from pursuit_audit.domain.geometry import (
    Body,
    bodies_overlap,
    body_gap_m,
    centre_distance_m,
    centre_from_front,
    front_distance_m,
    heading_difference_rad,
    heading_from_compass_deg,
)


def car(x: float, y: float, heading: float = 0.0, speed: float = 0.0) -> Body:
    return Body(x, y, heading, speed, 5.0, 1.8)


def test_two_cars_in_file_have_a_gap_but_are_a_car_length_apart():
    leader, follower = car(6.0, 0.0), car(0.0, 0.0)
    assert body_gap_m(leader, follower) == pytest.approx(1.0)
    assert centre_distance_m(leader, follower) == pytest.approx(6.0)
    assert front_distance_m(leader, follower) == pytest.approx(6.0)


def test_cars_passing_in_opposite_lanes_are_close_by_every_distance():
    one, other = car(0.0, 0.0), car(1.0, 3.2, heading=math.pi)
    assert body_gap_m(one, other) == pytest.approx(3.2 - 1.8)
    assert centre_distance_m(one, other) < 5.0


def test_overlapping_bodies_have_zero_gap():
    assert bodies_overlap(car(0.0, 0.0), car(2.0, 0.5))
    assert body_gap_m(car(0.0, 0.0), car(2.0, 0.5)) == 0.0


def test_gap_is_symmetric_and_handles_rotation():
    one, other = car(0.0, 0.0), car(4.0, 4.0, heading=math.pi / 2)
    assert body_gap_m(one, other) == pytest.approx(body_gap_m(other, one))
    assert body_gap_m(one, other) > 0.0


def test_heading_difference_wraps_around_the_circle():
    assert heading_difference_rad(math.pi - 0.05, -math.pi + 0.05) == pytest.approx(0.1)
    assert heading_difference_rad(0.0, math.pi) == pytest.approx(math.pi)


def test_compass_north_is_plus_y():
    assert heading_from_compass_deg(0.0) == pytest.approx(math.pi / 2)
    assert heading_from_compass_deg(90.0) == pytest.approx(0.0)


def test_centre_from_front_inverts_front():
    body = car(3.0, -2.0, heading=0.7)
    assert centre_from_front(*body.front(), body.heading_rad, body.length_m) == pytest.approx(
        (body.x, body.y)
    )


@pytest.mark.parametrize(
    "body",
    [
        Body(math.nan, 0.0, 0.0, 0.0, 5.0, 1.8),
        Body(0.0, 0.0, 0.0, -1.0, 5.0, 1.8),
        Body(0.0, 0.0, 0.0, 0.0, 0.0, 1.8),
        Body(0.0, 0.0, math.inf, 0.0, 5.0, 1.8),
    ],
)
def test_invalid_bodies_are_recognised(body: Body):
    assert not body.is_valid()
