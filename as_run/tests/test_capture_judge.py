"""Capture judge: geometry, the dwell boundary and the derived predicate properties.

Expected values are derived by hand in the docstrings and comments, from
configs/domain_v1.json, not from the implementation's output.
"""

from __future__ import annotations

import math
import unittest

from _support import load_config  # noqa: F401,E402
from _w2_support import requires_contracts  # noqa: E402


@requires_contracts
class TestBodyGeometry(unittest.TestCase):
    """Body separation must be geometric, not centre distance.

    Obligation O22 recorded a native collision at a reported positive body gap of 1.959 m
    because separation came from station arithmetic rather than geometry.
    """

    def setUp(self):
        from joint_interception.domain.geometry import Rectangle

        self.Rectangle = Rectangle

    def test_side_by_side(self):
        """Centres 3.0 m apart laterally, width 1.8 -> separation 3.0 - 1.8 = 1.2."""
        from joint_interception.domain.geometry import body_separation_m

        a = self.Rectangle(0.0, 0.0, 0.0, 5.0, 1.8)
        b = self.Rectangle(0.0, 3.0, 0.0, 5.0, 1.8)
        self.assertAlmostEqual(body_separation_m(a, b), 1.2, places=9)

    def test_in_line(self):
        """Centres 6.0 m apart along heading, length 5.0 -> separation 6.0 - 5.0 = 1.0."""
        from joint_interception.domain.geometry import body_separation_m

        a = self.Rectangle(0.0, 0.0, 0.0, 5.0, 1.8)
        b = self.Rectangle(6.0, 0.0, 0.0, 5.0, 1.8)
        self.assertAlmostEqual(body_separation_m(a, b), 1.0, places=9)

    def test_overlap_returns_zero(self):
        """Centres 4.0 m apart along heading with length 5.0 -> bodies overlap."""
        from joint_interception.domain.geometry import body_separation_m, rectangles_overlap

        a = self.Rectangle(0.0, 0.0, 0.0, 5.0, 1.8)
        b = self.Rectangle(4.0, 0.0, 0.0, 5.0, 1.8)
        self.assertTrue(rectangles_overlap(a, b))
        self.assertEqual(body_separation_m(a, b), 0.0)

    def test_perpendicular(self):
        """A spans y in [-0.9, 0.9]; B rotated 90 deg at y=4.0 spans y in [1.5, 6.5].

        Their x ranges overlap, so the separation is 1.5 - 0.9 = 0.6.
        """
        from joint_interception.domain.geometry import body_separation_m

        a = self.Rectangle(0.0, 0.0, 0.0, 5.0, 1.8)
        b = self.Rectangle(0.0, 4.0, math.pi / 2, 5.0, 1.8)
        self.assertAlmostEqual(body_separation_m(a, b), 0.6, places=9)

    def test_separation_is_symmetric(self):
        from joint_interception.domain.geometry import body_separation_m

        a = self.Rectangle(1.0, 2.0, 0.4, 5.0, 1.8)
        b = self.Rectangle(7.0, 3.0, -1.1, 5.0, 1.8)
        self.assertAlmostEqual(body_separation_m(a, b), body_separation_m(b, a), places=12)

    def test_heading_difference_wraps(self):
        """Headings near +pi and -pi describe almost the same direction."""
        from joint_interception.domain.geometry import heading_difference_rad

        self.assertAlmostEqual(
            heading_difference_rad(math.pi - 0.01, -math.pi + 0.01), 0.02, places=9
        )
        self.assertAlmostEqual(heading_difference_rad(0.0, math.pi / 2), math.pi / 2, places=9)


