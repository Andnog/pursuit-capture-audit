"""Arrival models: the direction is a property of the model, not a caller's annotation.

METHOD_SPEC_EN.md section 2.3 makes the two rules asymmetric. Rule A (`SUPPORTED`) needs
`UNDER`; Rule B (`REJECTED`) needs `OVER`. A model that computes an earliest arrival must
not be able to present itself as `UNDER`.
"""

from __future__ import annotations

import unittest

from _w2_support import requires_contracts  # noqa: E402


def query(distance_m=100.0, speed=3.0, limit=13.89, accel=2.6, horizon=300.0):
    from joint_interception.opportunities.arrival import ArrivalQuery

    return ArrivalQuery(
        participant="p1",
        distance_m=distance_m,
        current_speed_mps=speed,
        speed_limit_mps=limit,
        max_acceleration_mps2=accel,
        max_deceleration_mps2=4.5,
        horizon_s=horizon,
    )


@requires_contracts
class TestFreeFlowTime(unittest.TestCase):
    def test_pure_acceleration_phase_matches_the_closed_form(self):
        """From rest at 2 m/s^2 over 100 m: t = sqrt(2d/a) = sqrt(100) = 10 s."""
        from joint_interception.opportunities.arrival import free_flow_time_s

        self.assertAlmostEqual(
            free_flow_time_s(query(distance_m=100.0, speed=0.0, limit=1000.0, accel=2.0)),
            10.0,
            places=9,
        )

    def test_cruise_phase_is_added_after_the_limit_is_reached(self):
        """0 to 10 m/s at 2 m/s^2 takes 5 s over 25 m; the remaining 75 m at 10 m/s is 7.5 s."""
        from joint_interception.opportunities.arrival import free_flow_time_s

        self.assertAlmostEqual(
            free_flow_time_s(query(distance_m=100.0, speed=0.0, limit=10.0, accel=2.0)),
            12.5,
            places=9,
        )

    def test_zero_distance_is_immediate(self):
        from joint_interception.opportunities.arrival import free_flow_time_s

        self.assertEqual(free_flow_time_s(query(distance_m=0.0)), 0.0)

    def test_beyond_the_horizon_is_uncoverable(self):
        from joint_interception.opportunities.arrival import free_flow_time_s

        self.assertIsNone(free_flow_time_s(query(distance_m=1e7, horizon=300.0)))

    def test_free_flow_is_a_lower_bound_on_any_slower_traversal(self):
        """Interaction only delays, so no achievable time is shorter than free flow."""
        from joint_interception.opportunities.arrival import free_flow_time_s

        fastest = free_flow_time_s(query(distance_m=200.0, speed=5.0, limit=13.89, accel=2.6))
        slower = free_flow_time_s(query(distance_m=200.0, speed=5.0, limit=8.0, accel=2.6))
        self.assertLess(fastest, slower)


@requires_contracts
class TestDeclaredDirections(unittest.TestCase):
    def test_free_flow_is_over_and_can_never_support(self):
        from joint_interception.opportunities.arrival import (
            FreeFlowArrivalModel,
            can_reject,
            can_support,
        )
        from joint_interception.opportunities.types import Direction

        model = FreeFlowArrivalModel()
        self.assertIs(model.declared_direction, Direction.OVER)
        self.assertFalse(can_support([model]))
        self.assertTrue(can_reject([model]))
        self.assertIs(model.estimate(query()).direction, Direction.OVER)

    def test_free_flow_supplies_no_certified_upper_bound(self):
        """The heart of it: an arbitrarily slow arrival stays possible under interaction."""
        from joint_interception.opportunities.arrival import FreeFlowArrivalModel

        estimate = FreeFlowArrivalModel().estimate(query())
        self.assertTrue(estimate.covered)
        self.assertIsNotNone(estimate.earliest_s)
        self.assertIsNone(estimate.certified_upper_bound_s)

    def test_constructive_is_under_only_with_a_schedule(self):
        from joint_interception.opportunities.arrival import (
            ConstructiveArrivalModel,
            can_support,
        )
        from joint_interception.opportunities.types import Direction

        with_schedule = ConstructiveArrivalModel(schedules={"p1": (12.0, 20.0)})
        estimate = with_schedule.estimate(query())
        self.assertIs(estimate.direction, Direction.UNDER)
        self.assertTrue(estimate.covered)
        self.assertEqual(estimate.certified_upper_bound_s, 20.0)
        self.assertTrue(can_support([with_schedule]))

    def test_constructive_without_a_schedule_reports_uncovered_not_a_guess(self):
        """Falling back to free flow would turn an unsupportable claim into a
        supportable-looking one."""
        from joint_interception.opportunities.arrival import ConstructiveArrivalModel

        estimate = ConstructiveArrivalModel(schedules={}).estimate(query())
        self.assertFalse(estimate.covered)
        self.assertIsNone(estimate.earliest_s)
        self.assertEqual(estimate.reason, "no_constructive_schedule_supplied")

    def test_recorded_profile_is_prediction_and_supports_neither(self):
        from joint_interception.opportunities.arrival import (
            RecordedProfileModel,
            can_reject,
            can_support,
        )
        from joint_interception.opportunities.types import Direction

        model = RecordedProfileModel()
        self.assertIs(model.declared_direction, Direction.PREDICTION)
        self.assertFalse(can_support([model]))
        self.assertFalse(can_reject([model]))

    def test_every_model_justifies_its_direction(self):
        from joint_interception.opportunities.arrival import (
            ConstructiveArrivalModel,
            FreeFlowArrivalModel,
            RecordedProfileModel,
        )

        for model in (
            FreeFlowArrivalModel(),
            ConstructiveArrivalModel(schedules={}),
            RecordedProfileModel(),
        ):
            with self.subTest(model=model.model_id):
                self.assertTrue(model.direction_justification.strip())
                self.assertGreater(len(model.direction_justification), 40)


