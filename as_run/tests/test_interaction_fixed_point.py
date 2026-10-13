"""The interaction half: blocking windows derived from committed plans.

Every negative control the package protocol requires lives here. A module that can only
report success has not been shown to detect failure.
"""

from __future__ import annotations

import itertools
import unittest

from _support import ROOT  # noqa: F401
from joint_interception.opportunities.interaction import (  # noqa: E402
    ConsistencyVerdict,
    Lane,
    Participant,
    _contains,
    blocking_for,
    max_concurrent,
    occupancy_window,
    solve_mutual_consistency,
)
from joint_interception.opportunities.schedule import constructive_arrival_set  # noqa: E402

LANE = Lane("shared", length_m=14.0, body_length_m=5.0, min_gap_m=2.5)


def participant(pid: str, distance_m: float, **kwargs) -> Participant:
    return Participant(
        participant_id=pid,
        distance_m=distance_m,
        initial_speed_mps=kwargs.get("initial_speed_mps", 0.0),
        speed_limit_mps=kwargs.get("speed_limit_mps", 13.89),
        max_acceleration_mps2=kwargs.get("max_acceleration_mps2", 2.6),
        max_deceleration_mps2=kwargs.get("max_deceleration_mps2", 4.5),
    )


class TestCapacityMatchesTheFrozenWitness(unittest.TestCase):
    def test_a_14m_lane_admits_two_bodies_and_not_three(self):
        self.assertEqual(LANE.capacity(), 2)
        self.assertAlmostEqual(2 * 5.0 + 1 * 2.5, 12.5)
        self.assertAlmostEqual(3 * 5.0 + 2 * 2.5, 20.0)

    def test_a_lane_too_short_for_one_body_has_capacity_zero(self):
        self.assertEqual(Lane("tiny", 3.0, 5.0, 2.5).capacity(), 0)


class TestTheSweepIsNotAPairwiseCheck(unittest.TestCase):
    """Negative control 1: pairwise passes and the joint constraint fails."""

    #: Three windows overlapping at one instant. Capacity is two.
    SIMULTANEOUS = [(0.0, 3.0), (1.0, 4.0), (2.0, 5.0)]

    @staticmethod
    def pairwise_peak(windows):
        """What a pairwise test sees: the worst overlap over PAIRS only."""
        return max(max_concurrent([a, b]) for a, b in itertools.combinations(windows, 2))

    def test_pairwise_passes_while_the_joint_constraint_fails(self):
        self.assertLessEqual(self.pairwise_peak(self.SIMULTANEOUS), LANE.capacity())
        self.assertGreater(max_concurrent(self.SIMULTANEOUS), LANE.capacity())

    def test_sequential_pairwise_overlap_is_not_a_violation(self):
        """The pairwise test is not merely weak; it is wrong in both directions.

        These three windows overlap pairwise in sequence but never three at once, so they
        FIT. A rule forbidding pairwise overlap would reject a legal configuration.
        """
        sequential = [(0.0, 2.0), (1.0, 3.0), (2.5, 4.0)]
        self.assertEqual(max_concurrent(sequential), 2)
        self.assertLessEqual(max_concurrent(sequential), LANE.capacity())

    def test_a_vehicle_leaving_as_another_arrives_is_not_simultaneous(self):
        self.assertEqual(max_concurrent([(0.0, 2.0), (2.0, 4.0)]), 1)


class TestBlockingIsDerivedFromCapacityNotFromPresence(unittest.TestCase):
    def test_one_other_occupant_blocks_nothing_when_capacity_is_two(self):
        commitments = {"p2": type("C", (), {"participant_id": "p2", "occupancy": (10.0, 12.0)})()}
        self.assertEqual(blocking_for("p1", commitments, capacity=2), ())

    def test_two_other_occupants_block_their_overlap(self):
        class C:
            def __init__(self, pid, occ):
                self.participant_id = pid
                self.occupancy = occ

        commitments = {"p2": C("p2", (10.0, 14.0)), "p3": C("p3", (12.0, 16.0))}
        blocked = blocking_for("p1", commitments, capacity=2)
        self.assertEqual(blocked, ((12.0, 14.0),))


