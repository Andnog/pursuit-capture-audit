"""Schemas and semantic invariants reject missing or invalid critical fields.

This module is the direct check of the W2 acceptance criterion. It is an addition to the
module names listed in the master plan's directory tree; the tree is a required minimum,
not a prohibition, and the criterion it tests belongs to no other named module.
"""

from __future__ import annotations

import copy
import unittest

from _w2_support import requires_contracts  # noqa: E402


def valid_observation() -> dict:
    return {
        "contract_version": "task_contract_v1",
        "simulation_time_s": 3.0,
        "decision_index": 3,
        "topology_version": "t1",
        "vehicles": [
            {
                "vehicle_id": "p1",
                "vehicle_class": "pursuer",
                "position_xy_m": [0.0, 0.0],
                "speed_mps": 3.0,
                "heading_rad": 0.0,
                "lane_id": "l1",
                "lane_position_m": 10.0,
                "body_length_m": 5.0,
                "body_width_m": 1.8,
            },
            {
                "vehicle_id": "e1",
                "vehicle_class": "evader",
                "position_xy_m": [20.0, 0.0],
                "speed_mps": 3.0,
                "heading_rad": 0.0,
                "lane_id": "l1",
                "lane_position_m": 30.0,
                "body_length_m": 5.0,
                "body_width_m": 1.8,
            },
        ],
        "signals": [],
    }


def valid_result() -> dict:
    return {
        "contract_version": "task_contract_v1",
        "case_id": "c1",
        "arm": "J1",
        "split": "TRAINING",
        "city": "cityA",
        "scenario_id": "s1",
        "seeds": {"environment": 1, "training": None, "audit": None},
        "input_hashes": {"config": "0" * 64},
        "status": "COMPLETE",
        "endpoint_cause": "NO_CAPTURE_HORIZON_REACHED",
        "Y": 0,
        "Z": 0,
        "endpoint_time_s": 300.0,
        "physical_validity": "PASS",
        "safety_failures": 0,
        "guard_interventions": 0,
        "commitment_switches": 0,
        "audit_coverage": 0.0,
        "assistance_label": None,
        "reasons": [],
        "cost": {"wall_seconds": 1.0, "cpu_seconds": 1.0},
        "evidence_paths": ["experiments/x/results.jsonl"],
    }


@requires_contracts
class TestSchemasRejectMissingCriticalFields(unittest.TestCase):
    def test_baselines_are_valid(self):
        from joint_interception.domain.contracts import (
            validate_episode_result,
            validate_observation,
        )

        validate_observation(valid_observation())
        validate_episode_result(valid_result())

    def test_every_required_observation_field_is_enforced(self):
        from joint_interception.domain.contracts import ContractViolation, validate

        base = valid_observation()
        for field in list(base):
            record = copy.deepcopy(base)
            del record[field]
            with self.subTest(missing=field), self.assertRaises(ContractViolation):
                validate("public_observation", record)

    def test_every_required_vehicle_field_is_enforced(self):
        from joint_interception.domain.contracts import ContractViolation, validate

        base = valid_observation()
        for field in list(base["vehicles"][0]):
            record = copy.deepcopy(base)
            del record["vehicles"][0][field]
            with self.subTest(missing=field), self.assertRaises(ContractViolation):
                validate("public_observation", record)

    def test_every_required_result_field_is_enforced(self):
        from joint_interception.domain.contracts import ContractViolation, validate

        base = valid_result()
        for field in list(base):
            record = copy.deepcopy(base)
            del record[field]
            with self.subTest(missing=field), self.assertRaises(ContractViolation):
                validate("episode_result", record)

    def test_unknown_extra_key_is_rejected_not_ignored(self):
        from joint_interception.domain.contracts import ContractViolation, validate

        record = valid_observation()
        record["evader_route"] = ["edge1", "edge2"]
        with self.assertRaises(ContractViolation):
            validate("public_observation", record)

    def test_out_of_range_values_are_rejected(self):
        from joint_interception.domain.contracts import ContractViolation, validate

        cases = [
            ("simulation_time_s", 301.0),
            ("decision_index", -1),
        ]
        for field, bad in cases:
            record = valid_observation()
            record[field] = bad
            with self.subTest(field=field), self.assertRaises(ContractViolation):
                validate("public_observation", record)
        record = valid_observation()
        record["vehicles"][0]["speed_mps"] = -1.0
        with self.assertRaises(ContractViolation):
            validate("public_observation", record)

    def test_wrong_enum_is_rejected(self):
        from joint_interception.domain.contracts import ContractViolation, validate

        record = valid_observation()
        record["vehicles"][0]["vehicle_class"] = "drone"
        with self.assertRaises(ContractViolation):
            validate("public_observation", record)

    def test_all_problems_reported_not_only_the_first(self):
        from joint_interception.domain.contracts import schema_problems

        record = valid_observation()
        del record["topology_version"]
        record["decision_index"] = -5
        self.assertGreaterEqual(len(schema_problems("public_observation", record)), 2)


