"""O27 construction search: verification and the two coordination contrasts (A-49).

Uses the synthetic junction WITH cycles from the O27 package's positive control. A first
control without cycles left the evader ignoring every pursuer, so no helper could matter.
"""

from __future__ import annotations

import unittest

from _support import ROOT  # noqa: F401
from joint_interception.domain.contracts import load_domain  # noqa: E402
from joint_interception.evaluation.capture_judge import judge_capture  # noqa: E402
from joint_interception.simulator.evader import EvaderLevel  # noqa: E402
from joint_interception.world.construction import (  # noqa: E402
    Constructor,
    Plan,
    Scenario,
    Segment,
)
from joint_interception.world.network import EdgeInfo, GraphNetwork, Link  # noqa: E402

DOMAIN = load_domain()


def edge(i, f, t, length, x0, y0, x1, y1):
    return EdgeInfo(i, f, t, length, 1, 13.89, ((x0, y0), (x1, y1)))


def network() -> GraphNetwork:
    edges = {
        "D": edge("D", "n0", "N", 150, 0, 0, 150, 0),
        "E": edge("E", "N", "M", 100, 160, 0, 260, 0),
        "E2": edge("E2", "M", "n0", 120, 260, 10, 0, 10),
        "X": edge("X", "N", "Q", 100, 150, 10, 150, 110),
        "X2": edge("X2", "Q", "n0", 400, 150, 120, 0, 20),
        "F": edge("F", "f0", "N", 120, 150, -130, 150, -10),
        "G": edge("G", "g0", "N", 120, 20, 40, 145, 5),
    }
    pairs = [
        ("D", "E"),
        ("D", "X"),
        ("F", "E"),
        ("F", "X"),
        ("G", "X"),
        ("G", "E"),
        ("E", "E2"),
        ("X", "X2"),
        ("E2", "D"),
        ("X2", "D"),
    ]
    return GraphNetwork(edges, {p: Link(*p, 8.0, 8.0, (), None) for p in pairs}, {})


def constructor(level, helper_start=("G", 60.0, 10.0)) -> Constructor:
    scenario = Scenario(
        "control", level, 7, ("D", 10.0, 6.9), {"p1": ("F", 10.0, 0.0), "p2": helper_start}
    )
    # The EXPANSION cap must be the binding one here. The search also stops on CPU time,
    # and a time cutoff makes the result depend on machine speed: a determinism test under
    # a binding time cap would be testing the machine.
    return Constructor(network(), scenario, DOMAIN, 250, 100_000)


class TestTheEvaderIsSteerableHere(unittest.TestCase):
    """Without cycles every exit scores 'unreachable' and no helper can matter."""

    def test_a_helper_covering_the_natural_choice_changes_it(self):
        c = constructor(EvaderLevel.OPTIMAL_ESCAPE)
        natural = c.simulate(Plan()).evader.decisions[0].chosen
        covered = Plan({"p2": [Segment(0, natural, 12.0)]})
        steered = c.simulate(covered).evader.decisions[0].chosen
        self.assertNotEqual(natural, steered)


class TestVerificationAndContrasts(unittest.TestCase):
    def test_a_single_pursuer_capture_is_never_constructed(self):
        """The case that exposed the b1-only rule: one pursuer suffices, b1 disrupts."""
        c = constructor(EvaderLevel.AVOIDANT)
        plan = Plan(
            {"p1": [Segment(0, "F", None), Segment(7, "X", 10.0)], "p2": [Segment(0, "E", 12.0)]}
        )
        result = c.verify(plan)
        self.assertEqual(result["factual"]["judge"], "SUPPORTED")
        self.assertTrue(result["factual"]["deterministic"])
        self.assertEqual(result["factual"]["collisions"], [])
        self.assertEqual(result["necessity"]["helper_never_acts_judge"], "SUPPORTED")
        self.assertNotEqual(result["verdict"], "CONSTRUCTED")

    def test_disruption_by_the_substitute_is_named_not_counted(self):
        c = constructor(EvaderLevel.AVOIDANT)
        plan = Plan(
            {"p1": [Segment(0, "F", None), Segment(7, "X", 10.0)], "p2": [Segment(0, "E", 12.0)]}
        )
        result = c.verify(plan)
        if result["counterfactual"]["judge"] == "REJECTED":
            self.assertEqual(result["verdict"], "B1_CONTRAST_WITHOUT_NECESSITY")


