"""Constructive arrival witnesses: the `UNDER` label must be earned, not asserted.

Every check verifies a produced profile by INTEGRATING it. None re-asserts the formula that
generated it. This is the W1 fixture discipline applied to code that generates its own
answers: a generator checked against its own arithmetic checks nothing.
"""

from __future__ import annotations

import unittest

from _w2_support import requires_contracts  # noqa: E402

LIMIT = 13.89
ACCEL = 2.6
DECEL = 4.5
HORIZON = 300.0
DISTANCE = 100.0
START_SPEED = 3.0


@requires_contracts
class TestC1EarliestArrival(unittest.TestCase):
    """C1: the earliest schedule arrives at exactly `t_min`."""

    def test_integrates_to_the_distance_at_the_reported_time(self):
        from joint_interception.opportunities.schedule import earliest_arrival

        time_s, profile = earliest_arrival(DISTANCE, START_SPEED, LIMIT, ACCEL)
        covered, _ = profile.integrate()
        self.assertAlmostEqual(covered, DISTANCE, places=9)
        self.assertAlmostEqual(profile.duration_s, time_s, places=9)

    def test_matches_the_closed_form_on_a_pure_acceleration_case(self):
        """From rest at 2 m/s^2 over 100 m with a high limit: t = sqrt(2d/a) = 10 s."""
        from joint_interception.opportunities.schedule import earliest_arrival

        time_s, profile = earliest_arrival(100.0, 0.0, 1000.0, 2.0)
        self.assertAlmostEqual(time_s, 10.0, places=9)
        self.assertAlmostEqual(profile.integrate()[0], 100.0, places=9)

    def test_matches_the_closed_form_when_the_limit_is_reached(self):
        """0 to 10 m/s at 2 m/s^2 takes 5 s over 25 m; the remaining 75 m at 10 m/s is 7.5 s."""
        from joint_interception.opportunities.schedule import earliest_arrival

        time_s, profile = earliest_arrival(100.0, 0.0, 10.0, 2.0)
        self.assertAlmostEqual(time_s, 12.5, places=9)
        self.assertAlmostEqual(profile.integrate()[0], 100.0, places=9)

    def test_no_earlier_arrival_exists(self):
        """Asking for any time before the earliest must be refused, not approximated."""
        from joint_interception.opportunities.schedule import arrival_at, earliest_arrival

        time_s, _ = earliest_arrival(DISTANCE, START_SPEED, LIMIT, ACCEL)
        for delta in (0.001, 0.1, 1.0, 5.0):
            with self.subTest(delta=delta):
                self.assertIsNone(
                    arrival_at(DISTANCE, START_SPEED, LIMIT, ACCEL, DECEL, time_s - delta)
                )


@requires_contracts
class TestC2IntervalFullness(unittest.TestCase):
    """C2: every time in the interval has a profile arriving at exactly that time.

    This is what makes the arrival set an interval rather than a pair of endpoints, and it
    is the property the `UNDER` label actually rests on.
    """

    SAMPLES = 240

    def test_dense_sample_of_the_whole_interval(self):
        from joint_interception.opportunities.schedule import arrival_at, earliest_arrival

        earliest, _ = earliest_arrival(DISTANCE, START_SPEED, LIMIT, ACCEL)
        latest = 120.0
        checked = 0
        for index in range(self.SAMPLES):
            t = earliest + (latest - earliest) * index / (self.SAMPLES - 1)
            profile = arrival_at(DISTANCE, START_SPEED, LIMIT, ACCEL, DECEL, t)
            self.assertIsNotNone(profile, f"no profile for t={t}")
            covered, _ = profile.integrate()
            self.assertAlmostEqual(covered, DISTANCE, places=6, msg=f"t={t}")
            self.assertAlmostEqual(profile.duration_s, t, places=6, msg=f"t={t}")
            checked += 1
        self.assertGreaterEqual(checked, 200)

    def test_fullness_holds_from_a_standstill_too(self):
        """From rest the vehicle must ACCELERATE to make a late time, not slow down."""
        from joint_interception.opportunities.schedule import arrival_at, earliest_arrival

        earliest, _ = earliest_arrival(DISTANCE, 0.0, LIMIT, ACCEL)
        for index in range(60):
            t = earliest + (90.0 - earliest) * index / 59
            profile = arrival_at(DISTANCE, 0.0, LIMIT, ACCEL, DECEL, t)
            self.assertIsNotNone(profile, f"no profile for t={t}")
            self.assertAlmostEqual(profile.integrate()[0], DISTANCE, places=6)
            self.assertAlmostEqual(profile.duration_s, t, places=6)