@requires_contracts
class TestCaptureParameters(unittest.TestCase):
    def test_parameters_are_self_consistent(self):
        from joint_interception.domain.contracts import CaptureParameters

        self.assertEqual(CaptureParameters.from_domain().consistency_problems(), [])

    def test_parameters_are_frozen_by_the_research_lead(self):
        """D06 was resolved on 2026-09-21.

        This test previously asserted the OPPOSITE — that the code must not claim a freeze
        that had not happened — and it failed the moment the freeze was recorded, which is
        what it was for. It is inverted rather than deleted so the freeze itself is guarded:
        silently reverting the configuration to PROPOSED would now fail here.
        """
        from joint_interception.domain.contracts import CaptureParameters, load_domain

        self.assertTrue(CaptureParameters.from_domain().frozen)
        self.assertEqual(load_domain()["capture_predicate"]["status"], "FROZEN")

    def test_the_resolved_reading_is_contact_to_stop_not_moving_containment(self):
        """Moving containment was explicitly REJECTED: it reproduces the caging endpoint."""
        from joint_interception.domain.contracts import CaptureParameters, load_domain

        predicate = load_domain()["capture_predicate"]
        self.assertEqual(predicate["reading"], "CONTACT_TO_STOP")
        self.assertIn("MOVING CONTAINMENT IS REJECTED", predicate["reading_rationale"])
        # The bound must be low enough to exclude a slow roll, not merely a slow drive.
        self.assertLessEqual(CaptureParameters.from_domain().capture_speed_max_mps, 1.0)

    def test_contact_alone_is_not_capture_coordination_is_required(self):
        from joint_interception.domain.contracts import load_domain

        requirement = load_domain()["capture_predicate"]["coordination_requirement"]
        self.assertEqual(requirement["status"], "FROZEN")
        self.assertIn("NOT capture", requirement["statement"])
        self.assertTrue(requirement["dead_end_rule"]["captures_in_a_cul_de_sac_are_admissible"])
        self.assertIn("FORCED", requirement["dead_end_rule"]["but_count_as_coordinated_only_if"])

    def test_uncoordinated_captures_are_excluded_from_the_primary_outcome(self):
        from joint_interception.domain.contracts import load_domain

        domain = load_domain()
        for cause in ("CAPTURE_UNCOORDINATED_DEAD_END", "CAPTURE_UNCOORDINATED_SINGLE_PURSUER"):
            self.assertIn(cause, domain["endpoint_causes"])
            self.assertIn(cause, domain["endpoint_reporting_rule"])
        self.assertIn("excluded from the primary outcome", domain["endpoint_reporting_rule"])

    def test_ordinary_following_is_excluded_by_construction(self):
        """contact_gap_max_m must sit below the ordinary following gap measured in O26."""
        from joint_interception.domain.contracts import CaptureParameters, load_domain

        params = CaptureParameters.from_domain()
        min_gap = load_domain()["vehicle"]["min_gap_m"]
        self.assertLess(params.contact_gap_max_m, min_gap)
        # The historical O26 minimum prey/pursuer body gaps, measured over four episodes.
        for measured in (2.5009, 2.5016):
            self.assertGreater(measured, params.contact_gap_max_m)

    def test_monotone_traversal_cannot_satisfy_dwell(self):
        """band_width / relative_speed_max must be strictly less than the dwell."""
        from joint_interception.domain.contracts import CaptureParameters

        params = CaptureParameters.from_domain()
        band = params.contact_gap_max_m - params.contact_gap_min_m
        self.assertAlmostEqual(band, 1.70, places=9)
        self.assertLess(band / params.relative_speed_max_mps, params.dwell_time_s)

    def test_inconsistent_parameter_set_is_rejected(self):
        """A parameter set that would admit ordinary following must be refused."""
        from joint_interception.domain.contracts import CaptureParameters

        bad = CaptureParameters(
            contact_gap_min_m=0.30,
            contact_gap_max_m=3.00,
            capture_speed_max_mps=2.0,
            relative_speed_max_mps=1.0,
            orientation_tolerance_rad=0.2618,
            dwell_time_s=2.0,
            geometry_tolerance_m=0.01,
            frozen=False,
        )
        problems = bad.consistency_problems()
        self.assertTrue(any("min_gap_m" in p for p in problems), problems)


def _frames(count, step=0.1, gap=1.2, speed=1.0, start_index=0, evader_x=0.0):
    """Build `count` consecutive frames in which the conditions hold.

    The pursuer is AHEAD of the evader in file with a 1.2 m bumper gap, inside [0.30, 2.00];
    both speeds 1.0 <= 2.00; relative speed 0; heading difference 0; lateral offset 0. Until
    A-57 this fixture placed the pursuer BESIDE the evader - the geometry A-57 excludes.
    """
    from joint_interception.evaluation.capture_judge import TraceFrame, VehicleFrame

    out = []
    for i in range(count):
        t = round((start_index + i) * step, 9)
        out.append(
            TraceFrame(
                time_s=t,
                vehicles={
                    "e1": VehicleFrame("e1", evader_x, 0.0, 0.0, speed, 5.0, 1.8),
                    "p1": VehicleFrame("p1", evader_x + 5.0 + gap, 0.0, 0.0, speed, 5.0, 1.8),
                },
            )
        )
    return out


