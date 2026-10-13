"""Addendum r02 of the published-environment audit (A-133): pure logic, no simulator."""

import os
import sys
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

import audit_published_env_r02 as r02  # noqa: E402


class SpanTest(unittest.TestCase):
    def test_two_observations_span_one_second(self):
        self.assertEqual(r02.longest_span_s([10.0, 11.0]), 1.0)

    def test_three_consecutive_observations_span_two_seconds(self):
        self.assertEqual(r02.longest_span_s([10.0, 11.0, 12.0]), 2.0)

    def test_a_gap_restarts_the_span(self):
        self.assertEqual(r02.longest_span_s([10.0, 11.0, 13.0, 14.0]), 1.0)
        self.assertEqual(r02.longest_span_s([1.0, 5.0, 6.0, 7.0, 8.0, 20.0]), 3.0)

    def test_single_and_empty(self):
        self.assertEqual(r02.longest_span_s([4.0]), 0.0)
        self.assertIsNone(r02.longest_span_s([]))


class FakeVehicle:
    def __init__(self, world):
        self.world = world

    def getLeader(self, vid, _dist):  # noqa: N802 - TraCI name
        return self.world["leader"].get(vid)

    def getSpeed(self, vid):  # noqa: N802 - TraCI name
        return self.world["speed"][vid]


class FakeTraci:
    class TraCIException(Exception):  # noqa: N818 - TraCI name
        pass

    def __init__(self):
        self.world = {"leader": {}, "speed": {}, "t": 0.0}
        self.vehicle = FakeVehicle(self.world)
        self.simulation = type("S", (), {"getTime": lambda _self: self.world["t"]})()


class ObserverTest(unittest.TestCase):
    def _run(self, frames):
        traci, obs = FakeTraci(), r02.StopObserver()
        for t, leader, e_speed, p_speed in frames:
            traci.world["t"] = t
            traci.world["leader"] = {"e0": (leader, 2.5) if leader else None}
            traci.world["speed"] = {"e0": e_speed, "p0": p_speed, "p1": p_speed, "Background1": 0.0}
            obs.observe(traci, ["e0"])
        return obs.spans()

    def test_two_observations_are_not_two_seconds(self):
        spans = self._run([(0.0, "p0", 0.0, 0.0), (1.0, "p0", 0.0, 0.0)])
        self.assertEqual(spans["e0"], 1.0)
        self.assertLess(spans["e0"], r02.REQUIRED_S)

    def test_three_observations_behind_the_same_pursuer(self):
        spans = self._run([(t, "p0", 0.5, 0.2) for t in (5.0, 6.0, 7.0)])
        self.assertGreaterEqual(spans["e0"], r02.REQUIRED_S)

    def test_a_change_of_leader_does_not_accumulate(self):
        frames = [
            (0.0, "p0", 0.0, 0.0),
            (1.0, "p0", 0.0, 0.0),
            (2.0, "p1", 0.0, 0.0),
            (3.0, "p1", 0.0, 0.0),
        ]
        self.assertEqual(self._run(frames)["e0"], 1.0)

    def test_moving_or_background_leader_does_not_count(self):
        self.assertEqual(self._run([(t, "p0", 3.0, 0.0) for t in (0.0, 1.0, 2.0)]), {})
        self.assertEqual(self._run([(t, "Background1", 0.0, 0.0) for t in (0.0, 1.0, 2.0)]), {})
        self.assertEqual(self._run([(t, "p0", 0.0, 4.0) for t in (0.0, 1.0, 2.0)]), {})


class DesignTest(unittest.TestCase):
    def test_censored_selection(self):
        ev = {"step": 790, "evader": "e0", "pursuer": "p1"}
        rows = {
            "a": {"key": "a", "mode": "followup", "events": [ev], "follow": [{"dt": 1}, {"dt": 5}]},
            "b": {
                "key": "b",
                "mode": "followup",
                "events": [ev],
                "follow": [{"dt": d} for d in (1, 2, 5, 10, 30)],
            },
            "c": {"key": "c", "mode": "followup", "events": [], "follow": []},
            "d": {"key": "d", "mode": "published", "events": [ev], "follow": []},
        }
        self.assertEqual(r02.censored_keys(rows), ["a"])

    def test_tasks_on_the_sealed_package(self):
        rows = r02.sealed_rows()
        t = r02.tasks(rows)
        self.assertEqual(sum(x[0] == "F" for x in t), 12)
        self.assertEqual(sum(x[0] == "S" for x in t), 800)
        self.assertEqual(len({x[1] for x in t}), len(t))


if __name__ == "__main__":
    unittest.main()
