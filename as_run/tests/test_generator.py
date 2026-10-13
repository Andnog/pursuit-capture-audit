"""Candidate generation: pruning must be accounted, and truncation must be visible.

The historical O26 diagnostic recorded 6548 candidate occurrences of which none passed the
selector's screen, and could not distinguish an absent opportunity from a rejected one.
That is the defect these tests exist to prevent.
"""

from __future__ import annotations

import unittest

from _w2_support import requires_contracts  # noqa: E402


def build_inputs(lane_length_m: float = 30.0, participants=("p1", "p2", "p3")):
    from joint_interception.opportunities.reachability import ArrivalSet
    from joint_interception.opportunities.types import Direction

    corridors = {"c1": {"participants": list(participants)}}
    arrival_sets = {
        "c1": {p: ArrivalSet.build(p, [(10.0, 20.0)], Direction.UNDER) for p in participants}
    }
    stations = {"c1": dict.fromkeys(participants, "L1")}
    return corridors, arrival_sets, stations, {"L1": lane_length_m}


@requires_contracts
class TestGenerationAccounting(unittest.TestCase):
    """R7: enumerated must equal kept plus everything removed."""

    def _generate(self, **kwargs):
        from joint_interception.opportunities.generator import build_candidates

        corridors, arrival_sets, stations, lanes = build_inputs(
            kwargs.pop("lane_length_m", 30.0), kwargs.pop("participants", ("p1", "p2", "p3"))
        )
        return build_candidates(
            corridors=corridors,
            arrival_sets=arrival_sets,
            stations=stations,
            lane_lengths=lanes,
            dwell_required_s=3.0,
            body_length_m=5.0,
            min_gap_m=2.5,
            **kwargs,
        )

    def test_account_reconciles(self):
        _, account = self._generate()
        self.assertTrue(account.reconciles(), account.as_record())

    def test_enumeration_count_matches_the_combinatorics(self):
        """Three participants, subset sizes 2 and 3: C(3,2) + C(3,3) = 3 + 1 = 4."""
        _, account = self._generate()
        self.assertEqual(account.enumerated, 4)

    def test_rejected_candidates_are_counted_not_forgotten(self):
        """A 14 m lane fits two 5 m bodies at a 2.5 m gap but not three."""
        kept, account = self._generate(lane_length_m=14.0)
        self.assertEqual(account.pruned.get("rejected_by_compatibility"), 1)
        self.assertEqual(len(kept), 3)
        self.assertTrue(account.reconciles())
        self.assertTrue(
            any(k.startswith("rejected_by_compatibility:") for k in account.pruned_keys)
        )

    def test_truncation_is_recorded_and_deterministic(self):
        from joint_interception.opportunities.generator import GeneratorLimits

        kept, account = self._generate(limits=GeneratorLimits(max_candidates=2))
        self.assertEqual(len(kept), 2)
        self.assertEqual(account.truncated, 2)
        self.assertTrue(account.reconciles())
        again, _ = self._generate(limits=GeneratorLimits(max_candidates=2))
        self.assertEqual([o.opportunity_id for o in kept], [o.opportunity_id for o in again])

    def test_missing_arrival_set_is_pruned_with_its_own_reason(self):
        from joint_interception.opportunities.generator import build_candidates

        corridors, arrival_sets, stations, lanes = build_inputs()
        del arrival_sets["c1"]["p3"]
        kept, account = build_candidates(
            corridors=corridors,
            arrival_sets=arrival_sets,
            stations=stations,
            lane_lengths=lanes,
            dwell_required_s=3.0,
            body_length_m=5.0,
            min_gap_m=2.5,
        )
        self.assertEqual(account.pruned.get("no_arrival_set_for_participant"), 3)
        self.assertEqual(len(kept), 1)
        self.assertTrue(account.reconciles())

    def test_participant_cap_limits_subset_size(self):
        from joint_interception.opportunities.generator import GeneratorLimits

        _, account = self._generate(limits=GeneratorLimits(max_participants=2))
        self.assertEqual(account.enumerated, 3)


@requires_contracts
class TestPairwiseIsLabelledAsAnApproximation(unittest.TestCase):
    def test_pairwise_mode_records_that_it_is_not_a_certificate(self):
        from joint_interception.opportunities.generator import build_candidates

        corridors, arrival_sets, stations, lanes = build_inputs(lane_length_m=30.0)
        kept, _ = build_candidates(
            corridors=corridors,
            arrival_sets=arrival_sets,
            stations=stations,
            lane_lengths=lanes,
            dwell_required_s=3.0,
            body_length_m=5.0,
            min_gap_m=2.5,
            use_pairwise=True,
        )
        codes = [r.code for o in kept for r in o.reasons]
        self.assertIn("pairwise_approximation_used", codes)
        detail = next(
            r.detail for o in kept for r in o.reasons if r.code == "pairwise_approximation_used"
        )
        self.assertIn("NOT a team-feasibility certificate", detail)

    def test_joint_and_pairwise_disagree_on_the_three_body_lane(self):
        """Finite case F1, reached through the generator rather than directly."""
        from joint_interception.opportunities.generator import build_candidates

        corridors, arrival_sets, stations, lanes = build_inputs(lane_length_m=14.0)
        joint, joint_account = build_candidates(
            corridors=corridors,
            arrival_sets=arrival_sets,
            stations=stations,
            lane_lengths=lanes,
            dwell_required_s=3.0,
            body_length_m=5.0,
            min_gap_m=2.5,
        )
        triple = [o for o in joint if len(o.participants) == 3]
        self.assertEqual(triple, [], "the three-body candidate must be rejected")
        self.assertEqual(joint_account.pruned.get("rejected_by_compatibility"), 1)


