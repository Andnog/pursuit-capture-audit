"""The scripted evader: three declared difficulty levels, deterministic, auditable.

Decision D08, frozen 21 September 2026. These tests check the properties the contract
actually commits to, including the one that links D08 to D06: every decision must record
its alternatives, or the dead-end rule cannot be checked.
"""

from __future__ import annotations

import unittest

from _w2_support import requires_contracts  # noqa: E402


def line_with_branch():
    """A -> B, then B branches to C (open) or D (dead end)."""
    from joint_interception.simulator.topology import Edge, Topology

    return Topology.build(
        [
            Edge("e1", "A", "B", 100.0),
            Edge("e_open", "B", "C", 100.0),
            Edge("e_dead", "B", "D", 100.0),
            Edge("e_onward", "C", "E", 100.0),
        ]
    )


def both_branches_dead():
    """A -> B, then both continuations dead-end. The evader is genuinely forced."""
    from joint_interception.simulator.topology import Edge, Topology

    return Topology.build(
        [
            Edge("e1", "A", "B", 100.0),
            Edge("e_dead_a", "B", "X", 100.0),
            Edge("e_dead_b", "B", "Y", 100.0),
        ]
    )


@requires_contracts
class TestTopology(unittest.TestCase):
    def test_successors_are_in_a_frozen_order(self):
        topology = line_with_branch()
        self.assertEqual(topology.successors("e1"), ["e_dead", "e_open"])
        self.assertEqual(topology.successors("e1"), topology.successors("e1"))

    def test_dead_end_detection(self):
        topology = line_with_branch()
        self.assertTrue(topology.is_dead_end("e_dead"))
        self.assertFalse(topology.is_dead_end("e_open"))

    def test_distance_is_shortest_path_not_hop_count(self):
        from joint_interception.simulator.topology import Edge, Topology

        topology = Topology.build(
            [
                Edge("long", "A", "B", 500.0),
                Edge("short_1", "A", "M", 10.0),
                Edge("short_2", "M", "B", 10.0),
            ]
        )
        self.assertAlmostEqual(topology.distance_between_nodes("A", "B"), 20.0)

    def test_unreachable_is_none_not_infinity(self):
        from joint_interception.simulator.topology import Edge, Topology

        topology = Topology.build([Edge("e1", "A", "B", 10.0)])
        self.assertIsNone(topology.distance_between_nodes("B", "A"))


@requires_contracts
class TestDeterminism(unittest.TestCase):
    """Required for replicable experiments AND for the assistance replay prefix."""

    def _run(self, level, seed, steps=6):
        from joint_interception.simulator.evader import ScriptedEvader

        topology = line_with_branch()
        evader = ScriptedEvader(level, seed, topology)
        edge = "e1"
        trace = []
        for index in range(steps):
            decision = evader.choose(index, edge, {"p1": "E"})
            trace.append(decision.chosen)
            if decision.chosen is None:
                break
            edge = decision.chosen
        return trace

    def test_same_level_and_seed_reproduce_exactly(self):
        from joint_interception.simulator.evader import EvaderLevel

        for level in EvaderLevel:
            with self.subTest(level=level.name):
                self.assertEqual(self._run(level, 1234), self._run(level, 1234))

    def test_choice_depends_on_the_decision_index_not_a_draw_counter(self):
        """Keyed randomness, so a restored prefix reproduces the same choice.

        W3 showed a shared seed does not couple two runs once they consume different
        numbers of draws. A sequential stream would make the evader's choice depend on what
        else happened to draw; keying on the decision index removes that coupling.
        """
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader

        topology = line_with_branch()
        first = ScriptedEvader(EvaderLevel.RANDOM, 77, topology)
        second = ScriptedEvader(EvaderLevel.RANDOM, 77, topology)
        # `second` makes an unrelated decision first, so a sequential stream would desync it.
        second.choose(99, "e1", {"p1": "E"})
        self.assertEqual(
            first.choose(5, "e1", {"p1": "E"}).chosen,
            second.choose(5, "e1", {"p1": "E"}).chosen,
        )

    def test_different_seeds_can_differ(self):
        """A seed that changed nothing would mean the level was not stochastic at all."""
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader

        topology = line_with_branch()
        chosen = {
            ScriptedEvader(EvaderLevel.RANDOM, seed, topology).choose(0, "e1", {"p1": "E"}).chosen
            for seed in range(40)
        }
        self.assertGreater(len(chosen), 1)


