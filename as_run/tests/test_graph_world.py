"""The declared model for O27. It must reproduce what SUMO measured before it is searched.

A-46 measured in SUMO: a pursuer trailing a stopped evader rests at 2.501 m; an evader
behind a stopped pursuer rests at 1.001 m. A model that disagrees is a different model.
"""

from __future__ import annotations

import unittest

from _support import ROOT  # noqa: F401
from joint_interception.domain.contracts import CaptureParameters, load_domain  # noqa: E402
from joint_interception.evaluation.capture_judge import judge_capture  # noqa: E402
from joint_interception.opportunities.approach import SignalProgram  # noqa: E402
from joint_interception.opportunities.types import Verdict  # noqa: E402
from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader  # noqa: E402
from joint_interception.world.network import EdgeInfo, GraphNetwork, Link  # noqa: E402
from joint_interception.world.simulation import Vehicle, World  # noqa: E402

DOMAIN = load_domain()
PARAMS = {k: v["value"] for k, v in DOMAIN["capture_predicate"]["parameters"].items()}


def line_net(lanes: int = 1, signal: SignalProgram | None = None) -> GraphNetwork:
    """a -> b -> c, straight along x, 200 m each."""
    edges = {
        "a": EdgeInfo("a", "n0", "n1", 200.0, lanes, 13.89, ((0.0, 0.0), (200.0, 0.0))),
        "b": EdgeInfo("b", "n1", "n2", 200.0, lanes, 13.89, ((200.0, 0.0), (400.0, 0.0))),
        "c": EdgeInfo("c", "n2", "n3", 200.0, lanes, 13.89, ((400.0, 0.0), (600.0, 0.0))),
    }
    sig = ("t0", 0) if signal else None
    links = {
        ("a", "b"): Link("a", "b", 0.0, 13.89, (), sig),
        ("b", "c"): Link("b", "c", 0.0, 13.89, (), None),
    }
    return GraphNetwork(edges, links, {"t0": signal} if signal else {})


def vehicle(vid, klass, edge, offset, speed=0.0, route=None, hold=None):
    gap = 2.5 if klass == "pursuer" else 1.0
    return Vehicle(vid, klass, 5.0, 1.8, gap, edge, offset, speed, route=route or [], hold=hold)


def world(net, vehicles, record=False):
    evader = ScriptedEvader(EvaderLevel.AVOIDANT, 1, net.topology())
    return World(
        net,
        {v.vid: v for v in vehicles},
        evader,
        "e1",
        0.1,
        1.0,
        2.6,
        4.5,
        PARAMS,
        record_trace=record,
    )


class TestItReproducesTheSumoMeasurements(unittest.TestCase):
    def test_a_trailing_pursuer_rests_at_its_min_gap(self):
        net = line_net()
        w = world(
            net,
            [
                vehicle("e1", "evader", "a", 120.0, hold=("a", 120.0)),
                vehicle("p1", "pursuer", "a", 60.0, speed=5.0),
            ],
        )
        w.vehicles["e1"].stuck = True
        w.run(40.0)
        gap = w.vehicles["e1"].offset - 5.0 - w.vehicles["p1"].offset
        self.assertAlmostEqual(gap, 2.5, delta=0.05)
        self.assertGreater(gap, PARAMS["contact_gap_max_m"])

    def test_an_evader_behind_a_stopped_pursuer_rests_inside_the_band(self):
        net = line_net()
        w = world(
            net,
            [
                vehicle("p1", "pursuer", "a", 120.0, hold=("a", 120.0)),
                vehicle("e1", "evader", "a", 60.0, speed=5.0, route=["b"]),
            ],
            record=True,
        )
        w.run(60.0)
        gap = w.vehicles["p1"].offset - 5.0 - w.vehicles["e1"].offset
        self.assertAlmostEqual(gap, 1.0, delta=0.05)
        self.assertIsNotNone(w.captured_at_s)
        verdict = judge_capture(w.trace, "e1", CaptureParameters.from_domain(DOMAIN), 0.1)
        self.assertIs(verdict.verdict, Verdict.SUPPORTED)
        self.assertEqual(w.collisions, [])
        self.assertEqual(w.safety_failures, [])


class TestDeclaredLimitations(unittest.TestCase):
    def test_a_stopped_vehicle_does_not_block_a_multi_lane_edge(self):
        """Declared: no capture may be claimed from blocking a multi-lane edge."""
        net = line_net(lanes=2)
        w = world(
            net,
            [
                vehicle("p1", "pursuer", "a", 120.0, hold=("a", 120.0)),
                vehicle("e1", "evader", "a", 60.0, speed=5.0, route=["b"]),
            ],
        )
        w.run(40.0)
        self.assertNotEqual(w.vehicles["e1"].edge, "a")
        self.assertIsNone(w.captured_at_s)