@requires_contracts
class TestC3Legality(unittest.TestCase):
    """C3: every produced profile respects the speed and acceleration bounds."""

    def test_no_violations_across_the_interval(self):
        from joint_interception.opportunities.schedule import arrival_at, earliest_arrival

        earliest, earliest_profile = earliest_arrival(DISTANCE, START_SPEED, LIMIT, ACCEL)
        self.assertEqual(earliest_profile.violations(LIMIT, ACCEL, DECEL), [])
        for index in range(120):
            t = earliest + (150.0 - earliest) * index / 119
            profile = arrival_at(DISTANCE, START_SPEED, LIMIT, ACCEL, DECEL, t)
            self.assertIsNotNone(profile)
            self.assertEqual(profile.violations(LIMIT, ACCEL, DECEL), [], f"t={t}")

    def test_the_violation_check_actually_fires(self):
        """A check that can never fail is not a check."""
        from joint_interception.opportunities.schedule import Segment, SpeedProfile

        too_fast = SpeedProfile(3.0, (Segment(10.0, 99.0),))
        problems = too_fast.violations(LIMIT, ACCEL, DECEL)
        self.assertTrue(any("acceleration" in p for p in problems), problems)
        self.assertTrue(any("above limit" in p for p in problems), problems)

        negative = SpeedProfile(1.0, (Segment(10.0, -4.0),))
        self.assertTrue(any("negative" in p for p in negative.violations(LIMIT, ACCEL, DECEL)))


@requires_contracts
class TestC4UnderIsEarned(unittest.TestCase):
    """C4: the returned set is labelled `UNDER` only because its times were verified."""

    def test_witness_is_under_and_reports_what_it_verified(self):
        from joint_interception.opportunities.schedule import constructive_arrival_set
        from joint_interception.opportunities.types import Direction

        witness = constructive_arrival_set(
            "p1", DISTANCE, START_SPEED, LIMIT, ACCEL, DECEL, HORIZON
        )
        self.assertIsNotNone(witness)
        self.assertIs(witness.arrival_set.direction, Direction.UNDER)
        self.assertGreater(witness.verified_sample_count, 0)
        self.assertEqual(witness.earliest_profile.violations(LIMIT, ACCEL, DECEL), [])

    def test_unreachable_distance_returns_no_witness_rather_than_a_guess(self):
        from joint_interception.opportunities.schedule import constructive_arrival_set

        self.assertIsNone(
            constructive_arrival_set("p1", 1e7, START_SPEED, LIMIT, ACCEL, DECEL, HORIZON)
        )

    def test_witness_earliest_matches_an_independent_earliest_arrival(self):
        from joint_interception.opportunities.schedule import (
            constructive_arrival_set,
            earliest_arrival,
        )

        witness = constructive_arrival_set(
            "p1", DISTANCE, START_SPEED, LIMIT, ACCEL, DECEL, HORIZON
        )
        independent, _ = earliest_arrival(DISTANCE, START_SPEED, LIMIT, ACCEL)
        self.assertAlmostEqual(witness.earliest_s, independent, places=9)


@requires_contracts
class TestC5Nonconvexity(unittest.TestCase):
    """C5: a blocking window yields a genuinely nonconvex set, still fully scheduled."""

    def test_blocking_window_splits_the_interval(self):
        from joint_interception.opportunities.schedule import constructive_arrival_set

        witness = constructive_arrival_set(
            "p1",
            DISTANCE,
            START_SPEED,
            LIMIT,
            ACCEL,
            DECEL,
            HORIZON,
            blocking_windows=((20.0, 40.0),),
        )
        self.assertIsNotNone(witness)
        intervals = witness.arrival_set.intervals
        self.assertGreaterEqual(len(intervals), 2)
        self.assertAlmostEqual(intervals[0][1], 20.0, places=9)
        self.assertAlmostEqual(intervals[1][0], 40.0, places=9)

    def test_no_time_inside_a_blocking_window_is_reported(self):
        from joint_interception.opportunities.schedule import constructive_arrival_set

        witness = constructive_arrival_set(
            "p1",
            DISTANCE,
            START_SPEED,
            LIMIT,
            ACCEL,
            DECEL,
            HORIZON,
            blocking_windows=((20.0, 40.0), (60.0, 75.0)),
        )
        for low, high in witness.arrival_set.intervals:
            for blocked_low, blocked_high in ((20.0, 40.0), (60.0, 75.0)):
                overlap = min(high, blocked_high) - max(low, blocked_low)
                self.assertLessEqual(overlap, 1e-9, f"[{low},{high}] overlaps a blocked window")

    def test_each_surviving_subinterval_is_still_fully_scheduled(self):
        from joint_interception.opportunities.schedule import arrival_at, constructive_arrival_set

        witness = constructive_arrival_set(
            "p1",
            DISTANCE,
            START_SPEED,
            LIMIT,
            ACCEL,
            DECEL,
            120.0,
            blocking_windows=((20.0, 40.0), (60.0, 75.0)),
        )
        for low, high in witness.arrival_set.intervals:
            for index in range(25):
                t = low + (high - low) * index / 24
                profile = arrival_at(DISTANCE, START_SPEED, LIMIT, ACCEL, DECEL, t)
                self.assertIsNotNone(profile, f"t={t}")
                self.assertAlmostEqual(profile.integrate()[0], DISTANCE, places=6)

    def test_a_window_covering_everything_yields_no_witness(self):
        from joint_interception.opportunities.schedule import constructive_arrival_set

        self.assertIsNone(
            constructive_arrival_set(
                "p1",
                DISTANCE,
                START_SPEED,
                LIMIT,
                ACCEL,
                DECEL,
                HORIZON,
                blocking_windows=((0.0, 400.0),),
            )
        )

    def test_the_convex_hull_would_readmit_blocked_times(self):
        """The error this nonconvexity exists to prevent."""
        from joint_interception.opportunities.reachability import convex_hull
        from joint_interception.opportunities.schedule import constructive_arrival_set

        witness = constructive_arrival_set(
            "p1",
            DISTANCE,
            START_SPEED,
            LIMIT,
            ACCEL,
            DECEL,
            HORIZON,
            blocking_windows=((20.0, 40.0),),
        )
        hull = convex_hull(witness.arrival_set.intervals)
        self.assertEqual(len(hull), 1)
        self.assertLess(hull[0][0], 20.0)
        self.assertGreater(hull[0][1], 40.0)  # the hull swallows the blocked window


