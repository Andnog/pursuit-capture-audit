"""The standalone audit kit (audit_kit/pursuit_audit): geometry, endpoints, traces, command line,
and agreement with the project's own capture judge on valid traces."""

from __future__ import annotations

import io
import json
import math
import os
import random
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "audit_kit"))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pursuit_audit as pa  # noqa: E402
from pursuit_audit import audits, cli  # noqa: E402
from pursuit_audit.geometry import centre_from_front, heading_from_compass_deg  # noqa: E402

EXAMPLES = os.path.join(ROOT, "audit_kit", "examples")


def body(x, y, heading_deg=0.0, speed=0.0):
    return pa.Body(x, y, math.radians(heading_deg), speed, 5.0, 1.8)


def trace(fn, n=41, step=0.1):
    return [pa.Frame(round(k * step, 9), fn(round(k * step, 9))) for k in range(n)]


class GeometryTest(unittest.TestCase):
    def test_bumper_to_bumper_cars_are_far_apart_centre_to_centre(self):
        a, b = body(0, 0), body(-6, 0)
        self.assertAlmostEqual(pa.body_gap_m(a, b), 1.0)
        self.assertAlmostEqual(math.hypot(a.x - b.x, a.y - b.y), 6.0)

    def test_overlap_is_zero_gap_and_side_by_side_is_lateral_gap(self):
        self.assertEqual(pa.body_gap_m(body(0, 0), body(2, 0.5)), 0.0)
        self.assertAlmostEqual(pa.body_gap_m(body(0, 0), body(0, 3.2)), 1.4)

    def test_heading_wraps_and_conversions(self):
        self.assertAlmostEqual(
            pa.heading_difference_rad(math.radians(179), math.radians(-179)), math.radians(2)
        )
        self.assertAlmostEqual(heading_from_compass_deg(0.0), math.pi / 2)
        self.assertAlmostEqual(heading_from_compass_deg(90.0), 0.0)
        x, y = centre_from_front(2.5, 0.0, 0.0, 5.0)
        self.assertAlmostEqual(x, 0.0)
        self.assertAlmostEqual(body(0, 0).front()[0], 2.5)


class EndpointTest(unittest.TestCase):
    def test_stop_behind_a_pursuer_is_a_capture_at_the_end_of_the_dwell(self):
        frames = trace(lambda t: {"e1": body(-6, 0), "p1": body(0, 0)})
        r = pa.operational_capture(frames, "e1")
        self.assertTrue(r.captured)
        self.assertEqual((r.pursuer, r.witness_start_s, r.capture_time_s), ("p1", 0.0, 2.0))

    def test_passing_in_the_opposite_lane_is_proximity_but_not_capture(self):
        frames = trace(
            lambda t: {"e1": body(-20 + 10 * t, 0, 0, 10), "p1": body(20 - 10 * t, 3.2, 180, 10)}
        )
        self.assertFalse(pa.operational_capture(frames, "e1").captured)
        self.assertTrue(pa.proximity(frames, "e1", 5.0, "body").reached)
        self.assertTrue(pa.proximity(frames, "e1", 5.0, "front").reached)

    def test_pursuer_behind_the_evader_is_not_a_capture(self):
        frames = trace(lambda t: {"e1": body(0, 0), "p1": body(-6, 0)})
        r = pa.operational_capture(frames, "e1")
        self.assertFalse(r.captured)
        self.assertEqual(r.closest_failure, "evader_not_behind_pursuer")

    def test_each_condition_is_enforced(self):
        cases = {
            "gap_above_maximum": {"e1": body(-7.5, 0), "p1": body(0, 0)},
            "gap_below_minimum": {"e1": body(-5.2, 0), "p1": body(0, 0)},
            "evader_moving": {"e1": body(-6, 0, 0, 1.5), "p1": body(0, 0, 0, 1.0)},
            "pursuer_moving": {"e1": body(-6, 0, 0, 0.5), "p1": body(0, 0, 0, 1.5)},
            "headings_differ": {"e1": body(-6, 0, 20), "p1": body(0, 0)},
            "lateral_offset": {"e1": body(-6.2, 1.5), "p1": body(0, 0)},
        }
        for reason, vehicles in cases.items():
            r = pa.operational_capture(trace(lambda t, v=vehicles: v), "e1")
            self.assertFalse(r.captured, reason)
            self.assertEqual(r.closest_failure, reason)

    def test_two_short_contacts_do_not_add_up(self):
        def fn(t):
            near = t < 1.5 or t > 2.0
            return {"e1": body(-6 if near else -9, 0), "p1": body(0, 0)}

        r = pa.operational_capture(trace(fn, n=36), "e1")
        self.assertFalse(r.captured)
        self.assertAlmostEqual(r.longest_run_s, 1.4)

    def test_a_missing_pursuer_breaks_the_witness(self):
        def fn(t):
            out = {"e1": body(-6, 0)}
            if not 1.0 <= t <= 1.2:
                out["p1"] = body(0, 0)
            return out

        r = pa.operational_capture(trace(fn, n=31), "e1")
        self.assertFalse(r.captured)
        self.assertGreater(r.reasons["vehicle_missing"], 0)

    def test_the_witness_does_not_pass_between_pursuers(self):
        def fn(t):
            ahead = "p1" if t < 1.5 else "p2"
            other = "p2" if ahead == "p1" else "p1"
            return {"e1": body(-6, 0), ahead: body(0, 0), other: body(50, 50)}

        self.assertFalse(pa.operational_capture(trace(fn, n=30), "e1").captured)

    def test_the_earliest_completed_dwell_wins(self):
        def fn(t):
            out = {"e1": body(-6, 0), "p9": body(0, 0)}
            out["p1"] = body(0, 0) if t >= 1.0 else body(80, 80)
            return out

        r = pa.operational_capture(trace(fn, n=41), "e1")
        self.assertEqual((r.pursuer, r.capture_time_s), ("p9", 2.0))

    def test_distance_kind_changes_the_proximity_verdict(self):
        frames = trace(lambda t: {"e1": body(-7, 0), "p1": body(0, 0)})
        self.assertTrue(pa.proximity(frames, "e1", 5.0, "body").reached)
        self.assertFalse(pa.proximity(frames, "e1", 5.0, "centre").reached)
        self.assertFalse(pa.proximity(frames, "e1", 5.0, "front").reached)
        with self.assertRaises(ValueError):
            pa.proximity(frames, "e1", 5.0, "bumper")