class TestTheConvexHullIsUnsoundHere(unittest.TestCase):
    """Negative control 3: the hull admits a time the blocking windows removed."""

    def test_a_time_in_the_hull_is_not_a_time_in_the_set(self):
        witness = constructive_arrival_set(
            "p1",
            distance_m=60.0,
            initial_speed_mps=0.0,
            speed_limit_mps=13.89,
            max_acceleration_mps2=2.6,
            max_deceleration_mps2=4.5,
            horizon_s=120.0,
            blocking_windows=((20.0, 40.0),),
        )
        self.assertIsNotNone(witness)
        intervals = witness.arrival_set.intervals
        self.assertGreater(len(intervals), 1, "the blocking window must split the set")

        hull_low, hull_high = intervals[0][0], intervals[-1][1]
        blocked_time = 30.0
        self.assertTrue(hull_low <= blocked_time <= hull_high, "in the hull")
        self.assertFalse(_contains(witness, blocked_time), "but not in the set")


class TestProvableInconsistencyIsReachable(unittest.TestCase):
    """Negative control 2: failure is reachable, and is distinguished from 'not found'."""

    def test_a_lane_too_short_for_one_body_is_provably_inconsistent(self):
        result = solve_mutual_consistency(
            [participant("p1", 50.0)],
            Lane("tiny", 3.0, 5.0, 2.5),
            horizon_s=100.0,
            dwell_s=2.0,
        )
        self.assertIs(result.verdict, ConsistencyVerdict.PROVABLY_INCONSISTENT)
        self.assertIsNotNone(result.proof)

    def test_an_unreachable_participant_is_provably_inconsistent(self):
        """Unreachable BEFORE any blocking, so no assignment can rescue it.

        The proof does not depend on the grid: blocking only ever removes times, so a
        participant with an empty set under no blocking has an empty set under any.
        """
        result = solve_mutual_consistency(
            [participant("p1", 100_000.0)],
            LANE,
            horizon_s=10.0,
            dwell_s=2.0,
        )
        self.assertIs(result.verdict, ConsistencyVerdict.PROVABLY_INCONSISTENT)
        self.assertIn("blocking only removes times", result.proof)


class TestWitnessesAreVerifiedNotAsserted(unittest.TestCase):
    def test_a_found_witness_satisfies_all_three_soundness_conditions(self):
        participants = [
            participant("p1", 60.0),
            participant("p2", 80.0),
            participant("p3", 110.0),
        ]
        result = solve_mutual_consistency(participants, LANE, horizon_s=120.0, dwell_s=2.0, grid=7)
        self.assertIs(result.verdict, ConsistencyVerdict.WITNESS_VERIFIED)

        committed = {c.participant_id: c.arrival_s for c in result.commitments}

        # 1. every time lies in its set recomputed against the others
        for p in participants:
            blocking = blocking_for(
                p.participant_id,
                {c.participant_id: c for c in result.commitments},
                result.capacity,
            )
            witness = constructive_arrival_set(
                p.participant_id,
                p.distance_m,
                p.initial_speed_mps,
                p.speed_limit_mps,
                p.max_acceleration_mps2,
                p.max_deceleration_mps2,
                120.0,
                blocking_windows=blocking,
            )
            self.assertIsNotNone(witness)
            self.assertTrue(_contains(witness, committed[p.participant_id]))

        # 2. capacity holds at every instant
        windows = [c.occupancy for c in result.commitments]
        self.assertLessEqual(max_concurrent(windows), result.capacity)

        # 3. the arrival sets carry a discharged UNDER label
        for witness in result.witnesses:
            self.assertGreater(witness.verified_sample_count, 0)

    def test_occupancy_starts_at_arrival_and_lasts_the_dwell(self):
        self.assertEqual(occupancy_window(10.0, 2.0), (10.0, 12.0))


