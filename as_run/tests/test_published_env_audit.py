"""Pure geometry of the published-environment audit (A-126); no simulator, no third-party code."""

import os
import sys
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

from audit_published_env import classify, tasks  # noqa: E402


def veh(x, y, speed, angle, road, lane=None, lane_pos=0.0):
    return {
        "x": x,
        "y": y,
        "speed": speed,
        "angle": angle,
        "road": road,
        "lane": lane or road + "_0",
        "lane_pos": lane_pos,
    }


class ClassifyTest(unittest.TestCase):
    def test_opposite_direction_passing(self):
        # evader eastbound on E12, pursuer westbound on -E12, lanes 3.2 m apart
        e = veh(100.0, -1.6, 13.0, 90.0, "E12")
        p = veh(102.0, 1.6, 13.0, 270.0, "-E12")
        c = classify(e, p)
        self.assertEqual(c["relation"], "opposite_direction")
        self.assertAlmostEqual(c["heading_diff_deg"], 180.0)
        self.assertAlmostEqual(c["lateral_m"], 3.2)
        self.assertFalse(c["stop_compatible"])

    def test_same_lane_blocked_stop(self):
        e = veh(100.0, -1.6, 0.0, 90.0, "E12")
        p = veh(104.0, -1.6, 0.0, 90.0, "E12")
        c = classify(e, p)
        self.assertEqual(c["relation"], "same_lane")
        self.assertTrue(c["pursuer_ahead"])
        self.assertAlmostEqual(c["longitudinal_m"], 4.0)
        self.assertTrue(c["stop_compatible"])

    def test_same_lane_pursuer_behind_is_not_a_stop(self):
        e = veh(100.0, -1.6, 0.0, 90.0, "E12")
        p = veh(96.0, -1.6, 0.0, 90.0, "E12")
        c = classify(e, p)
        self.assertFalse(c["pursuer_ahead"])
        self.assertFalse(c["stop_compatible"])

    def test_moving_evader_is_not_a_stop(self):
        e = veh(100.0, -1.6, 5.0, 90.0, "E12")
        p = veh(104.0, -1.6, 0.0, 90.0, "E12")
        self.assertFalse(classify(e, p)["stop_compatible"])

    def test_junction_and_other_road(self):
        e = veh(0.0, 0.0, 3.0, 0.0, ":J5_1", ":J5_1_0")
        p = veh(2.0, 2.0, 3.0, 90.0, "E12")
        self.assertEqual(classify(e, p)["relation"], "junction")
        e = veh(0.0, 0.0, 3.0, 0.0, "E15")
        self.assertEqual(classify(e, p)["relation"], "different_road")

    def test_heading_wraps(self):
        e = veh(0.0, 0.0, 1.0, 350.0, "E12")
        p = veh(0.0, 3.0, 1.0, 10.0, "E12")
        self.assertAlmostEqual(classify(e, p)["heading_diff_deg"], 20.0)


class TaskTest(unittest.TestCase):
    def test_registered_design(self):
        t = tasks()
        self.assertEqual(len(t), (300 + 100) * 2 * 2)
        self.assertEqual(len({x[0] for x in t}), len(t))


if __name__ == "__main__":
    unittest.main()
