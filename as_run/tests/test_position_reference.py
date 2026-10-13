"""SUMO reports the front bumper; the project's geometry is centred.

The mismatch was latent from W3 until A-46: invisible on one lane with one heading, wrong
by up to a body length across a junction.
"""

from __future__ import annotations

import math
import unittest

from _support import ROOT  # noqa: F401
from joint_interception.domain.geometry import Rectangle, body_separation_m  # noqa: E402
from joint_interception.simulator.sumo_adapter import TraciBackend  # noqa: E402

LENGTH, WIDTH = 5.0, 1.8
centre = TraciBackend.centre_from_front


class TestCentreFromFront(unittest.TestCase):
    def test_heading_east_moves_the_centre_back_along_x(self):
        self.assertEqual(centre(10.0, 0.0, 0.0, LENGTH), (7.5, 0.0))

    def test_heading_north_moves_the_centre_back_along_y(self):
        cx, cy = centre(0.0, 10.0, math.pi / 2, LENGTH)
        self.assertAlmostEqual(cx, 0.0, places=12)
        self.assertAlmostEqual(cy, 7.5, places=12)


class TestTheDefectMatteredOnlyAcrossHeadings(unittest.TestCase):
    """Why no single-lane native test caught it, and why it mattered anyway."""

    @staticmethod
    def separation(front_a, heading_a, front_b, heading_b, convert):
        def body(front, heading):
            x, y = centre(*front, heading, LENGTH) if convert else front
            return Rectangle(x, y, heading, LENGTH, WIDTH)

        return body_separation_m(body(front_a, heading_a), body(front_b, heading_b))

    def test_same_lane_same_heading_is_unaffected(self):
        """Both bodies shift alike, so the gap survives - the single-lane blind spot."""
        a, b = (0.0, 0.0), (7.0, 0.0)
        right = self.separation(a, 0.0, b, 0.0, convert=True)
        wrong = self.separation(a, 0.0, b, 0.0, convert=False)
        self.assertAlmostEqual(right, wrong, places=9)
        self.assertAlmostEqual(right, 2.0, places=9)

    def test_across_a_junction_the_uncorrected_separation_is_wrong(self):
        """One vehicle heading east, one heading north, meeting at a corner."""
        east_front, north_front = (0.0, 0.0), (3.0, -1.0)
        right = self.separation(east_front, 0.0, north_front, math.pi / 2, convert=True)
        wrong = self.separation(east_front, 0.0, north_front, math.pi / 2, convert=False)
        self.assertGreater(abs(right - wrong), 0.5)


if __name__ == "__main__":
    unittest.main()
