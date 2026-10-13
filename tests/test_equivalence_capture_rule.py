"""The capture rule of the library against the judge that scored the published results.

The frozen judge (`as_run/src/joint_interception/evaluation`) is the reference. The library's
rule is a separate implementation. They are compared on random situations concentrated near every
threshold, and on random traces with several pursuers, interruptions and missing vehicles.
"""

import math
import random
from dataclasses import replace

import pytest

import pursuit_audit as pa
from pursuit_audit.endpoints.specification import PairState

reference_judge = pytest.importorskip("joint_interception.evaluation.capture_judge")
reference_time = pytest.importorskip("joint_interception.evaluation.capture_time")
reference_contracts = pytest.importorskip("joint_interception.domain.contracts")

STEP = 0.1
PARAMS = pa.CaptureParameters()
REFERENCE_PARAMS = reference_contracts.CaptureParameters(
    contact_gap_min_m=PARAMS.gap_min_m,
    contact_gap_max_m=PARAMS.gap_max_m,
    capture_speed_max_mps=PARAMS.speed_max_mps,
    relative_speed_max_mps=PARAMS.relative_speed_max_mps,
    orientation_tolerance_rad=PARAMS.heading_tolerance_rad,
    dwell_time_s=PARAMS.dwell_s,
    geometry_tolerance_m=PARAMS.overlap_tolerance_m,
    frozen=True,
    alignment_lateral_max_m=PARAMS.lateral_max_m,
)
REASONS = {
    "invalid_frame_values": "invalid_values",
    "body_overlap_or_within_tolerance": "bodies_overlap",
    "separation_below_contact_gap_min": "gap_below_minimum",
    "separation_above_contact_gap_max": "gap_above_maximum",
    "evader_speed_above_capture_speed_max": "evader_moving",
    "pursuer_speed_above_capture_speed_max": "pursuer_moving",
    "relative_speed_above_max": "relative_speed",
    "relative_orientation_outside_tolerance": "headings_differ",
    "evader_not_behind_pursuer": "evader_not_behind_pursuer",
    "lateral_offset_above_alignment_max": "lateral_offset",
    "all_conditions_hold": None,
}


def to_reference(vehicle_id: str, body: pa.Body):
    return reference_judge.VehicleFrame(
        vehicle_id, body.x, body.y, body.heading_rad, body.speed_mps, body.length_m, body.width_m
    )


def near_contact_pair(rng: random.Random) -> tuple[pa.Body, pa.Body]:
    """A pursuer and an evader close to the capture configuration, with every value perturbed."""
    heading = rng.uniform(-math.pi, math.pi)
    gap = rng.choice([rng.uniform(-0.5, 3.0), rng.uniform(0.25, 0.35), rng.uniform(1.95, 2.05)])
    lateral = rng.choice([rng.uniform(-2.0, 2.0), rng.uniform(0.95, 1.05), 0.0])
    along = 5.0 + gap
    if rng.random() < 0.08:
        along = -along
    evader = pa.Body(
        rng.uniform(-50, 50), rng.uniform(-50, 50), heading, max(0.0, rng.gauss(0.6, 0.6)), 5.0, 1.8
    )
    twist = rng.choice([0.0, rng.uniform(-0.4, 0.4), rng.uniform(0.25, 0.27)])
    pursuer = pa.Body(
        evader.x + along * math.cos(heading) - lateral * math.sin(heading),
        evader.y + along * math.sin(heading) + lateral * math.cos(heading),
        heading + twist,
        max(0.0, rng.gauss(0.6, 0.6)),
        5.0,
        1.8,
    )
    return pursuer, evader


def test_the_default_parameters_are_the_registered_ones(snapshot):
    registered = reference_contracts.CaptureParameters.from_domain()
    assert registered.frozen
    assert (registered.contact_gap_min_m, registered.contact_gap_max_m) == (
        PARAMS.gap_min_m,
        PARAMS.gap_max_m,
    )
    assert registered.capture_speed_max_mps == PARAMS.speed_max_mps
    assert registered.relative_speed_max_mps == PARAMS.relative_speed_max_mps
    assert registered.orientation_tolerance_rad == PARAMS.heading_tolerance_rad
    assert registered.dwell_time_s == PARAMS.dwell_s
    assert registered.geometry_tolerance_m == PARAMS.overlap_tolerance_m
    assert registered.alignment_lateral_max_m == PARAMS.lateral_max_m


