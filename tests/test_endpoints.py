import math
import os

import pytest

import pursuit_audit as pa
from pursuit_audit.endpoints.specification import PairState

STEP = 0.1


def car(x, y, heading=0.0, speed=0.0):
    return pa.Body(x, y, heading, speed, 5.0, 1.8)


def trace(seconds, vehicles_at):
    count = int(round(seconds / STEP)) + 1
    return [pa.Frame(round(i * STEP, 6), vehicles_at(round(i * STEP, 6))) for i in range(count)]


def stopped_in_file(_t):
    return {"e1": car(0.0, 0.0), "p1": car(6.0, 0.0)}


def test_a_held_stop_behind_a_pursuer_is_a_capture_after_the_dwell():
    result = pa.operational_capture(trace(3.0, stopped_in_file), "e1")
    assert result.captured and result.pursuer == "p1"
    assert result.witness_start_s == 0.0
    assert result.capture_time_s == pytest.approx(2.0)


def test_a_stop_shorter_than_the_dwell_is_not_a_capture():
    result = pa.operational_capture(trace(1.9, stopped_in_file), "e1")
    assert not result.captured
    assert result.longest_run_s == pytest.approx(1.9)


def test_the_dwell_cannot_pass_from_one_pursuer_to_another():
    def relay(t):
        ahead = "p1" if t < 1.5 else "p2"
        other = "p2" if ahead == "p1" else "p1"
        return {"e1": car(0.0, 0.0), ahead: car(6.0, 0.0), other: car(60.0, 40.0)}

    result = pa.operational_capture(trace(2.9, relay), "e1")
    assert not result.captured
    assert result.longest_run_s < 2.0


def test_a_missing_frame_of_the_pursuer_breaks_the_dwell():
    def blink(t):
        vehicles = {"e1": car(0.0, 0.0), "p1": car(6.0, 0.0)}
        if 1.0 <= t < 1.1:
            del vehicles["p1"]
        return vehicles

    result = pa.operational_capture(trace(2.9, blink), "e1")
    assert not result.captured
    assert result.reasons["vehicle_missing"] == 1


@pytest.mark.parametrize(
    ("pursuer", "evader", "expected"),
    [
        (car(6.0, 0.0), car(0.0, 0.0), None),
        (car(5.2, 0.0), car(0.0, 0.0), "gap_below_minimum"),
        (car(7.5, 0.0), car(0.0, 0.0), "gap_above_maximum"),
        (car(6.0, 0.0), car(0.0, 0.0, speed=1.5), "evader_moving"),
        (car(6.0, 0.0, speed=1.5), car(0.0, 0.0), "pursuer_moving"),
        (car(6.0, 0.0, heading=0.5), car(0.0, 0.0), "headings_differ"),
        (car(-6.0, 0.0), car(0.0, 0.0), "evader_not_behind_pursuer"),
        (car(0.5, 3.2), car(0.0, 0.0), "lateral_offset"),
        (car(2.0, 0.0), car(0.0, 0.0), "bodies_overlap"),
        (car(math.nan, 0.0), car(0.0, 0.0), "invalid_values"),
    ],
)
def test_each_condition_is_reported_by_name(pursuer, evader, expected):
    rule = pa.contact_specification(pa.CaptureParameters())
    assert rule.first_failure(PairState.measure(pursuer, evader)) == expected


def test_side_by_side_stopped_cars_are_not_a_capture():
    def adjacent(_t):
        return {"e1": car(0.0, 0.0), "p1": car(0.2, 3.2)}

    assert not pa.operational_capture(trace(3.0, adjacent), "e1").captured


def test_proximity_rules_differ_by_the_distance_they_use():
    def passing(t):
        return {
            "e1": car(-30.0 + 12.0 * t, 0.0, speed=12.0),
            "p1": car(30.0 - 12.0 * t, 3.2, heading=math.pi, speed=12.0),
        }

    frames = trace(5.0, passing)
    assert pa.proximity(frames, "e1", pa.ProximityRule(5.0, "body")).reached
    assert pa.proximity(frames, "e1", pa.ProximityRule(5.0, "centre")).reached
    assert not pa.operational_capture(frames, "e1").captured


def test_an_unknown_distance_is_refused():
    with pytest.raises(ValueError, match="unknown distance kind"):
        pa.ProximityRule(5.0, "bumper")


def test_irregular_traces_are_refused_not_scored():
    frames = trace(1.0, stopped_in_file)
    del frames[4]
    with pytest.raises(pa.TraceError):
        pa.operational_capture(frames, "e1")


@pytest.mark.parametrize(
    ("name", "captured", "body_5m", "front_5m"),
    [
        ("blocked_stop", True, True, False),
        ("passing_cars", False, True, True),
        ("follower_behind", False, True, False),
    ],
)
def test_the_three_example_traces(examples, name, captured, body_5m, front_5m):
    row = pa.score_trace(pa.load_trace(os.path.join(examples, f"{name}.jsonl")), "e1")
    assert (row["oc"], row["body_5m"], row["front_5m"]) == (captured, body_5m, front_5m)
