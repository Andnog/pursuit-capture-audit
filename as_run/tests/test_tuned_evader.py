"""A-127: the TUNED evader (level 5)."""

from __future__ import annotations

import random
import unittest

from _w2_support import requires_contracts  # noqa: E402


def grid(n=4, length=120.0):
    """An n x n two-way grid with a few one-way removals, a cul-de-sac and unequal lengths."""
    from joint_interception.simulator.topology import Edge, Topology

    rng = random.Random(5)
    edges = []
    for r in range(n):
        for c in range(n):
            for dr, dc in ((0, 1), (1, 0)):
                r2, c2 = r + dr, c + dc
                if r2 >= n or c2 >= n:
                    continue
                a, b = f"n{r}{c}", f"n{r2}{c2}"
                ln = length * rng.choice((1.0, 1.5, 3.0, 9.0))
                edges.append(Edge(f"{a}_{b}", a, b, ln))
                if rng.random() > 0.15:
                    edges.append(Edge(f"{b}_{a}", b, a, ln))
    edges.append(Edge("culdesac", "n11", "dead", 60.0))
    return Topology.build(edges)


@requires_contracts
class TestTunedEvader(unittest.TestCase):
    def setUp(self):
        import joint_interception.simulator.evader as module

        self.module = module
        self.saved = module.TUNED_WEIGHTS
        self.top = grid()

    def tearDown(self):
        self.module.TUNED_WEIGHTS = self.saved

    def _states(self, k=400):
        rng = random.Random(11)
        edges = sorted(self.top.edges)
        for index in range(k):
            current = rng.choice(edges)
            n_p = rng.choice((1, 3, 5))
            p_nodes, p_pos = {}, {}
            for j in range(n_p):
                e = self.top.edges[rng.choice(edges)]
                p_nodes[f"p{j + 1}"] = e.to_node
                p_pos[f"p{j + 1}"] = (e.from_node, e.to_node, rng.random())
            yield index, current, p_nodes, p_pos

    def test_reference_weights_reproduce_optimal_escape(self):
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader

        self.module.TUNED_WEIGHTS = (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        compared = with_choice = 0
        for mode in ("node", "interpolated"):
            tuned = ScriptedEvader(EvaderLevel.TUNED, 3, self.top, input_mode=mode)
            optimal = ScriptedEvader(EvaderLevel.OPTIMAL_ESCAPE, 3, self.top, input_mode=mode)
            for index, current, p_nodes, p_pos in self._states():
                a = tuned.choose(index, current, p_nodes, p_pos)
                b = optimal.choose(index, current, p_nodes, p_pos)
                self.assertEqual(a.chosen, b.chosen, (mode, current, p_nodes))
                compared += 1
                with_choice += len(a.admissible) > 1
        self.assertEqual(compared, 800)
        self.assertGreater(with_choice, 300)

    def test_default_weights_are_the_reference(self):
        self.assertEqual(self.saved, (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
        self.assertEqual(len(self.module.TUNED_FEATURES), 7)

    def test_negative_weight_on_occupied_edges_avoids_them(self):
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader
        from joint_interception.simulator.topology import Edge, Topology

        top = Topology.build(
            [
                Edge("in", "A", "B", 100.0),
                Edge("left", "B", "L", 100.0),
                Edge("l_on", "L", "X", 100.0),
                Edge("right", "B", "R", 100.0),
                Edge("r_on", "R", "X", 100.0),
                Edge("x_on", "X", "A", 100.0),
            ]
        )
        self.module.TUNED_WEIGHTS = (0.0, 0.0, 0.0, 0.0, -1.0, 0.0, 0.0)
        ev = ScriptedEvader(EvaderLevel.TUNED, 3, top)
        d = ev.choose(0, "in", {"p1": "L"}, {"p1": ("B", "L", 0.5)})
        self.assertEqual(d.chosen, "right")
        d = ev.choose(1, "in", {"p1": "R"}, {"p1": ("B", "R", 0.5)})
        self.assertEqual(d.chosen, "left")
        d = ev.choose(2, "in", {"p1": "X"}, {"p1": ("R", "X", 0.1)})
        self.assertEqual(d.chosen, "left")

    def test_cul_de_sac_ranks_last_whatever_the_weights(self):
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader

        rng = random.Random(2)
        for trial in range(30):
            self.module.TUNED_WEIGHTS = tuple(rng.uniform(-1, 1) for _ in range(7))
            ev = ScriptedEvader(EvaderLevel.TUNED, trial, self.top)
            entering = [e for e in self.top.edges if self.top.edges[e].to_node == "n11"]
            for current in entering:
                d = ev.choose(0, current, {"p1": "n33"}, {"p1": ("n32", "n33", 0.3)})
                if len(d.admissible) > 1:
                    self.assertNotEqual(d.chosen, "culdesac")

    def test_deterministic_and_logged(self):
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader

        self.module.TUNED_WEIGHTS = (0.2, -0.4, 0.3, -0.1, -0.5, -0.6, 0.9)
        runs = []
        for _ in range(2):
            ev = ScriptedEvader(EvaderLevel.TUNED, 17, self.top)
            runs.append([ev.choose(i, c, n, p).chosen for i, c, n, p in self._states(120)])
            self.assertEqual(len(ev.decisions), 120)
            self.assertTrue(all(d.level is EvaderLevel.TUNED for d in ev.decisions))
            self.assertTrue(any(len(d.scores) > 1 for d in ev.decisions))
        self.assertEqual(runs[0], runs[1])

    def test_wrong_number_of_weights_is_refused(self):
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader

        self.module.TUNED_WEIGHTS = (1.0, 0.0)
        ev = ScriptedEvader(EvaderLevel.TUNED, 3, self.top)
        current = next(e for e in sorted(self.top.edges) if len(self.top.successors(e)) > 1)
        with self.assertRaises(ValueError):
            ev.choose(0, current, {"p1": "n33"}, None)


if __name__ == "__main__":
    unittest.main()