@requires_contracts
class TestSemanticInvariants(unittest.TestCase):
    """Records that are structurally valid but scientifically wrong must be refused."""

    def _expect_problem(self, mutate, fragment):
        from joint_interception.domain.contracts import ContractViolation, validate_episode_result

        record = valid_result()
        mutate(record)
        with self.assertRaises(ContractViolation) as caught:
            validate_episode_result(record)
        self.assertIn(fragment, str(caught.exception))

    def test_assisted_capture_requires_capture(self):
        def mutate(r):
            r["Z"] = 1

        self._expect_problem(mutate, "Z=1 requires Y=1")

    def test_known_noncapture_requires_Z_zero(self):
        def mutate(r):
            r["Z"] = "UNKNOWN"

        self._expect_problem(mutate, "Y=0 requires Z=0")

    def test_capture_with_unresolved_audit_cannot_be_Z_one(self):
        """The single most load-bearing invariant: it keeps the primary endpoint honest."""

        def mutate(r):
            r.update(
                Y=1,
                Z=1,
                endpoint_cause="CAPTURE_MOVING_CIRCULATION",
                endpoint_time_s=120.0,
                audit_coverage=0.5,
            )

        self._expect_problem(mutate, "audit_coverage=1.0")

    def test_capture_with_full_coverage_is_accepted(self):
        from joint_interception.domain.contracts import validate_episode_result

        record = valid_result()
        record.update(
            Y=1,
            Z=1,
            endpoint_cause="CAPTURE_MOVING_CIRCULATION",
            endpoint_time_s=120.0,
            audit_coverage=1.0,
            assistance_label="POSITIVE_ACROSS_FAMILY",
        )
        validate_episode_result(record)

    def test_safety_failure_cannot_be_a_capture(self):
        def mutate(r):
            r.update(Y=1, Z="UNKNOWN", endpoint_cause="SAFETY_FAILURE", endpoint_time_s=10.0)

        self._expect_problem(mutate, "SAFETY_FAILURE cannot coincide with Y=1")

    def test_failed_physical_validity_cannot_be_a_capture(self):
        def mutate(r):
            r.update(
                Y=1,
                Z="UNKNOWN",
                endpoint_cause="CAPTURE_MOVING_CIRCULATION",
                endpoint_time_s=10.0,
                physical_validity="FAIL",
                audit_coverage=1.0,
            )

        self._expect_problem(mutate, "physical_validity=FAIL")

    def test_incomplete_trace_requires_unknown_outcome(self):
        def mutate(r):
            r.update(Y=0, Z=0, endpoint_cause="INTEGRITY_FAILURE_INCOMPLETE_TRACE")

        self._expect_problem(mutate, "requires Y=UNKNOWN")

    def test_not_executed_keeps_case_but_carries_no_outcome(self):
        def mutate(r):
            r.update(status="NOT_EXECUTED")

        self._expect_problem(mutate, "requires Y=UNKNOWN and Z=UNKNOWN")

    def test_capture_beyond_horizon_is_rejected_by_the_schema(self):
        """Defence in depth: the schema bound catches this before the invariant layer."""
        from joint_interception.domain.contracts import ContractViolation, validate_episode_result

        record = valid_result()
        record.update(
            Y=1,
            Z="UNKNOWN",
            endpoint_cause="CAPTURE_MOVING_CIRCULATION",
            endpoint_time_s=301.0,
            audit_coverage=0.0,
        )
        with self.assertRaises(ContractViolation) as caught:
            validate_episode_result(record)
        self.assertEqual(caught.exception.layer, "schema:episode_result")

    def test_horizon_invariant_is_reachable_on_its_own(self):
        """The invariant must also hold independently, so it still guards a relaxed schema."""
        from joint_interception.domain.contracts import episode_result_invariants

        record = valid_result()
        record.update(
            Y=1,
            Z="UNKNOWN",
            endpoint_cause="CAPTURE_MOVING_CIRCULATION",
            endpoint_time_s=301.0,
            audit_coverage=0.0,
        )
        self.assertTrue(any("exceeds horizon" in p for p in episode_result_invariants(record)))

    def test_positive_assistance_label_requires_full_coverage(self):
        def mutate(r):
            r.update(assistance_label="POSITIVE_ACROSS_FAMILY", audit_coverage=0.5)

        self._expect_problem(mutate, "POSITIVE_ACROSS_FAMILY requires audit_coverage=1.0")


