"""A-112: the goal-directed evader (level 4)."""

from __future__ import annotations

import unittest

from _w2_support import requires_contracts  # noqa: E402


def two_routes():
    """From B the evader can go north (short to goal G) or east (long to G)."""
    from joint_interception.simulator.topology import Edge, Topology

    return Topology.build(
        [
            Edge("e1", "A", "B", 100.0),
            Edge("north", "B", "N", 100.0),
            Edge("n_goal", "N", "G", 800.0),
            Edge("east", "B", "E", 100.0),
            Edge("e_far", "E", "F", 900.0),
            Edge("f_goal", "F", "G", 900.0),
            Edge("g_on", "G", "H", 100.0),
            Edge("h_back", "H", "A", 100.0),
        ]
    )


@requires_contracts
class TestGoalDirectedEvader(unittest.TestCase):
    def _evader(self, seed=3):
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader

        return ScriptedEvader(EvaderLevel.GOAL_DIRECTED, seed, two_routes(), goal_nodes=("G",))

    def test_takes_the_shortest_route_to_the_destination_when_safe(self):
        d = self._evader().choose(0, "e1", {"p1": "H"})
        self.assertEqual(d.chosen, "north")
        self.assertEqual(d.reason, "shortest_road_distance_to_destination_among_safe")

    def test_avoids_a_continuation_ending_near_a_pursuer(self):
        d = self._evader().choose(0, "e1", {"p1": "N"})
        self.assertEqual(d.chosen, "east")

    def test_falls_back_to_escape_when_every_continuation_is_near_a_pursuer(self):
        d = self._evader().choose(0, "e1", {"p1": "N", "p2": "E"})
        self.assertEqual(d.reason, "all_continuations_near_a_pursuer_fallback_escape")

    def test_deterministic_given_seed(self):
        a = [self._evader(9).choose(i, "e1", {"p1": "H"}).chosen for i in range(5)]
        b = [self._evader(9).choose(i, "e1", {"p1": "H"}).chosen for i in range(5)]
        self.assertEqual(a, b)

    def test_destination_is_far_enough_by_road(self):
        from joint_interception.simulator.evader import GOAL_MIN_DISTANCE_M

        ev = self._evader()
        ev.choose(0, "e1", {"p1": "H"})
        self.assertEqual(ev._goal, "G")
        self.assertGreaterEqual(ev.topology.distance_between_nodes("B", "G"), GOAL_MIN_DISTANCE_M)

    def test_without_destinations_behaves_like_an_escape(self):
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader

        ev = ScriptedEvader(EvaderLevel.GOAL_DIRECTED, 3, two_routes())
        d = ev.choose(0, "e1", {"p1": "N"})
        self.assertEqual(d.reason, "all_continuations_near_a_pursuer_fallback_escape")
        self.assertEqual(d.chosen, "east")


if __name__ == "__main__":
    unittest.main()
