"""Canonical interval unions, nonconvexity and the approximation-direction rules."""

from __future__ import annotations

import random
import unittest

from _support import (  # noqa: E402
    TOLERANCE,
    build_opportunity,
    intervals_equal,
    load_config,
    load_fixture,
)
from joint_interception.opportunities.compatibility import assess_temporal  # noqa: E402
from joint_interception.opportunities.reachability import (  # noqa: E402
    ArrivalSet,
    all_over,
    all_under,
    canonicalize,
    convex_hull,
    intersect,
    intersect_all,
    max_contiguous,
    total_width,
)
from joint_interception.opportunities.types import Direction, Verdict  # noqa: E402


class TestCanonicalForm(unittest.TestCase):
    def test_merges_overlapping_and_touching(self):
        self.assertEqual(canonicalize([(1, 3), (2, 5)]), ((1.0, 5.0),))
        self.assertEqual(canonicalize([(1, 2), (2, 4)]), ((1.0, 4.0),))

    def test_drops_empty_intervals(self):
        self.assertEqual(canonicalize([(5, 4)]), ())

    def test_sorts_and_keeps_disjoint(self):
        self.assertEqual(canonicalize([(10, 12), (1, 3)]), ((1.0, 3.0), (10.0, 12.0)))

    def test_idempotent_and_total_on_random_input(self):
        rng = random.Random(20260920)
        for _ in range(500):
            raw = []
            for _ in range(rng.randint(0, 6)):
                low = rng.uniform(-50, 50)
                raw.append((low, low + rng.uniform(-5, 10)))
            once = canonicalize(raw)
            twice = canonicalize(once)
            self.assertEqual(once, twice)
            for left, right in zip(once, once[1:], strict=False):
                self.assertLess(left[1], right[0])
            for low, high in once:
                self.assertLessEqual(low, high + TOLERANCE)


class TestIntersection(unittest.TestCase):
    def test_disjoint_unions_intersect_exactly(self):
        left = canonicalize([(5, 12), (20, 25)])
        right = canonicalize([(10, 22)])
        self.assertEqual(intersect(left, right), ((10.0, 12.0), (20.0, 22.0)))

    def test_empty_collection_yields_empty_not_universal(self):
        self.assertEqual(intersect_all([]), ())

    def test_width_and_max_contiguous_differ(self):
        union = canonicalize([(10, 12), (20, 22)])
        self.assertAlmostEqual(total_width(union), 4.0)
        self.assertAlmostEqual(max_contiguous(union), 2.0)


class TestNonconvexity(unittest.TestCase):
    """Case F3: the convex hull declares unreachable times reachable."""

    def setUp(self):
        self.config = load_config()
        self.expected = load_fixture()["representation_expectations"]["F3"]

    def test_exact_intersection_is_empty(self):
        opportunity, _ = build_opportunity(self.config, "F3")
        self.assertEqual(opportunity.joint_window, ())
        self.assertAlmostEqual(opportunity.max_contiguous, self.expected["max_contiguous"])

    def test_hull_relaxation_would_report_a_window(self):
        spec = next(c for c in self.config["representation_cases"] if c["case_id"] == "F3")
        p1 = canonicalize(spec["arrival_sets"]["p1"]["intervals"])
        p2 = canonicalize(spec["arrival_sets"]["p2"]["intervals"])
        hull_window = intersect(convex_hull(p1), p2)
        self.assertTrue(intervals_equal(hull_window, self.expected["hull_would_give_window"]))
        self.assertAlmostEqual(
            max_contiguous(hull_window), self.expected["hull_would_give_max_contiguous"]
        )
        self.assertNotEqual(hull_window, intersect(p1, p2))


class TestApproximationDirectionRules(unittest.TestCase):
    """Rules A and B are not symmetric; a single model cannot serve both."""

    def test_predicates(self):
        self.assertTrue(all_under([Direction.UNDER, Direction.UNDER]))
        self.assertFalse(all_under([Direction.UNDER, Direction.OVER]))
        self.assertTrue(all_over([Direction.OVER]))
        self.assertFalse(all_under([]))
        self.assertFalse(all_over([]))

    def test_over_sets_may_reject_under_sets_may_not(self):
        fixture = load_fixture()["representation_expectations"]["F3"]
        config = load_config()
        over_opportunity, _ = build_opportunity(config, "F3")
        self.assertEqual(over_opportunity.temporal_verdict.value, fixture["temporal_verdict"])

        under_opportunity, _ = build_opportunity(config, "F3", direction_override="UNDER")
        self.assertEqual(
            under_opportunity.temporal_verdict.value,
            fixture["under_variant"]["temporal_verdict"],
        )
        self.assertEqual(under_opportunity.verdict.value, fixture["under_variant"]["joint_verdict"])

    def test_under_sets_required_to_certify_existence(self):
        sets = [
            ArrivalSet.build("p1", [(0, 10)], Direction.OVER),
            ArrivalSet.build("p2", [(0, 10)], Direction.OVER),
        ]
        verdict, _, _, _ = assess_temporal(sets, dwell_required_s=1.0)
        self.assertEqual(verdict, Verdict.UNKNOWN)

    def test_prediction_supports_neither_verdict(self):
        overlapping = [
            ArrivalSet.build("p1", [(0, 10)], Direction.PREDICTION),
            ArrivalSet.build("p2", [(0, 10)], Direction.PREDICTION),
        ]
        self.assertEqual(assess_temporal(overlapping, 1.0)[0], Verdict.UNKNOWN)
        disjoint = [
            ArrivalSet.build("p1", [(0, 1)], Direction.PREDICTION),
            ArrivalSet.build("p2", [(5, 6)], Direction.PREDICTION),
        ]
        self.assertEqual(assess_temporal(disjoint, 1.0)[0], Verdict.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