class TraceTest(unittest.TestCase):
    def test_invalid_values_and_irregular_cadence_are_refused_not_scored(self):
        good = trace(lambda t: {"e1": body(-6, 0), "p1": body(0, 0)})
        nan = list(good)
        nan[5] = pa.Frame(
            nan[5].time_s, {"e1": pa.Body(-6, 0, 0.0, float("nan"), 5.0, 1.8), "p1": body(0, 0)}
        )
        with self.assertRaises(pa.TraceError):
            pa.operational_capture(nan, "e1")
        with self.assertRaises(pa.TraceError):
            pa.operational_capture(good[:10] + good[12:], "e1")
        with self.assertRaises(pa.TraceError):
            pa.validate_trace(good[:1])
        self.assertAlmostEqual(pa.validate_trace(good), 0.1)

    def test_front_position_and_compass_heading_are_accepted(self):
        rows = [
            {
                "t": 0.0,
                "vehicles": {
                    "e1": {
                        "front_x": -3.5,
                        "front_y": 0.0,
                        "heading_deg": 90.0,
                        "speed": 0.0,
                        "length": 5.0,
                        "width": 1.8,
                    }
                },
            },
            {
                "t": 0.1,
                "vehicles": {
                    "e1": {
                        "x": -6.0,
                        "y": 0.0,
                        "heading_rad": 0.0,
                        "speed": 0.0,
                        "length": 5.0,
                        "width": 1.8,
                    }
                },
            },
        ]
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as handle:
            handle.write("\n".join(json.dumps(r) for r in rows))
        frames = pa.load_trace(handle.name)
        os.unlink(handle.name)
        self.assertAlmostEqual(frames[0].vehicles["e1"].x, frames[1].vehicles["e1"].x)
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as handle:
            handle.write(json.dumps({"t": 0.0, "vehicles": {"e1": {"x": 1}}}))
        with self.assertRaises(pa.TraceError):
            pa.load_trace(handle.name)
        os.unlink(handle.name)