class TestTheSearchReportsWhatItFound(unittest.TestCase):
    def test_verified_captures_are_never_reported_as_no_witness(self):
        c = constructor(EvaderLevel.OPTIMAL_ESCAPE)
        result = c.search()
        verified = sum(v for k, v in result["tally"].items() if k != "FACTUAL_FAILED_VERIFICATION")
        if verified:
            self.assertNotEqual(result["verdict"], "NO_WITNESS_WITHIN_CAP")

    def test_the_search_is_deterministic(self):
        first = constructor(EvaderLevel.AVOIDANT).search()
        second = constructor(EvaderLevel.AVOIDANT).search()
        self.assertEqual(first["verdict"], second["verdict"])
        self.assertEqual(first["tally"], second["tally"])


class TestTheJudgeRemainsIndependent(unittest.TestCase):
    def test_the_verdict_comes_from_the_trace_not_the_world_watch(self):
        c = constructor(EvaderLevel.AVOIDANT)
        plan = Plan(
            {"p1": [Segment(0, "F", None), Segment(7, "X", 10.0)], "p2": [Segment(0, "E", 12.0)]}
        )
        world = c.simulate(plan, record=True)
        verdict = judge_capture(world.trace, "e1", c.params, c.step_s)
        self.assertEqual(verdict.verdict.value, c.verify(plan)["factual"]["judge"])


if __name__ == "__main__":
    unittest.main()


class TestSettlingTime(unittest.TestCase):
    """D12 revised (A-51): the b1 window ends when the helper took its position."""

    @staticmethod
    def trace(positions_and_speeds):
        from joint_interception.evaluation.capture_judge import TraceFrame, VehicleFrame

        return [
            TraceFrame(round(i * 0.1, 6), {"h": VehicleFrame("h", x, 0.0, 0.0, v, 5.0, 1.8)})
            for i, (x, v) in enumerate(positions_and_speeds)
        ]

    def test_a_helper_moving_at_the_witness_reduces_to_the_original_rule(self):
        from joint_interception.world.construction import settling_time_s

        tr = self.trace([(i * 0.5, 5.0) for i in range(100)])
        self.assertEqual(settling_time_s(tr, "h", 9.9), 9.9)

    def test_a_helper_that_stopped_early_settles_when_it_stopped(self):
        from joint_interception.world.construction import settling_time_s

        moving = [(i * 1.0, 10.0) for i in range(30)]
        stopped = [(29.0, 0.0)] * 70
        tr = self.trace(moving + stopped)
        settle = settling_time_s(tr, "h", 9.9)
        self.assertLess(settle, 3.0)
        self.assertGreaterEqual(settle, 2.8)

    def test_drift_under_one_metre_does_not_unsettle(self):
        from joint_interception.world.construction import settling_time_s

        tr = self.trace([(0.0, 0.0)] * 50 + [(0.5, 0.0)] * 50)
        self.assertEqual(settling_time_s(tr, "h", 9.9), 0.0)


class TestMovingStartsAreAdmissible(unittest.TestCase):
    def test_r02_starts_can_stop_by_the_edge_end_and_r01_starts_are_unchanged(self):
        from joint_interception.world.construction import ORDINARY_DECEL, _moving_start

        info = EdgeInfo("x", "n0", "n1", 30.87, 1, 27.78, ((0.0, 0.0), (30.87, 0.0)))
        edge, offset, speed = _moving_start(info, "r02")
        self.assertLessEqual(speed**2 / (2 * ORDINARY_DECEL), info.length_m - offset - 0.5)
        self.assertEqual(_moving_start(info, ""), ("x", 10.0, 0.5 * 27.78))