class TestSignalsAndHolds(unittest.TestCase):
    """The red-signal test caught a real defect: a vehicle brought EXACTLY to the stop line
    was treated as having crossed it, and drove through the red."""

    def test_a_red_signal_holds_the_vehicle_at_the_line(self):
        red_then_green = SignalProgram("t0", (30.0, 30.0), ("r", "G"))
        net = line_net(signal=red_then_green)
        w = world(net, [vehicle("p1", "pursuer", "a", 150.0, speed=10.0, route=["b", "c"])])
        w.run(20.0)
        self.assertEqual(w.vehicles["p1"].edge, "a")
        self.assertAlmostEqual(w.vehicles["p1"].offset, 200.0, delta=0.5)
        w.run(45.0)
        self.assertNotEqual(w.vehicles["p1"].edge, "a")

    def test_a_hold_across_the_next_link_needs_no_emergency_braking(self):
        net = line_net()
        w = world(
            net, [vehicle("p1", "pursuer", "a", 150.0, speed=13.89, route=["b"], hold=("b", 15.0))]
        )
        w.run(30.0)
        self.assertEqual(w.vehicles["p1"].edge, "b")
        self.assertAlmostEqual(w.vehicles["p1"].offset, 15.0, delta=0.3)
        self.assertEqual(w.safety_failures, [])


class TestDeterminism(unittest.TestCase):
    def test_two_runs_produce_identical_traces(self):
        def run_once():
            net = line_net()
            w = world(
                net,
                [
                    vehicle("p1", "pursuer", "a", 120.0, hold=("a", 120.0)),
                    vehicle("e1", "evader", "a", 30.0, speed=8.0, route=["b"]),
                ],
                record=True,
            )
            w.run(40.0)
            return [
                (f.time_s, tuple(sorted((k, v.x, v.y, v.speed_mps) for k, v in f.vehicles.items())))
                for f in w.trace
            ]

        self.assertEqual(run_once(), run_once())


if __name__ == "__main__":
    unittest.main()


class TestDefectsFoundInBaselinesStayFixed(unittest.TestCase):
    """Each of these produced spurious or real emergency braking in a scenario baseline."""

    def test_a_slow_internal_lane_is_anticipated(self):
        edges = {
            "a": EdgeInfo("a", "n0", "n1", 200.0, 1, 13.89, ((0.0, 0.0), (200.0, 0.0))),
            "b": EdgeInfo("b", "n1", "n2", 200.0, 1, 13.89, ((210.0, 0.0), (410.0, 0.0))),
        }
        net = GraphNetwork(
            edges, {("a", "b"): Link("a", "b", 10.0, 3.0, ((200.0, 0.0), (210.0, 0.0)), None)}, {}
        )
        w = world(net, [vehicle("p1", "pursuer", "a", 50.0, speed=13.89, route=["b"])])
        w.run(40.0)
        self.assertEqual(w.safety_failures, [])

    def test_a_moving_leader_is_not_treated_as_a_wall(self):
        net = line_net()
        w = world(
            net,
            [
                vehicle("p1", "pursuer", "a", 40.0, speed=11.0, route=["b", "c"]),
                vehicle("p2", "pursuer", "a", 20.0, speed=11.0, route=["b", "c"]),
            ],
        )
        w.run(20.0)
        self.assertEqual(w.safety_failures, [])

    def test_the_dilemma_zone_proceeds_on_yellow(self):
        """Green until 10 s, then yellow: a fast vehicle 4 m short of the line cannot stop."""
        program = SignalProgram("t0", (10.0, 3.0, 30.0), ("G", "y", "r"))
        net = line_net(signal=program)
        w = world(net, [vehicle("p1", "pursuer", "a", 60.0, speed=13.89, route=["b", "c"])])
        w.run(15.0)
        self.assertEqual(w.safety_failures, [])
        self.assertNotEqual(w.vehicles["p1"].edge, "a")

    def test_red_is_never_run(self):
        program = SignalProgram("t0", (60.0, 60.0), ("r", "G"))
        net = line_net(signal=program)
        w = world(net, [vehicle("p1", "pursuer", "a", 60.0, speed=13.89, route=["b", "c"])])
        w.run(30.0)
        self.assertEqual(w.vehicles["p1"].edge, "a")
        self.assertEqual(w.safety_failures, [])


