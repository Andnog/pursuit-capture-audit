"""Joint compatibility against the frozen fixture, and the unsoundness of pairwise checks."""

from __future__ import annotations

import unittest

from _support import build_opportunity, intervals_equal, load_config, load_fixture  # noqa: E402
from joint_interception.opportunities.compatibility import (  # noqa: E402
    lane_capacity_required_m,
)
from joint_interception.opportunities.types import Verdict, verdict_and, verdict_or  # noqa: E402


class TestVerdictAlgebra(unittest.TestCase):
    def test_rejection_dominates_ignorance(self):
        self.assertEqual(
            verdict_and([Verdict.UNKNOWN, Verdict.REJECTED, Verdict.SUPPORTED]),
            Verdict.REJECTED,
        )

    def test_unknown_never_becomes_supported(self):
        for extra in (Verdict.SUPPORTED, Verdict.UNKNOWN):
            self.assertEqual(verdict_and([Verdict.UNKNOWN, extra]), Verdict.UNKNOWN)

    def test_empty_conjunction_is_unknown_not_supported(self):
        self.assertEqual(verdict_and([]), Verdict.UNKNOWN)
        self.assertEqual(verdict_or([]), Verdict.UNKNOWN)

    def test_exhaustive_no_unknown_yields_supported(self):
        values = list(Verdict)
        for a in values:
            for b in values:
                for c in values:
                    result = verdict_and([a, b, c])
                    if result is Verdict.SUPPORTED:
                        self.assertTrue(all(v is Verdict.SUPPORTED for v in (a, b, c)))


class TestLaneCapacity(unittest.TestCase):
    def test_arithmetic_matches_hand_derivation(self):
        self.assertAlmostEqual(lane_capacity_required_m(1, 5.0, 2.5), 5.0)
        self.assertAlmostEqual(lane_capacity_required_m(2, 5.0, 2.5), 12.5)
        self.assertAlmostEqual(lane_capacity_required_m(3, 5.0, 2.5), 20.0)
        self.assertAlmostEqual(lane_capacity_required_m(0, 5.0, 2.5), 0.0)