@requires_contracts
class TestEvidenceRows(unittest.TestCase):
    """R8: rows are built in one place and validate against both layers."""

    def _hashes(self):
        from _support import ROOT
        from joint_interception.evidence.provenance import hash_inputs

        return hash_inputs(["configs/domain_v1.json"], root=ROOT)

    def test_valid_row_is_built(self):
        from joint_interception.evidence.records import build_episode_result

        row = build_episode_result(
            case_id="c1",
            arm="J1",
            split="TRAINING",
            city="cityA",
            scenario_id="s1",
            environment_seed=1,
            input_hashes=self._hashes(),
            status="COMPLETE",
            endpoint_cause="NO_CAPTURE_HORIZON_REACHED",
            y_outcome=0,
            z_outcome=0,
            physical_validity="PASS",
            audit_coverage=0.0,
            wall_seconds=1.0,
            cpu_seconds=1.0,
            evidence_paths=["experiments/x/results.jsonl"],
            endpoint_time_s=300.0,
        )
        self.assertEqual(row["Y"], 0)

    def test_inflated_endpoint_is_refused_at_construction(self):
        from joint_interception.domain.contracts import ContractViolation
        from joint_interception.evidence.records import build_episode_result

        with self.assertRaises(ContractViolation):
            build_episode_result(
                case_id="c1",
                arm="J1",
                split="TRAINING",
                city="cityA",
                scenario_id="s1",
                environment_seed=1,
                input_hashes=self._hashes(),
                status="COMPLETE",
                endpoint_cause="CAPTURE_MOVING_CIRCULATION",
                y_outcome=1,
                z_outcome=1,
                physical_validity="PASS",
                audit_coverage=0.5,
                wall_seconds=1.0,
                cpu_seconds=1.0,
                evidence_paths=["x"],
                endpoint_time_s=120.0,
            )

    def test_not_executed_row_stays_in_the_denominator(self):
        from joint_interception.evidence.records import (
            build_episode_result,
            build_not_executed_row,
            endpoint_bounds_over_rows,
        )

        hashes = self._hashes()
        executed = [
            build_episode_result(
                case_id=f"c{i}",
                arm="J1",
                split="TRAINING",
                city="cityA",
                scenario_id="s1",
                environment_seed=i,
                input_hashes=hashes,
                status="COMPLETE",
                endpoint_cause="NO_CAPTURE_HORIZON_REACHED",
                y_outcome=0,
                z_outcome=0,
                physical_validity="PASS",
                audit_coverage=0.0,
                wall_seconds=1.0,
                cpu_seconds=1.0,
                evidence_paths=["x"],
                endpoint_time_s=300.0,
            )
            for i in range(3)
        ]
        skipped = build_not_executed_row(
            "c9", "J1", "TRAINING", "cityA", "s1", 9, hashes, "dependency_gate", ["x"]
        )
        rows = [*executed, skipped]
        self.assertEqual(skipped["Y"], "UNKNOWN")
        self.assertEqual(endpoint_bounds_over_rows(rows), (0.0, 0.0))
        self.assertEqual(len(rows), 4)

    def test_unresolved_audit_widens_the_bounds(self):
        from joint_interception.evidence.records import (
            build_episode_result,
            endpoint_bounds_over_rows,
        )

        hashes = self._hashes()
        rows = [
            build_episode_result(
                case_id="c1",
                arm="J1",
                split="TRAINING",
                city="cityA",
                scenario_id="s1",
                environment_seed=1,
                input_hashes=hashes,
                status="COMPLETE",
                endpoint_cause="CAPTURE_MOVING_CIRCULATION",
                y_outcome=1,
                z_outcome="UNKNOWN",
                physical_validity="PASS",
                audit_coverage=0.0,
                wall_seconds=1.0,
                cpu_seconds=1.0,
                evidence_paths=["x"],
                endpoint_time_s=100.0,
            ),
            build_episode_result(
                case_id="c2",
                arm="J1",
                split="TRAINING",
                city="cityA",
                scenario_id="s1",
                environment_seed=2,
                input_hashes=hashes,
                status="COMPLETE",
                endpoint_cause="NO_CAPTURE_HORIZON_REACHED",
                y_outcome=0,
                z_outcome=0,
                physical_validity="PASS",
                audit_coverage=0.0,
                wall_seconds=1.0,
                cpu_seconds=1.0,
                evidence_paths=["x"],
                endpoint_time_s=300.0,
            ),
        ]
        self.assertEqual(endpoint_bounds_over_rows(rows), (0.0, 0.5))

    def test_missing_provenance_input_raises(self):
        from joint_interception.evidence.provenance import hash_inputs

        with self.assertRaises(FileNotFoundError):
            hash_inputs(["configs/does_not_exist.json"], root=".")


if __name__ == "__main__":
    unittest.main()