class TestTheEvaderAnticipatesEveryContinuation(unittest.TestCase):
    def test_a_short_edge_before_a_dead_end_needs_no_emergency_braking(self):
        """r02 washington baseline: a 4.9 m edge whose sole exit led to a dead end 27 m on."""
        fast = 27.78
        edges = {
            "a": EdgeInfo("a", "n0", "n1", 300.0, 1, fast, ((0.0, 0.0), (300.0, 0.0))),
            "b": EdgeInfo("b", "n1", "n2", 4.86, 1, fast, ((300.0, 0.0), (304.86, 0.0))),
            "c": EdgeInfo("c", "n2", "n3", 27.0, 1, fast, ((304.86, 0.0), (331.86, 0.0))),
        }
        links = {
            ("a", "b"): Link("a", "b", 0.0, fast, (), None),
            ("b", "c"): Link("b", "c", 0.0, fast, (), None),
        }
        net = GraphNetwork(edges, links, {})
        w = world(net, [vehicle("e1", "evader", "a", 50.0, speed=fast)])
        w.run(30.0)
        self.assertEqual(w.safety_failures, [])
        self.assertEqual(w.vehicles["e1"].edge, "c")


class TestAHoldBeyondAnInternalLaneIsKept(unittest.TestCase):
    def test_a_hold_past_a_long_internal_lane_needs_no_emergency_braking(self):
        """O27 r02 (A-52): the hold dropped out while the vehicle was on the internal lane."""
        edges = {
            "a": EdgeInfo("a", "n0", "n1", 130.0, 1, 13.89, ((0.0, 0.0), (130.0, 0.0))),
            "b": EdgeInfo("b", "n1", "n2", 170.0, 1, 13.89, ((144.44, 0.0), (314.44, 0.0))),
        }
        via = Link("a", "b", 14.44, 13.89, ((130.0, 0.0), (144.44, 0.0)), None)
        net = GraphNetwork(edges, {("a", "b"): via}, {})
        w = world(
            net, [vehicle("p1", "pursuer", "a", 60.0, speed=13.89, route=["b"], hold=("b", 12.0))]
        )
        w.run(30.0)
        self.assertEqual(w.safety_failures, [])
        self.assertEqual(w.vehicles["p1"].edge, "b")
        self.assertAlmostEqual(w.vehicles["p1"].offset, 12.0, delta=0.2)


class TestAMergeYieldNeverDemandsMoreThanOrdinaryBraking(unittest.TestCase):
    def test_a_vehicle_able_to_stop_only_at_the_entry_yields_there(self):
        """O27 r03 (A-54): the yield point sat 0.5 m short of where commitment is judged."""
        edges = {
            "a": EdgeInfo("a", "n0", "n1", 100.0, 1, 13.89, ((0.0, 0.0), (100.0, 0.0))),
            "c": EdgeInfo("c", "n2", "n1", 100.0, 1, 13.89, ((100.0, -100.0), (100.0, -10.0))),
            "b": EdgeInfo("b", "n1", "n3", 100.0, 1, 13.89, ((110.0, 0.0), (210.0, 0.0))),
        }
        links = {
            ("a", "b"): Link("a", "b", 10.0, 13.89, ((100.0, 0.0), (110.0, 0.0)), None),
            ("c", "b"): Link("c", "b", 10.0, 13.89, ((100.0, -10.0), (110.0, 0.0)), None),
        }
        net = GraphNetwork(edges, links, {})
        v = vehicle("p1", "pursuer", "a", 95.0, speed=6.71, route=["b"])
        other = vehicle("p2", "pursuer", "c", 2.0, speed=5.0, route=["b"])
        other.in_link = links[("c", "b")]
        w = world(net, [v, other])
        self.assertAlmostEqual(w._merge_yield(v), 5.0, places=6)
        w.step()
        self.assertEqual(w.safety_failures, [])