@requires_contracts
class TestLevelOrdering(unittest.TestCase):
    """The levels must actually differ in difficulty, or the knob is decorative."""

    def test_level_3_avoids_a_dead_end_when_an_alternative_exists(self):
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader

        topology = line_with_branch()
        for seed in range(30):
            evader = ScriptedEvader(EvaderLevel.OPTIMAL_ESCAPE, seed, topology)
            self.assertEqual(evader.choose(0, "e1", {"p1": "E"}).chosen, "e_open")

    def test_level_1_sometimes_walks_into_the_dead_end(self):
        """Random is genuinely worse; if it never did this it would not be level 1."""
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader

        topology = line_with_branch()
        entered = sum(
            ScriptedEvader(EvaderLevel.RANDOM, seed, topology).choose(0, "e1", {"p1": "E"}).chosen
            == "e_dead"
            for seed in range(60)
        )
        self.assertGreater(entered, 0)

    def test_level_3_is_at_least_as_far_from_pursuers_as_level_2(self):
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader

        topology = line_with_branch()
        for seed in range(30):
            with self.subTest(seed=seed):
                two = ScriptedEvader(EvaderLevel.AVOIDANT, seed, topology)
                three = ScriptedEvader(EvaderLevel.OPTIMAL_ESCAPE, seed, topology)
                d2 = two.choose(0, "e1", {"p1": "D"})
                d3 = three.choose(0, "e1", {"p1": "D"})
                # Level 3 must never score its own choice below what level 2 achieved.
                self.assertGreaterEqual(d3.scores[d3.chosen], d2.scores[d2.chosen])

    def test_a_single_admissible_continuation_is_taken_at_every_level(self):
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader
        from joint_interception.simulator.topology import Edge, Topology

        topology = Topology.build([Edge("e1", "A", "B", 10.0), Edge("only", "B", "C", 10.0)])
        for level in EvaderLevel:
            with self.subTest(level=level.name):
                evader = ScriptedEvader(level, 5, topology)
                self.assertEqual(evader.choose(0, "e1", {"p1": "C"}).chosen, "only")


@requires_contracts
class TestDecisionRecordSupportsTheD06DeadEndRule(unittest.TestCase):
    """The link between D08 and D06: without alternatives logged, the rule is vacuous."""

    def test_every_decision_records_its_admissible_set(self):
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader

        evader = ScriptedEvader(EvaderLevel.AVOIDANT, 3, line_with_branch())
        decision = evader.choose(0, "e1", {"p1": "E"})
        self.assertEqual(set(decision.admissible), {"e_open", "e_dead"})
        self.assertTrue(decision.had_alternatives)

    def test_entering_a_dead_end_is_recorded(self):
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader

        evader = ScriptedEvader(EvaderLevel.RANDOM, 1, line_with_branch())
        evader.choose(0, "e1", {"p1": "E"})
        decision = evader.choose(1, "e_dead", {"p1": "E"})
        self.assertTrue(decision.entered_dead_end)
        self.assertIsNone(decision.chosen)

    def test_not_forced_when_an_escapable_alternative_existed(self):
        """The evader chose the cul-de-sac; the pursuers did not force it there."""
        from joint_interception.simulator.evader import (
            EvaderDecision,
            EvaderLevel,
            ScriptedEvader,
        )

        evader = ScriptedEvader(EvaderLevel.RANDOM, 1, line_with_branch())
        # Record the entry decision explicitly, so the case under test is the one intended
        # rather than whichever branch this seed happens to take.
        evader.decisions.append(
            EvaderDecision(0, "e1", ("e_dead", "e_open"), "e_dead", EvaderLevel.RANDOM, "test")
        )
        evader.choose(1, "e_dead", {"p1": "E"})

        forced, reason, detail = evader.was_forced_into_dead_end()
        self.assertFalse(forced)
        self.assertEqual(reason, "an_escapable_alternative_existed_at_entry")
        self.assertEqual(detail["alternatives_with_onward_continuations"], ["e_open"])

    def test_forced_when_every_alternative_was_also_a_dead_end(self):
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader

        evader = ScriptedEvader(EvaderLevel.OPTIMAL_ESCAPE, 9, both_branches_dead())
        first = evader.choose(0, "e1", {"p1": "X"})
        evader.choose(1, first.chosen, {"p1": "X"})
        forced, reason, _ = evader.was_forced_into_dead_end()
        self.assertTrue(forced)
        self.assertEqual(reason, "every_alternative_was_also_a_dead_end")

    def test_no_dead_end_means_no_forced_claim(self):
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader

        evader = ScriptedEvader(EvaderLevel.OPTIMAL_ESCAPE, 2, line_with_branch())
        evader.choose(0, "e1", {"p1": "E"})
        forced, reason, _ = evader.was_forced_into_dead_end()
        self.assertFalse(forced)
        self.assertEqual(reason, "no_dead_end_entry_recorded")