@requires_contracts
class TestCaptureJudgeDwellBoundary(unittest.TestCase):
    """A run of k consecutive frames covers (k-1) * 0.1 s. The dwell is 2.0 s.

    So k = 20 gives 1.9 s and must fail; k = 21 gives exactly 2.0 s and must pass.
    """

    def setUp(self):
        from joint_interception.domain.contracts import CaptureParameters

        self.params = CaptureParameters.from_domain()
        self.step = 0.1

    def _judge(self, trace, **kwargs):
        from joint_interception.evaluation.capture_judge import judge_capture

        return judge_capture(trace, "e1", self.params, self.step, **kwargs)

    def test_twenty_frames_is_one_point_nine_seconds_and_fails(self):
        from joint_interception.opportunities.types import Verdict

        verdict = self._judge(_frames(20))
        self.assertEqual(verdict.verdict, Verdict.REJECTED)
        self.assertAlmostEqual(verdict.longest_run_s, 1.9, places=9)

    def test_twenty_one_frames_is_exactly_two_seconds_and_passes(self):
        from joint_interception.opportunities.types import Verdict

        verdict = self._judge(_frames(21))
        self.assertEqual(verdict.verdict, Verdict.SUPPORTED)
        self.assertAlmostEqual(verdict.witness_duration_s, 2.0, places=9)
        self.assertEqual(verdict.finisher, "p1")

    def test_ordinary_following_at_the_o26_gap_is_not_capture(self):
        """Body gap 2.5009 m, the historical measured following distance."""
        from joint_interception.evaluation.capture_judge import TraceFrame, VehicleFrame
        from joint_interception.opportunities.types import Verdict

        trace = []
        for i in range(60):
            trace.append(
                TraceFrame(
                    time_s=round(i * 0.1, 9),
                    vehicles={
                        "e1": VehicleFrame("e1", 0.0, 0.0, 0.0, 1.0, 5.0, 1.8),
                        # In line, centres 5.0 + 2.5009 apart -> body gap 2.5009.
                        "p1": VehicleFrame("p1", -7.5009, 0.0, 0.0, 1.0, 5.0, 1.8),
                    },
                )
            )
        self.assertEqual(self._judge(trace).verdict, Verdict.REJECTED)

    def test_monotone_fly_through_cannot_satisfy_dwell(self):
        """Closing from 2.0 m to 0.30 m at 1.0 m/s takes 1.7 s, short of the 2.0 s dwell."""
        from joint_interception.evaluation.capture_judge import TraceFrame, VehicleFrame
        from joint_interception.opportunities.types import Verdict

        trace = []
        for i in range(40):
            t = round(i * 0.1, 9)
            lateral = 1.8 + 2.00 - 1.0 * t  # body gap starts at 2.00 and closes at 1 m/s
            trace.append(
                TraceFrame(
                    time_s=t,
                    vehicles={
                        "e1": VehicleFrame("e1", 0.0, 0.0, 0.0, 1.0, 5.0, 1.8),
                        "p1": VehicleFrame("p1", 0.0, lateral, 0.0, 2.0, 5.0, 1.8),
                    },
                )
            )
        verdict = self._judge(trace)
        self.assertEqual(verdict.verdict, Verdict.REJECTED)
        self.assertLess(verdict.longest_run_s, self.params.dwell_time_s)

    def test_role_cannot_pass_between_pursuers_mid_witness(self):
        """Two pursuers holding 11 frames each is 2.1 s in total but neither alone reaches 2.0 s."""
        from joint_interception.evaluation.capture_judge import TraceFrame, VehicleFrame
        from joint_interception.opportunities.types import Verdict

        far, near = 30.0, 3.0
        trace = []
        for i in range(22):
            t = round(i * 0.1, 9)
            p1_lateral = near if i < 11 else far
            p2_lateral = far if i < 11 else near
            trace.append(
                TraceFrame(
                    time_s=t,
                    vehicles={
                        "e1": VehicleFrame("e1", 0.0, 0.0, 0.0, 1.0, 5.0, 1.8),
                        "p1": VehicleFrame("p1", 0.0, p1_lateral, 0.0, 1.0, 5.0, 1.8),
                        "p2": VehicleFrame("p2", 0.0, p2_lateral, 0.0, 1.0, 5.0, 1.8),
                    },
                )
            )
        verdict = self._judge(trace)
        self.assertEqual(verdict.verdict, Verdict.REJECTED)
        self.assertLessEqual(max(verdict.per_pursuer_longest_run_s.values()), 1.1)

    def test_missing_frame_yields_unknown_not_zero(self):
        from joint_interception.opportunities.types import Verdict

        trace = _frames(30)
        del trace[10]
        verdict = self._judge(trace)
        self.assertEqual(verdict.verdict, Verdict.UNKNOWN)
        self.assertEqual(verdict.reason, "trace_has_missing_frames")

    def test_incomplete_trace_yields_unknown(self):
        from joint_interception.opportunities.types import Verdict

        verdict = self._judge(_frames(30), trace_is_complete=False)
        self.assertEqual(verdict.verdict, Verdict.UNKNOWN)

    def test_empty_trace_yields_unknown(self):
        from joint_interception.opportunities.types import Verdict

        self.assertEqual(self._judge([]).verdict, Verdict.UNKNOWN)

    def test_safety_failure_inside_the_interval_invalidates_the_witness(self):
        from joint_interception.opportunities.types import Verdict

        trace = _frames(21)
        verdict = self._judge(trace, safety_failure_times_s=frozenset({1.0}))
        self.assertEqual(verdict.verdict, Verdict.REJECTED)

    def test_evader_above_speed_bound_is_not_capture(self):
        from joint_interception.opportunities.types import Verdict

        self.assertEqual(self._judge(_frames(40, speed=2.5)).verdict, Verdict.REJECTED)