class TestTheInteractionIsNotVacuous(unittest.TestCase):
    """The coupling must actually bite, not merely exist in the code.

    A first witness was found in which only one participant saw any blocking window, and
    that window lay entirely before its earliest arrival — so it removed nothing. The
    machinery was present and inert. These tests fix configurations where the interaction
    changes the answer, so a regression to inert coupling fails rather than passes.
    """

    #: Blockers far (late earliest), blocked participant near (early earliest), so the
    #: blocked window falls strictly INSIDE the near participant's reachable range.
    FAR = 250.0
    NEAR = 30.0

    def solve(self):
        return solve_mutual_consistency(
            [
                participant("far1", self.FAR),
                participant("far2", self.FAR),
                participant("near", self.NEAR),
            ],
            LANE,
            horizon_s=120.0,
            dwell_s=6.0,
            grid=9,
        )

    def test_the_interaction_produces_a_nonconvex_arrival_set(self):
        result = self.solve()
        self.assertIs(result.verdict, ConsistencyVerdict.WITNESS_VERIFIED)
        near = next(w for w in result.witnesses if w.participant == "near")
        self.assertEqual(
            len(near.arrival_set.intervals),
            2,
            "the blockers' joint occupancy must punch a hole, not merely truncate a front",
        )
        self.assertTrue(near.blocking_windows, "the hole must come from a blocking window")

    def test_the_hull_of_that_set_would_readmit_a_genuinely_blocked_time(self):
        """Nonconvexity produced by interaction is load-bearing, not decorative."""
        result = self.solve()
        near = next(w for w in result.witnesses if w.participant == "near")
        (low, gap_start), (gap_end, high) = near.arrival_set.intervals
        blocked_time = (gap_start + gap_end) / 2.0

        self.assertTrue(low <= blocked_time <= high, "inside the convex hull")
        self.assertFalse(_contains(near, blocked_time), "outside the set")

        occupied = sum(
            1
            for c in result.commitments
            if c.participant_id != "near" and c.occupancy[0] <= blocked_time <= c.occupancy[1]
        )
        self.assertGreaterEqual(
            occupied,
            result.capacity,
            "and blocked for a physical reason: the lane is already full at that instant",
        )

    def test_blocking_delays_a_participant_beyond_its_unblocked_earliest(self):
        """Three participants that all want the same early slot; capacity is two."""
        result = solve_mutual_consistency(
            [participant("p1", 60.0), participant("p2", 60.0), participant("p3", 60.0)],
            LANE,
            horizon_s=60.0,
            dwell_s=8.0,
            grid=9,
        )
        self.assertIs(result.verdict, ConsistencyVerdict.WITNESS_VERIFIED)
        unblocked_earliest = constructive_arrival_set(
            "p3", 60.0, 0.0, 13.89, 2.6, 4.5, 60.0
        ).earliest_s
        arrivals = sorted(c.arrival_s for c in result.commitments)
        self.assertGreater(
            arrivals[-1],
            unblocked_earliest + 1.0,
            "the third participant must be pushed well past what it could reach alone",
        )


class TestFailureIsNotMisreportedAsNonExistence(unittest.TestCase):
    def test_a_search_that_finds_nothing_says_only_that(self):
        """Four participants, capacity two, a horizon too tight to stagger them.

        Whatever the truth is, the module may only report what it checked.
        """
        participants = [participant(f"p{i}", 60.0 + i) for i in range(1, 5)]
        result = solve_mutual_consistency(participants, LANE, horizon_s=12.0, dwell_s=6.0, grid=3)
        self.assertIn(
            result.verdict,
            (ConsistencyVerdict.NOT_FOUND_ON_THIS_GRID, ConsistencyVerdict.WITNESS_VERIFIED),
        )
        if result.verdict is ConsistencyVerdict.NOT_FOUND_ON_THIS_GRID:
            self.assertIsNone(result.proof, "a failed search carries no proof")
            self.assertGreater(result.combinations_examined, 0)


if __name__ == "__main__":
    unittest.main()