@requires_contracts
class TestObservationAndActionBuilders(unittest.TestCase):
    def test_simulation_time_is_derived_not_supplied(self):
        from joint_interception.domain.observations import (
            VehicleObservation,
            build_public_observation,
        )

        record = build_public_observation(
            7,
            [VehicleObservation("p1", "pursuer", (0.0, 0.0), 1.0, 0.0, "l1", 1.0, 5.0, 1.8)],
        )
        self.assertEqual(record["simulation_time_s"], 7.0)

    def test_desynchronised_clock_is_rejected(self):
        from joint_interception.domain.contracts import ContractViolation, validate_observation

        record = valid_observation()
        record["simulation_time_s"] = 99.0
        with self.assertRaises(ContractViolation) as caught:
            validate_observation(record)
        self.assertIn("disagrees with decision_index", str(caught.exception))

    def test_duplicate_vehicle_id_is_rejected(self):
        from joint_interception.domain.contracts import ContractViolation, validate_observation

        record = valid_observation()
        record["vehicles"][1]["vehicle_id"] = "p1"
        with self.assertRaises(ContractViolation):
            validate_observation(record)

    def test_prohibited_key_named_explicitly_by_the_invariant_layer(self):
        """The prose boundary list must never be pattern-matched; the key list is."""
        from joint_interception.domain.contracts import observation_invariants

        record = valid_observation()
        record["vehicles"][0]["internal_memory"] = {"x": 1}
        problems = observation_invariants(record)
        self.assertTrue(any("internal_memory" in p for p in problems), problems)
        # 'evader' appears legitimately as a vehicle_class and must NOT be flagged.
        self.assertFalse(any("evader" in p for p in observation_invariants(valid_observation())))

    def test_unknown_action_is_refused(self):
        from joint_interception.domain.actions import build_action

        with self.assertRaises(KeyError):
            build_action("p1", "TELEPORT", True)

    def test_invalid_action_must_carry_a_reason(self):
        from joint_interception.domain.actions import build_action

        with self.assertRaises(ValueError):
            build_action("p1", "CRUISE", False)
        build_action("p1", "CRUISE", False, invalid_reason="lane_blocked")

    def test_unexpected_parameter_is_refused(self):
        from joint_interception.domain.actions import build_action

        with self.assertRaises(ValueError):
            build_action("p1", "HOLD_LANE", True, {"target_speed_fraction": 0.5})

    def test_fallback_exists_when_nothing_is_valid(self):
        from joint_interception.domain.actions import build_action, choose_with_fallback

        actions = [
            build_action("p1", "HOLD_LANE", True),
            build_action("p1", "CRUISE", False, {"target_speed_fraction": 0.5}, "blocked"),
        ]
        chosen, label = choose_with_fallback(actions, None)
        self.assertEqual(label, "FALLBACK")
        self.assertEqual(chosen["action_id"], "HOLD_LANE")

    def test_hold_lane_is_declared_always_valid(self):
        from joint_interception.domain.actions import action_menu

        self.assertTrue(action_menu()["HOLD_LANE"].always_valid)


if __name__ == "__main__":
    unittest.main()