def test_the_instantaneous_conditions_agree_on_random_situations():
    rng = random.Random(20261013)
    rule = pa.contact_specification(PARAMS)
    outcomes = {}
    for _ in range(20_000):
        pursuer, evader = near_contact_pair(rng)
        expected_holds, expected_reason = reference_judge._conditions_hold(
            to_reference("p1", pursuer), to_reference("e1", evader), REFERENCE_PARAMS
        )
        failure = rule.first_failure(PairState.measure(pursuer, evader))
        assert (failure is None) == expected_holds
        assert failure == REASONS[expected_reason]
        outcomes[failure] = outcomes.get(failure, 0) + 1
    # The comparison is only worth something if every branch of the rule was exercised. One
    # cannot be: with the registered thresholds, two speeds of at most 1 m/s cannot differ by more
    # than 1 m/s. That branch is exercised below, with a stricter relative bound.
    assert set(outcomes) == set(REASONS.values()) - {"invalid_values", "relative_speed"}
    assert outcomes[None] > 500


def test_the_relative_speed_condition_agrees_when_it_can_fail():
    strict = replace(PARAMS, relative_speed_max_mps=0.3)
    reference = replace(REFERENCE_PARAMS, relative_speed_max_mps=0.3)
    rule = pa.contact_specification(strict)
    rng = random.Random(7)
    failures = 0
    for _ in range(5_000):
        pursuer, evader = near_contact_pair(rng)
        expected_holds, expected_reason = reference_judge._conditions_hold(
            to_reference("p1", pursuer), to_reference("e1", evader), reference
        )
        failure = rule.first_failure(PairState.measure(pursuer, evader))
        assert failure == REASONS[expected_reason]
        failures += failure == "relative_speed"
    assert failures > 50


def random_trace(rng: random.Random, pursuers: int, frames: int):
    """A trace in which each pursuer holds the contact in random stretches, or is absent."""
    evader = pa.Body(0.0, 0.0, 0.0, 0.2, 5.0, 1.8)
    holding = pa.Body(6.0, 0.0, 0.0, 0.1, 5.0, 1.8)
    chasing = pa.Body(6.0, 0.0, 0.0, 4.0, 5.0, 1.8)
    states = {f"p{i + 1}": rng.choice(["hold", "chase", "absent"]) for i in range(pursuers)}
    clean, reference = [], []
    for index in range(frames):
        time_s = round(index * STEP, 6)
        vehicles = {"e1": evader}
        for pursuer_id in sorted(states):
            if rng.random() < 0.06:
                states[pursuer_id] = rng.choice(["hold", "hold", "chase", "absent"])
            behaviour = states[pursuer_id]
            if behaviour != "absent":
                vehicles[pursuer_id] = holding if behaviour == "hold" else chasing
        clean.append(pa.Frame(time_s, vehicles))
        reference.append(
            reference_judge.TraceFrame(time_s, {v: to_reference(v, b) for v, b in vehicles.items()})
        )
    return clean, reference


def test_the_capture_instant_agrees_on_random_traces():
    rng = random.Random(137)
    captured = 0
    for _ in range(400):
        clean, reference = random_trace(rng, pursuers=rng.randint(1, 4), frames=rng.randint(15, 90))
        expected = reference_time.earliest_capture(reference, "e1", REFERENCE_PARAMS, STEP)
        through_judge = reference_time.judge_earliest_capture(
            reference, "e1", REFERENCE_PARAMS, STEP
        )
        result = pa.operational_capture(clean, "e1", step_s=STEP)
        assert result.captured == (expected is not None) == (through_judge is not None)
        if expected is not None:
            captured += 1
            assert result.capture_time_s == pytest.approx(expected.time_s)
            assert result.witness_start_s == pytest.approx(expected.run_start_s)
            assert result.pursuer == expected.pursuer_id
    assert 80 < captured < 320