class TestRepresentationCases(unittest.TestCase):
    def setUp(self):
        self.config = load_config()
        self.fixture = load_fixture()["representation_expectations"]

    def _check(self, case_id, keys, direction_override=None, expected=None):
        expected = expected or self.fixture[case_id]
        opportunity, pairwise = build_opportunity(
            self.config, case_id, direction_override=direction_override
        )
        for key in keys:
            with self.subTest(case=case_id, field=key):
                if key == "joint_window":
                    self.assertTrue(
                        intervals_equal(opportunity.joint_window, expected[key]),
                        f"{opportunity.joint_window} != {expected[key]}",
                    )
                elif key == "joint_verdict":
                    self.assertEqual(opportunity.verdict.value, expected[key])
                elif key == "pairwise_verdict":
                    self.assertEqual(pairwise.value, expected[key])
                elif key == "pairwise_joint_discrepancy":
                    self.assertEqual(pairwise != opportunity.verdict, expected[key])
                elif key in ("max_contiguous", "margin", "coverage"):
                    self.assertAlmostEqual(getattr(opportunity, key), expected[key])
                else:
                    self.assertEqual(getattr(opportunity, key).value, expected[key])
        return opportunity, pairwise

    def test_F1_pairwise_compatible_jointly_infeasible(self):
        opportunity, pairwise = self._check(
            "F1",
            [
                "joint_window",
                "max_contiguous",
                "temporal_verdict",
                "occupancy_verdict",
                "movement_verdict",
                "joint_verdict",
                "pairwise_verdict",
                "pairwise_joint_discrepancy",
            ],
        )
        # Claim P1: the pairwise relaxation is unsound as a certificate.
        self.assertEqual(opportunity.verdict, Verdict.REJECTED)
        self.assertEqual(pairwise, Verdict.SUPPORTED)

    def test_F1_variant_rejection_dominates_unknown_temporal(self):
        expected = self.fixture["F1"]["variant_unknown_temporal"]
        self._check(
            "F1",
            ["temporal_verdict", "occupancy_verdict", "joint_verdict"],
            direction_override="PREDICTION",
            expected=expected,
        )

    def test_F2_genuinely_compatible(self):
        self._check(
            "F2",
            [
                "joint_window",
                "max_contiguous",
                "margin",
                "temporal_verdict",
                "occupancy_verdict",
                "movement_verdict",
                "joint_verdict",
                "pairwise_verdict",
                "pairwise_joint_discrepancy",
            ],
        )

    def test_F2_dwell_uses_max_contiguous_not_total_width(self):
        """Raising the dwell to 3.0 must remove support, although total width is 4.0."""
        from joint_interception.opportunities.compatibility import assess_temporal
        from joint_interception.opportunities.reachability import ArrivalSet, total_width
        from joint_interception.opportunities.types import Direction

        spec = next(c for c in self.config["representation_cases"] if c["case_id"] == "F2")
        sets = [
            ArrivalSet.build(name, data["intervals"], Direction(data["direction"]))
            for name, data in spec["arrival_sets"].items()
        ]
        verdict_ok, window, longest, _ = assess_temporal(sets, 1.5)
        self.assertEqual(verdict_ok, Verdict.SUPPORTED)
        self.assertAlmostEqual(total_width(window), 4.0)
        self.assertAlmostEqual(longest, 2.0)
        verdict_strict, _, _, _ = assess_temporal(sets, 3.0)
        self.assertNotEqual(verdict_strict, Verdict.SUPPORTED)

    def test_F3_nonconvex_rejected(self):
        self._check("F3", ["joint_window", "max_contiguous", "temporal_verdict", "joint_verdict"])

    def test_F5_one_step_safety_does_not_certify_sequence(self):
        opportunity, _ = self._check(
            "F5",
            ["temporal_verdict", "occupancy_verdict", "movement_verdict", "joint_verdict"],
        )
        expected = self.fixture["F5"]
        self.assertFalse(expected["one_step_safety_certifies_sequence"])
        self.assertFalse(expected["execution_permitted"])
        # Unresolved admission must never become permission to execute.
        self.assertNotEqual(opportunity.verdict, Verdict.SUPPORTED)

    def test_every_verdict_carries_a_reason(self):
        for case_id in ("F1", "F2", "F3", "F4", "F5"):
            opportunity, _ = build_opportunity(self.config, case_id)
            with self.subTest(case=case_id):
                self.assertTrue(opportunity.reasons)
                self.assertTrue(all(r.code for r in opportunity.reasons))


class TestEvaderBranchCoverage(unittest.TestCase):
    """Case F4: an unexamined branch yields UNKNOWN and blocks an all-branch claim."""

    def setUp(self):
        self.config = load_config()
        self.expected = load_fixture()["representation_expectations"]["F4"]

    def test_examined_branch_supported_but_all_branch_claim_unknown(self):
        spec = next(c for c in self.config["representation_cases"] if c["case_id"] == "F4")
        opportunity, _ = build_opportunity(self.config, "F4")
        self.assertEqual(opportunity.verdict.value, self.expected["branch_verdicts"]["b1"])
        self.assertTrue(intervals_equal(opportunity.joint_window, self.expected["b1_joint_window"]))

        declared = spec["evader_branches"]
        examined = spec["examined_branches"]
        coverage = len(examined) / len(declared)
        self.assertAlmostEqual(coverage, self.expected["coverage"])

        branch_verdicts = [
            opportunity.verdict if b in examined else Verdict.UNKNOWN for b in declared
        ]
        self.assertEqual(verdict_and(branch_verdicts).value, self.expected["all_branch_verdict"])
        self.assertEqual(coverage < 1.0, not self.expected["all_branch_claim_permitted"])


if __name__ == "__main__":
    unittest.main()