if __name__ == "__main__":
    unittest.main()


@requires_contracts
class TestEvaderIsAScriptedDifficultyLevel(unittest.TestCase):
    """D08 was resolved as three scripted levels, not a policy to be learned or justified."""

    def setUp(self):
        from joint_interception.domain.contracts import load_domain

        self.evader = load_domain()["evader"]

    def test_three_declared_levels(self):
        self.assertEqual(self.evader["status"], "FROZEN_2026_09_21")
        self.assertEqual(self.evader["model"], "SCRIPTED_DIFFICULTY_LEVEL")
        self.assertEqual(
            [level["name"] for level in self.evader["levels"]],
            ["RANDOM", "AVOIDANT", "OPTIMAL_ESCAPE"],
        )
        self.assertEqual([level["level"] for level in self.evader["levels"]], [1, 2, 3])

    def test_determinism_is_required(self):
        """The assistance audit needs a reproducible prefix, not only replicable experiments."""
        self.assertTrue(self.evader["determinism"]["required"])

    def test_the_evader_may_not_be_faster_than_the_pursuers(self):
        self.assertFalse(self.evader["speed"]["evader_may_be_faster_than_pursuers"])

    def test_an_easier_speed_ratio_must_be_reported(self):
        """A curriculum that slows the evader makes the task easier, not the method better."""
        self.assertIn("declared scenario parameter", self.evader["speed"]["curriculum_note"])
        self.assertIn("not a better method", self.evader["speed"]["curriculum_note"])

    def test_no_future_route_oracle(self):
        self.assertTrue(self.evader["route_exhaustion"]["no_future_route_oracle"])


class TestAlignmentA57(unittest.TestCase):
    """A-57: the evader must be held BEHIND the finisher, in file."""

    def _judge(self, pursuer_x, pursuer_y):
        from joint_interception.domain.contracts import CaptureParameters, load_domain
        from joint_interception.evaluation.capture_judge import (
            TraceFrame,
            VehicleFrame,
            judge_capture,
        )

        frames = [
            TraceFrame(
                round(i * 0.1, 9),
                {
                    "e1": VehicleFrame("e1", 0.0, 0.0, 0.0, 0.0, 5.0, 1.8),
                    "p1": VehicleFrame("p1", pursuer_x, pursuer_y, 0.0, 0.0, 5.0, 1.8),
                },
            )
            for i in range(30)
        ]
        return judge_capture(frames, "e1", CaptureParameters.from_domain(load_domain()), 0.1)

    def test_in_file_ahead_is_a_capture(self):
        self.assertEqual(self._judge(6.2, 0.0).verdict.value, "SUPPORTED")

    def test_side_by_side_in_adjacent_lanes_is_not(self):
        """Stopped abreast at a light: lateral gap 3.0 - 1.8 = 1.2 m, inside the band."""
        self.assertEqual(self._judge(0.0, 3.0).verdict.value, "REJECTED")

    def test_pursuer_behind_the_evader_is_not(self):
        self.assertEqual(self._judge(-6.2, 0.0).verdict.value, "REJECTED")
