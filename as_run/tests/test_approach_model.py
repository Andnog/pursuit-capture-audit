"""The signal-aware approach model.

The model exists because A-40's constructive times were unreachable on the network. It must
therefore be held to the property that failed there: a time it reports must be ACHIEVABLE.
These tests cover the parts that can be checked without a simulator.
"""

from __future__ import annotations

import math
import unittest

from _support import ROOT  # noqa: F401
from joint_interception.opportunities.approach import (  # noqa: E402
    Segment,
    SignalProgram,
    earliest_arrival_on_approach,
    traverse,
)
from joint_interception.opportunities.schedule import earliest_arrival  # noqa: E402

PROGRAM = SignalProgram("t0", (82.0, 3.0, 5.0), ("GG", "yy", "rr"))


class TestItAgreesWithTheAbstractionWhereTheyOverlap(unittest.TestCase):
    def test_one_segment_no_signal_matches_earliest_arrival(self):
        """A single unobstructed lane is exactly the case the abstraction already solved.

        If these disagreed, one of them would be wrong and there would be no way to tell
        which from the network evidence alone.
        """
        result = earliest_arrival_on_approach([Segment("l0", 1000.0, 13.89)], {}, 0.0, 2.6, 4.5)
        expected, _ = earliest_arrival(1000.0, 0.0, 13.89, 2.6)
        self.assertAlmostEqual(result["time_s"], expected, places=9)


class TestSignalReading(unittest.TestCase):
    def test_green_and_red_are_read_from_the_program(self):
        self.assertTrue(PROGRAM.is_green(0, 0.0))
        self.assertFalse(PROGRAM.is_green(0, 86.0))

    def test_yellow_is_not_go(self):
        """Entering on yellow is a judgement the model must not make for the vehicle."""
        self.assertFalse(PROGRAM.is_green(0, 83.0))

    def test_next_green_is_the_start_of_the_next_green_phase(self):
        self.assertAlmostEqual(PROGRAM.next_green_s(0, 86.0), 90.0, places=6)

    def test_next_green_returns_the_time_itself_when_already_green(self):
        self.assertAlmostEqual(PROGRAM.next_green_s(0, 10.0), 10.0, places=6)

    def test_a_link_that_is_never_green_yields_infinity_not_a_wrong_answer(self):
        never = SignalProgram("t1", (10.0,), ("r",))
        self.assertEqual(never.next_green_s(0, 0.0), math.inf)

    def test_a_link_index_outside_the_state_string_is_treated_as_unsignalled(self):
        self.assertTrue(PROGRAM.is_green(99, 86.0))


class TestSignalsDelayAndTheDelayIsReported(unittest.TestCase):
    def test_a_red_on_arrival_adds_a_recorded_wait(self):
        #: Short lane so the vehicle reaches the signalled entry inside the red phase.
        segments = [
            Segment("l0", 1.0, 13.89),
            Segment(":j_0", 10.0, 7.0, True, ("t0", 0)),
            Segment("l1", 50.0, 13.89),
        ]
        red_start = SignalProgram("t0", (5.0, 82.0, 3.0), ("rr", "GG", "yy"))
        result = earliest_arrival_on_approach(segments, {"t0": red_start}, 0.0, 2.6, 4.5)
        self.assertTrue(result["reachable"])
        self.assertEqual(len(result["signal_waits"]), 1)
        self.assertGreater(result["total_wait_s"], 0.0)

    def test_a_green_on_arrival_adds_no_wait(self):
        segments = [
            Segment("l0", 1.0, 13.89),
            Segment(":j_0", 10.0, 7.0, True, ("t0", 0)),
        ]
        result = earliest_arrival_on_approach(segments, {"t0": PROGRAM}, 0.0, 2.6, 4.5)
        self.assertEqual(result["signal_waits"], [])
        self.assertEqual(result["total_wait_s"], 0.0)

    def test_a_link_never_green_makes_the_station_unreachable(self):
        segments = [Segment(":j_0", 10.0, 7.0, True, ("t0", 0))]
        never = SignalProgram("t0", (10.0,), ("r",))
        result = earliest_arrival_on_approach(segments, {"t0": never}, 0.0, 2.6, 4.5)
        self.assertFalse(result["reachable"])
        self.assertEqual(result["time_s"], math.inf)


class TestTheStoppingSetIsAFixedPoint(unittest.TestCase):
    """Stopping at a line is not free: the vehicle must brake in the PRECEDING segment.

    The first version of this model ignored that, via a helper that returned zero
    unconditionally. It understated every time involving a stop.
    """

    def test_a_run_without_signals_converges_immediately(self):
        result = earliest_arrival_on_approach([Segment("l0", 500.0, 13.89)], {}, 0.0, 2.6, 4.5)
        self.assertTrue(result["stop_set_converged"])
        self.assertEqual(result["stop_set_iterations"], 1)

    def test_convergence_is_reported_rather_than_assumed(self):
        segments = [
            Segment("l0", 200.0, 13.89),
            Segment(":j_0", 10.0, 7.0, True, ("t0", 0)),
            Segment("l1", 200.0, 13.89),
        ]
        result = earliest_arrival_on_approach(segments, {"t0": PROGRAM}, 0.0, 2.6, 4.5)
        self.assertIn("stop_set_converged", result)
        self.assertIsInstance(result["stop_set_converged"], bool)


class TestTraverseRespectsTheLimitsItIsGiven(unittest.TestCase):
    def test_exit_speed_never_exceeds_the_next_segments_cap(self):
        _, exit_speed = traverse(200.0, 13.89, 13.89, 5.0, 2.6, 4.5)
        self.assertLessEqual(exit_speed, 5.0 + 1e-9)

    def test_a_slower_segment_takes_longer(self):
        fast, _ = traverse(100.0, 0.0, 13.89, 13.89, 2.6, 4.5)
        slow, _ = traverse(100.0, 0.0, 5.0, 5.0, 2.6, 4.5)
        self.assertGreater(slow, fast)

    def test_a_zero_length_segment_costs_no_time(self):
        duration, _ = traverse(0.0, 10.0, 13.89, 13.89, 2.6, 4.5)
        self.assertEqual(duration, 0.0)

    def test_entry_above_the_cap_is_clamped_not_honoured(self):
        """A segment cannot be entered faster than it allows, whatever the caller passes."""
        duration, exit_speed = traverse(100.0, 20.0, 5.0, 5.0, 2.6, 4.5)
        self.assertLessEqual(exit_speed, 5.0 + 1e-9)
        self.assertGreater(duration, 0.0)


if __name__ == "__main__":
    unittest.main()