@requires_contracts
class TestInformationBoundaryOfTheEvader(unittest.TestCase):
    def test_choose_receives_only_current_pursuer_positions(self):
        """A-62 adds `pursuer_positions`: each pursuer's CURRENT edge ends and fraction
        covered - the same public, present-tense information as the node, made continuous."""
        import inspect

        from joint_interception.simulator.evader import ScriptedEvader

        parameters = set(inspect.signature(ScriptedEvader.choose).parameters)
        self.assertEqual(
            parameters,
            {"self", "decision_index", "current_edge", "pursuer_nodes", "pursuer_positions"},
        )

    def test_interpolated_input_is_continuous_across_a_node(self):
        from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader
        from joint_interception.simulator.topology import Edge, Topology

        topo = Topology.build(
            [
                Edge("a", "n0", "n1", 100.0),
                Edge("b", "n1", "n2", 100.0),
                Edge("c", "n2", "n3", 100.0),
                Edge("x", "n1", "n4", 50.0),
                Edge("y", "n4", "n2", 50.0),
            ]
        )
        ev = ScriptedEvader(EvaderLevel.OPTIMAL_ESCAPE, 1, topo, input_mode="interpolated")
        ev._positions = {"p1": ("n1", "n2", 1.0)}
        end_of_b = ev._pursuer_distances("x", {})
        ev._positions = {"p1": ("n2", "n3", 0.0)}
        start_of_c = ev._pursuer_distances("x", {})
        self.assertEqual(end_of_b, start_of_c)

    def test_no_future_or_oracle_token_in_the_module(self):
        import inspect

        import joint_interception.simulator.evader as module

        source = inspect.getsource(module).lower()
        for forbidden in ("future_route", "route_file", "ground_truth", "judge"):
            self.assertNotIn(forbidden, source.replace("no route oracle", ""))

    def test_contract_forbids_a_faster_evader(self):
        from joint_interception.domain.contracts import load_domain

        speed = load_domain()["evader"]["speed"]
        self.assertFalse(speed["evader_may_be_faster_than_pursuers"])


if __name__ == "__main__":
    unittest.main()


@requires_contracts
class TestScoreSentinelsDoNotCollide(unittest.TestCase):
    """Unreachable and dead-end are opposite outcomes and must never share a value.

    An earlier version mapped both to -1.0, which made "no pursuer can reach this" — the
    safest outcome — indistinguishable from "this is a cul-de-sac", the worst. The scores
    are written into the decision record, so the collision would have corrupted the audit
    trail as well as the choice.
    """

    def test_the_two_sentinels_differ(self):
        from joint_interception.simulator.evader import DEAD_END_PENALTY, UNREACHABLE_SCORE

        self.assertNotEqual(DEAD_END_PENALTY, UNREACHABLE_SCORE)
        self.assertLess(DEAD_END_PENALTY, 0.0)
        self.assertGreater(UNREACHABLE_SCORE, 0.0)

    def test_unreachable_scores_high_not_low(self):
        from joint_interception.simulator.evader import (
            UNREACHABLE_SCORE,
            EvaderLevel,
            ScriptedEvader,
        )

        # Pursuer at D, which is unreachable from C, so e_open must score maximally safe.
        evader = ScriptedEvader(EvaderLevel.OPTIMAL_ESCAPE, 0, line_with_branch())
        decision = evader.choose(0, "e1", {"p1": "D"})
        self.assertEqual(decision.chosen, "e_open")
        self.assertEqual(decision.scores["e_open"], UNREACHABLE_SCORE)

    def test_dead_end_scores_below_every_real_distance(self):
        from joint_interception.simulator.evader import (
            DEAD_END_PENALTY,
            EvaderLevel,
            ScriptedEvader,
        )

        evader = ScriptedEvader(EvaderLevel.OPTIMAL_ESCAPE, 0, line_with_branch())
        decision = evader.choose(0, "e1", {"p1": "D"})
        self.assertEqual(decision.scores["e_dead"], DEAD_END_PENALTY)
        self.assertLess(decision.scores["e_dead"], decision.scores["e_open"])


@requires_contracts
class TestDifficultyOrderingIsMonotone(unittest.TestCase):
    """The dead-end rate must fall as the level rises, or the knob is not a difficulty knob.

    This property was BROKEN and measurement caught it. Level 2 scored a cul-de-sac as
    maximally safe, because graph distance says no pursuer can reach it, and so entered dead
    ends 75.5% of the time against 47% for level 1 — the supposedly harder level was easier
    for the pursuers. The fix was to share the dead-end penalty across levels 2 and 3.
    """

    TRIALS = 200

    def _dead_end_rate(self, level):
        from joint_interception.simulator.evader import ScriptedEvader

        topology = line_with_branch()
        entered = sum(
            ScriptedEvader(level, seed, topology).choose(0, "e1", {"p1": "E"}).chosen == "e_dead"
            for seed in range(self.TRIALS)
        )
        return entered / self.TRIALS

    def test_dead_end_rate_is_non_increasing_with_level(self):
        from joint_interception.simulator.evader import EvaderLevel

        rates = [self._dead_end_rate(level) for level in EvaderLevel]
        self.assertEqual(
            rates, sorted(rates, reverse=True), f"dead-end rates not monotone: {rates}"
        )

    def test_level_2_is_strictly_better_than_level_1(self):
        from joint_interception.simulator.evader import EvaderLevel

        self.assertLess(
            self._dead_end_rate(EvaderLevel.AVOIDANT),
            self._dead_end_rate(EvaderLevel.RANDOM),
        )

    def test_level_3_never_enters_a_dead_end_when_an_alternative_exists(self):
        from joint_interception.simulator.evader import EvaderLevel

        self.assertEqual(self._dead_end_rate(EvaderLevel.OPTIMAL_ESCAPE), 0.0)

    def test_level_2_remains_suboptimal(self):
        """If level 2 matched level 3 it would not be a distinct level."""
        from joint_interception.simulator.evader import EvaderLevel

        self.assertGreater(self._dead_end_rate(EvaderLevel.AVOIDANT), 0.0)