class ExamplesAndCliTest(unittest.TestCase):
    def test_examples_show_the_three_cases(self):
        expect = {
            "blocked_stop": (True, True),
            "passing_cars": (False, True),
            "follower_behind": (False, True),
        }
        for name, (oc, near) in expect.items():
            row = pa.score_trace(pa.load_trace(os.path.join(EXAMPLES, f"{name}.jsonl")), "e1")
            self.assertEqual((row["oc"], row["body_5m"]), (oc, near), name)
        row = pa.score_trace(pa.load_trace(os.path.join(EXAMPLES, "blocked_stop.jsonl")), "e1")
        self.assertEqual(row["oc_time_s"], 5.0)
        self.assertFalse(row["centre_5m"])

    def test_command_line_prints_one_json_row_per_trace(self):
        out = io.StringIO()
        with redirect_stdout(out):
            status = cli.main([os.path.join(EXAMPLES, "blocked_stop.jsonl"), "--evader", "e1"])
        self.assertEqual(status, 0)
        self.assertTrue(json.loads(out.getvalue())["oc"])

    def test_grouped_summaries(self):
        rows = [
            {"group": g, "oc": g % 4 == 0, "body_5m": True} for g in range(40) for _ in range(3)
        ]
        rates = audits.endpoint_rates(rows, ["oc", "body_5m"])
        self.assertAlmostEqual(rates["oc"][0], 0.25)
        self.assertEqual(rates["body_5m"], [1.0, 1.0, 1.0])
        d = audits.disagreement(rows, "body_5m", "oc")
        self.assertAlmostEqual(d[0], 0.75)
        self.assertLess(d[1], 0.75)


class AgreementWithProjectJudgeTest(unittest.TestCase):
    """On valid, regular traces the kit and the project's judge must give the same verdict."""

    def test_same_verdict_on_random_traces(self):
        from joint_interception.domain.contracts import CaptureParameters
        from joint_interception.evaluation.capture_judge import (
            TraceFrame,
            VehicleFrame,
            judge_capture,
        )
        from joint_interception.opportunities.types import Verdict

        params = CaptureParameters.from_domain()
        kit = pa.CaptureParameters(
            gap_min_m=params.contact_gap_min_m,
            gap_max_m=params.contact_gap_max_m,
            speed_max_mps=params.capture_speed_max_mps,
            relative_speed_max_mps=params.relative_speed_max_mps,
            heading_tolerance_rad=params.orientation_tolerance_rad,
            lateral_max_m=params.alignment_lateral_max_m,
            dwell_s=params.dwell_time_s,
            overlap_tolerance_m=params.geometry_tolerance_m,
        )
        rng, captured, compared = random.Random(2026), 0, 0
        for _ in range(400):
            n = rng.randint(25, 60)
            phases = sorted(rng.sample(range(1, n), 3))
            base = {
                "gap": rng.choice([0.8, 1.0, 1.5, 2.2, 0.2]),
                "lat": rng.choice([0.0, 0.3, 0.9, 1.3]),
                "dh": rng.choice([0.0, 5.0, 14.0, 20.0]),
            }
            frames_kit, frames_prj = [], []
            for k in range(n):
                t = round(k * 0.1, 9)
                stage = sum(k >= p for p in phases)
                moving = stage in (0, 2) and rng.random() < 0.8
                e_speed = rng.uniform(1.2, 6.0) if moving else rng.uniform(0.0, 0.9)
                p_speed = rng.uniform(0.0, 0.9)
                jitter = rng.uniform(-0.05, 0.05)
                ex = -(5.0 + base["gap"] + (3.0 if stage == 2 else 0.0)) + jitter
                vehicles = {
                    "e1": (ex, base["lat"], math.radians(base["dh"]), e_speed),
                    "p1": (0.0, 0.0, 0.0, p_speed),
                    "p2": (40.0, 30.0, 1.0, 3.0),
                }
                frames_kit.append(
                    pa.Frame(t, {v: pa.Body(*s, 5.0, 1.8) for v, s in vehicles.items()})
                )
                frames_prj.append(
                    TraceFrame(t, {v: VehicleFrame(v, *s, 5.0, 1.8) for v, s in vehicles.items()})
                )
            mine = pa.operational_capture(frames_kit, "e1", params=kit)
            theirs = judge_capture(frames_prj, "e1", params, 0.1)
            self.assertIn(theirs.verdict, (Verdict.SUPPORTED, Verdict.REJECTED))
            self.assertEqual(mine.captured, theirs.verdict is Verdict.SUPPORTED)
            if mine.captured:
                captured += 1
                self.assertEqual(mine.pursuer, theirs.finisher)
                self.assertAlmostEqual(mine.witness_start_s, theirs.witness_start_s)
            self.assertAlmostEqual(mine.longest_run_s, theirs.longest_run_s, places=6)
            compared += 1
        self.assertEqual(compared, 400)
        # both verdicts must be well represented for the comparison to mean something
        self.assertGreaterEqual(captured, 30)
        self.assertLessEqual(compared - captured, 370)


if __name__ == "__main__":
    unittest.main()