class TestRightOfWayLearnedFromSumoOnTrainingMaps(unittest.TestCase):
    """A-47 harness development: rules the model lacked, each measured against SUMO."""

    def _junction(self, minor_state="m", prohibit=True):
        edges = {
            "a": EdgeInfo("a", "n0", "n1", 200.0, 1, 13.89, ((0.0, 0.0), (200.0, 0.0))),
            "c": EdgeInfo("c", "n2", "n1", 200.0, 1, 13.89, ((210.0, -200.0), (210.0, -10.0))),
            "b": EdgeInfo("b", "n1", "n3", 200.0, 1, 13.89, ((210.0, 0.0), (410.0, 0.0))),
        }
        major = Link("c", "b", 10.0, 13.89, ((210.0, -10.0), (210.0, 0.0)), None, "M", ())
        minor = Link(
            "a",
            "b",
            10.0,
            13.89,
            ((200.0, 0.0), (210.0, 0.0)),
            None,
            minor_state,
            (("c", "b"),) if prohibit else (),
        )
        return GraphNetwork(edges, {("a", "b"): minor, ("c", "b"): major}, {})

    def test_a_minor_link_is_approached_at_visibility_speed(self):
        net = self._junction()
        w = world(net, [vehicle("p1", "pursuer", "a", 100.0, speed=13.89, route=["b"])], True)
        speeds = []
        while w.time_s < 20.0:
            w.step()
            v = w.vehicles["p1"]
            if v.edge == "a" and not v.in_link and 200.0 - v.offset <= 4.5:
                speeds.append(v.speed)
        self.assertTrue(speeds)
        # At the visibility point; past it the junction is seen free and SUMO accelerates.
        self.assertLessEqual(speeds[0], (2 * 4.5 * 4.5) ** 0.5 + 2.6 * 0.1 + 0.05)
        self.assertEqual(w.safety_failures, [])

    def test_a_minor_link_yields_to_a_prioritised_foe(self):
        net = self._junction()
        w = world(
            net,
            [
                vehicle("p1", "pursuer", "a", 170.0, speed=6.0, route=["b"]),
                vehicle("p2", "pursuer", "c", 175.0, speed=13.89, route=["b"]),
            ],
        )
        w.run(15.0)
        self.assertEqual(w.collisions, [])
        self.assertEqual(w.safety_failures, [])
        order = sorted(("p1", "p2"), key=lambda vid: -w.vehicles[vid].offset)
        self.assertEqual(order[0], "p2")

    def test_two_vehicles_abreast_enter_one_link_in_file_even_into_a_multi_lane_target(self):
        edges = {
            "a": EdgeInfo("a", "n0", "n1", 100.0, 2, 13.89, ((0.0, 0.0), (100.0, 0.0))),
            "b": EdgeInfo("b", "n1", "n2", 200.0, 2, 13.89, ((110.0, 0.0), (310.0, 0.0))),
        }
        link = Link("a", "b", 10.0, 13.89, ((100.0, 0.0), (110.0, 0.0)), None)
        net = GraphNetwork(edges, {("a", "b"): link}, {})
        p1 = vehicle("p1", "pursuer", "a", 99.0, route=["b"])
        p2 = vehicle("p2", "pursuer", "a", 99.0, route=["b"])
        w = world(net, [p1, p2])
        w.run(20.0)
        self.assertEqual(w.collisions, [])


class TestJunctionKeepClear(unittest.TestCase):
    """X02: SUMO lets no vehicle enter a junction it cannot leave."""

    def test_no_entry_while_a_stopped_vehicle_leaves_no_room_for_the_whole_body(self):
        edges = {
            "a": EdgeInfo("a", "n0", "n1", 200.0, 1, 13.89, ((0.0, 0.0), (200.0, 0.0))),
            "b": EdgeInfo("b", "n1", "n2", 200.0, 1, 13.89, ((210.0, 0.0), (410.0, 0.0))),
        }
        link = Link("a", "b", 10.0, 13.89, ((200.0, 0.0), (210.0, 0.0)), None)
        net = GraphNetwork(edges, {("a", "b"): link}, {})
        blocker = vehicle("p1", "pursuer", "b", 10.0, hold=("b", 10.0))
        mover = vehicle("e1", "evader", "a", 120.0, speed=10.0, route=["b"])
        w = world(net, [blocker, mover])
        w.run(30.0)
        e = w.vehicles["e1"]
        self.assertEqual((e.edge, e.in_link), ("a", None))
        self.assertEqual(w.safety_failures, [])
        self.assertEqual(w.collisions, [])

    def test_entry_when_there_is_room(self):
        edges = {
            "a": EdgeInfo("a", "n0", "n1", 200.0, 1, 13.89, ((0.0, 0.0), (200.0, 0.0))),
            "b": EdgeInfo("b", "n1", "n2", 200.0, 1, 13.89, ((210.0, 0.0), (410.0, 0.0))),
        }
        link = Link("a", "b", 10.0, 13.89, ((200.0, 0.0), (210.0, 0.0)), None)
        net = GraphNetwork(edges, {("a", "b"): link}, {})
        blocker = vehicle("p1", "pursuer", "b", 12.0, hold=("b", 12.0))
        mover = vehicle("e1", "evader", "a", 120.0, speed=10.0, route=["b"])
        w = world(net, [blocker, mover])
        w.run(30.0)
        self.assertEqual(w.vehicles["e1"].edge, "b")
        self.assertEqual(w.collisions, [])