@requires_contracts
class TestMixedDirectionsSupportNothing(unittest.TestCase):
    def test_a_mixed_set_can_neither_support_nor_reject(self):
        from joint_interception.opportunities.arrival import (
            ConstructiveArrivalModel,
            FreeFlowArrivalModel,
            can_reject,
            can_support,
        )

        mixed = [FreeFlowArrivalModel(), ConstructiveArrivalModel(schedules={"p1": (1.0, 2.0)})]
        self.assertFalse(can_support(mixed))
        self.assertFalse(can_reject(mixed))

    def test_empty_set_supports_nothing(self):
        from joint_interception.opportunities.arrival import can_reject, can_support

        self.assertFalse(can_support([]))
        self.assertFalse(can_reject([]))


@requires_contracts
class TestEndToEndThroughTheCompatibilityPredicate(unittest.TestCase):
    """The whole point: a free-flow model cannot yield SUPPORTED through the real predicate."""

    def test_free_flow_sets_yield_unknown_not_supported(self):
        from joint_interception.opportunities.arrival import ArrivalQuery, FreeFlowArrivalModel
        from joint_interception.opportunities.compatibility import assess_joint_compatibility
        from joint_interception.opportunities.types import Verdict

        model = FreeFlowArrivalModel()
        sets = [
            model.estimate(ArrivalQuery(p, 100.0, 3.0, 13.89, 2.6, 4.5, 300.0)).arrival_set
            for p in ("p1", "p2")
        ]
        opportunity = assess_joint_compatibility(
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
        self.assertEqual(opportunity.temporal_verdict, Verdict.UNKNOWN)
        self.assertNotEqual(opportunity.verdict, Verdict.SUPPORTED)

    def test_constructive_sets_can_yield_supported(self):
        from joint_interception.opportunities.arrival import ArrivalQuery, ConstructiveArrivalModel
        from joint_interception.opportunities.compatibility import assess_joint_compatibility
        from joint_interception.opportunities.types import Verdict

        model = ConstructiveArrivalModel(schedules={"p1": (10.0, 20.0), "p2": (12.0, 22.0)})
        sets = [
            model.estimate(ArrivalQuery(p, 100.0, 3.0, 13.89, 2.6, 4.5, 300.0)).arrival_set
            for p in ("p1", "p2")
        ]
        opportunity = assess_joint_compatibility(
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
        self.assertEqual(opportunity.verdict, Verdict.SUPPORTED)


if __name__ == "__main__":
    unittest.main()


@requires_contracts
class TestScheduledArrivalModel(unittest.TestCase):
    """The model that generates its own witnesses rather than being handed them."""

    def test_it_is_under_and_can_support(self):
        from joint_interception.opportunities.arrival import ScheduledArrivalModel, can_support
        from joint_interception.opportunities.types import Direction

        model = ScheduledArrivalModel()
        self.assertIs(model.declared_direction, Direction.UNDER)
        self.assertTrue(can_support([model]))

    def test_it_supplies_a_certified_upper_bound(self):
        """The thing free-flow could never provide."""
        from joint_interception.opportunities.arrival import ScheduledArrivalModel

        estimate = ScheduledArrivalModel().estimate(query())
        self.assertTrue(estimate.covered)
        self.assertIsNotNone(estimate.certified_upper_bound_s)
        self.assertIn("verified_schedules_on_", estimate.reason)

    def test_its_earliest_matches_an_independent_computation(self):
        from joint_interception.opportunities.arrival import ScheduledArrivalModel
        from joint_interception.opportunities.schedule import earliest_arrival

        estimate = ScheduledArrivalModel().estimate(query())
        independent, _ = earliest_arrival(100.0, 3.0, 13.89, 2.6)
        self.assertAlmostEqual(estimate.earliest_s, independent, places=9)

    def test_unreachable_distance_reports_uncovered_not_a_guess(self):
        from joint_interception.opportunities.arrival import ArrivalQuery, ScheduledArrivalModel

        estimate = ScheduledArrivalModel().estimate(
            ArrivalQuery("p1", 1e7, 3.0, 13.89, 2.6, 4.5, 300.0)
        )
        self.assertFalse(estimate.covered)
        self.assertEqual(estimate.reason, "no_verified_schedule_exists")

    def test_blocking_windows_make_the_reported_set_nonconvex(self):
        from joint_interception.opportunities.arrival import ScheduledArrivalModel

        model = ScheduledArrivalModel(blocking_windows=((20.0, 40.0),))
        intervals = model.estimate(query()).arrival_set.intervals
        self.assertGreaterEqual(len(intervals), 2)