@requires_contracts
class TestC6EndToEnd(unittest.TestCase):
    """C6: constructive sets reach SUPPORTED where free-flow sets give UNKNOWN."""

    def _assess(self, sets):
        from joint_interception.opportunities.compatibility import assess_joint_compatibility

        return assess_joint_compatibility(
            opportunity_id="o1",
            corridor="c1",
            participants=("p1", "p2"),
            arrival_sets=sets,
            stations={"p1": "L1", "p2": "L1"},
            lane_lengths={"L1": 30.0},
            dwell_required_s=2.0,
            body_length_m=5.0,
            min_gap_m=2.5,
        )

    def test_free_flow_gives_unknown(self):
        from joint_interception.opportunities.arrival import ArrivalQuery, FreeFlowArrivalModel
        from joint_interception.opportunities.types import Verdict

        model = FreeFlowArrivalModel()
        sets = [
            model.estimate(
                ArrivalQuery(p, DISTANCE, START_SPEED, LIMIT, ACCEL, DECEL, HORIZON)
            ).arrival_set
            for p in ("p1", "p2")
        ]
        self.assertEqual(self._assess(sets).temporal_verdict, Verdict.UNKNOWN)

    def test_constructive_gives_supported(self):
        from joint_interception.opportunities.schedule import constructive_arrival_set
        from joint_interception.opportunities.types import Verdict

        sets = [
            constructive_arrival_set(
                p, DISTANCE, START_SPEED, LIMIT, ACCEL, DECEL, HORIZON
            ).arrival_set
            for p in ("p1", "p2")
        ]
        opportunity = self._assess(sets)
        self.assertEqual(opportunity.temporal_verdict, Verdict.SUPPORTED)
        self.assertEqual(opportunity.verdict, Verdict.SUPPORTED)

    def test_the_first_constructive_supported_verdict_in_the_project(self):
        """Recorded explicitly: this is the first SUPPORTED verdict backed by schedules."""
        from joint_interception.opportunities.schedule import constructive_arrival_set
        from joint_interception.opportunities.types import Direction

        sets = [
            constructive_arrival_set(
                p, DISTANCE, START_SPEED, LIMIT, ACCEL, DECEL, HORIZON
            ).arrival_set
            for p in ("p1", "p2")
        ]
        self.assertTrue(all(s.direction is Direction.UNDER for s in sets))

    def test_blocked_participants_cannot_meet(self):
        """Disjoint blocking makes an otherwise-compatible pair temporally impossible."""
        from joint_interception.opportunities.schedule import constructive_arrival_set
        from joint_interception.opportunities.types import Verdict

        first = constructive_arrival_set(
            "p1",
            DISTANCE,
            START_SPEED,
            LIMIT,
            ACCEL,
            DECEL,
            40.0,
            blocking_windows=((20.0, 40.0),),
        )
        second = constructive_arrival_set(
            "p2",
            DISTANCE,
            START_SPEED,
            LIMIT,
            ACCEL,
            DECEL,
            40.0,
            blocking_windows=((0.0, 20.0),),
        )
        verdict = self._assess([first.arrival_set, second.arrival_set]).temporal_verdict
        # Both sets are UNDER, so an empty intersection cannot justify REJECTED (Rule B).
        self.assertEqual(verdict, Verdict.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
