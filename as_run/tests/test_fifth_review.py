"""A-139: the defects found by the fifth review, reproduced, and the corrected code.

`TestLegacyDefects` pins each defect in the earlier functions, which are kept unchanged as the
record of how the sealed studies were computed. The other classes test the corrected code:
the transition contract (F5-1), the capture-instant extractor (F5-2) and the rejection of
invalid values by the judge (F5-5).
"""

from __future__ import annotations

import math
import os
import sys
import unittest
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "src"))

from _w2_support import requires_contracts  # noqa: E402

STEP = 0.1


def _frame(t, hold=True, missing=(), evader_speed=0.0, extra=None):
    """Evader at the origin; pursuer p1 5 m long, centre 6 m ahead: body gap 1.0 m, in file."""
    from joint_interception.evaluation.capture_judge import TraceFrame, VehicleFrame

    vehicles = {"e1": VehicleFrame("e1", 0.0, 0.0, 0.0, evader_speed, 5.0, 1.8)}
    vehicles["p1"] = VehicleFrame("p1", 6.0, 0.0, 0.0, 0.0 if hold else 2.0, 5.0, 1.8)
    vehicles.update(extra or {})
    for vid in missing:
        vehicles.pop(vid, None)
    return TraceFrame(round(t, 1), vehicles)


def _params():
    from joint_interception.domain.contracts import CaptureParameters

    return CaptureParameters.from_domain()


def _gap_trace():
    """Predicate holds at 0.0 s; p1 is absent from 0.1 to 2.0 s; it holds again from 2.1 s on.

    The only continuous 2 s run starts at 2.1 s, so the capture instant is 4.1 s.
    """
    return [_frame(i / 10, missing=("p1",) if 1 <= i <= 20 else ()) for i in range(44)]


@requires_contracts
class TestLegacyDefects(unittest.TestCase):
    """Regression record of the earlier code. These tests must keep passing: they document what
    the sealed learning studies and audits computed."""

    def test_f5_1_the_decision_taken_at_the_capture_instant_is_trained_and_rewarded(self):
        import train_mappo_v2 as v2

        ticks = [{"t": t} for t in (0.0, 3.0, 6.0, 9.0)]
        kept = v2.truncate_ticks(ticks, 3.0)
        self.assertEqual([k["t"] for k in kept], [0.0, 3.0])
        rewards = v2.episode_rewards(len(kept), True, False)
        self.assertAlmostEqual(rewards[-1], 0.995)  # paid to the decision taken AFTER the capture
        self.assertAlmostEqual(rewards[0], -0.005)

    def test_f5_1_the_decision_taken_at_the_horizon_is_trained(self):
        import train_mappo_v2 as v2

        ticks = [{"t": float(t)} for t in range(0, 301, 3)]
        kept = v2.truncate_ticks(ticks, None)
        self.assertEqual(len(kept), 101)  # 101 decisions for 100 intervals of 3 s
        self.assertEqual(kept[-1]["t"], 300.0)
        self.assertAlmostEqual(v2.episode_rewards(len(kept), False, False)[-1], -0.005)

    def test_f5_1_a_collision_after_the_cut_penalises_the_finished_prefix(self):
        import train_mappo_v2 as v2

        self.assertAlmostEqual(v2.episode_rewards(2, True, False)[-1], 0.995)
        self.assertAlmostEqual(v2.episode_rewards(2, True, True)[-1], -0.005)

    def test_f5_2_an_absent_pursuer_does_not_reset_the_earlier_helpers(self):
        from audit_d06_persistence import _witness
        from run_test_confirmation import _capture_time

        ep = SimpleNamespace(trace=_gap_trace())
        self.assertEqual(_capture_time(ep), 2.1)
        self.assertEqual(_witness(ep), (2.1, "p1"))


class TestTransitionContract(unittest.TestCase):
    def build(self, ticks, **kw):
        from joint_interception.rl.transitions import build_transitions

        return build_transitions(ticks, **kw)

    def test_capture_exactly_on_a_decision_tick(self):
        """Capture completes at 3.0 s, on the second tick. The reward belongs to the decision at
        0.0 s, whose interval (0, 3] contains the capture; the tick at 3.0 s is not trained."""
        ts = self.build([0.0, 3.0, 6.0, 9.0], trace_end_s=300.0, event_s=3.0)
        self.assertEqual(ts.ticks, [0])
        tr = ts.transitions[0]
        self.assertEqual((tr.t_decision_s, tr.t_end_s, tr.duration_s), (0.0, 3.0, 3.0))
        self.assertAlmostEqual(tr.reward, 1.0 - 0.005)
        self.assertTrue(tr.terminal)
        self.assertEqual(tr.next_tick, 1)
        self.assertEqual(ts.terminal_observation_ticks, (1, 2, 3))
        self.assertEqual(ts.end_reason, "event")

    def test_capture_between_two_ticks(self):
        """Capture at 4.0 s: the decision at 3.0 s is in force for 1 s and receives the reward,
        with a third of the time cost; later ticks are not trained."""
        ts = self.build([0.0, 3.0, 6.0], trace_end_s=300.0, event_s=4.0)
        self.assertEqual(ts.ticks, [0, 1])
        first, last = ts.transitions
        self.assertAlmostEqual(first.reward, -0.005)
        self.assertFalse(first.terminal)
        self.assertEqual(first.next_tick, 1)
        self.assertAlmostEqual(last.duration_s, 1.0)
        self.assertAlmostEqual(last.reward, 1.0 - 0.005 / 3.0)
        self.assertTrue(last.terminal)
        self.assertIsNone(last.next_tick)  # the interval ends between ticks
        self.assertEqual(ts.terminal_observation_ticks, (2,))

    def test_horizon_without_capture(self):
        """Ticks every 3 s from 0 to 300: 100 intervals are trained, the tick at 300 s is not, and
        no objective reward is paid."""
        ts = self.build(
            [float(t) for t in range(0, 301, 3)], trace_end_s=300.0, trace_end_reason="horizon"
        )
        self.assertEqual(len(ts.transitions), 100)
        self.assertEqual(ts.terminal_observation_ticks, (100,))
        self.assertEqual(ts.end_reason, "horizon")
        self.assertTrue(all(abs(tr.reward + 0.005) < 1e-12 for tr in ts.transitions))
        self.assertTrue(ts.transitions[-1].terminal)
        self.assertEqual(sum(tr.terminal for tr in ts.transitions), 1)
        self.assertAlmostEqual(sum(ts.rewards), -0.5)

    def test_objective_already_met_at_the_first_decision(self):
        """The event precedes or coincides with the first decision: nothing is trainable."""
        for event in (0.0, -0.1):
            ts = self.build([0.0, 3.0], trace_end_s=300.0, event_s=event)
            self.assertEqual(ts.transitions, ())
            self.assertEqual(ts.exclusion, "ended_before_first_decision")
            self.assertEqual(ts.terminal_observation_ticks, (0, 1))

    def test_closure_present_before_the_first_decision_and_completed_after_it(self):
        """A closure that already holds at 0.0 s completes its 2 s dwell at 2.0 s, inside the
        first interval: one transition of 2 s, rewarded, and nothing else."""
        ts = self.build([0.0, 3.0], trace_end_s=300.0, event_s=2.0)
        self.assertEqual(ts.ticks, [0])
        self.assertAlmostEqual(ts.transitions[0].duration_s, 2.0)
        self.assertAlmostEqual(ts.transitions[0].reward, 1.0 - 0.005 * 2.0 / 3.0)

    def test_no_decision_recorded(self):
        ts = self.build([], trace_end_s=300.0)
        self.assertEqual(ts.transitions, ())
        self.assertEqual(ts.exclusion, "no_decision_recorded")

    def test_evader_exit_between_ticks_ends_the_interval_without_reward(self):
        ts = self.build([0.0, 3.0, 6.0], trace_end_s=7.4, trace_end_reason="evader_exit")
        self.assertEqual(ts.ticks, [0, 1, 2])
        self.assertAlmostEqual(ts.transitions[-1].duration_s, 1.4)
        self.assertAlmostEqual(ts.transitions[-1].reward, -0.005 * 1.4 / 3.0)
        self.assertEqual(ts.end_reason, "evader_exit")

    def test_collision_after_the_cut_is_recorded_and_not_penalised(self):
        ts = self.build([0.0, 3.0, 6.0], trace_end_s=300.0, event_s=3.0, collision_times=[10.0])
        self.assertAlmostEqual(ts.transitions[0].reward, 0.995)
        self.assertFalse(ts.transitions[0].collision)
        self.assertEqual(ts.collisions_in_interval, ())
        self.assertEqual(ts.collisions_outside, (10.0,))

    def test_collision_inside_the_trained_interval_is_penalised_where_it_happened(self):
        ts = self.build([0.0, 3.0, 6.0], trace_end_s=300.0, event_s=7.0, collision_times=[4.0])
        r = ts.rewards
        self.assertAlmostEqual(r[0], -0.005)
        self.assertAlmostEqual(r[1], -0.005 - 1.0)  # (3, 6] contains the collision
        self.assertAlmostEqual(r[2], 1.0 - 0.005 / 3.0)  # (6, 7] contains the capture
        self.assertEqual([tr.collision for tr in ts.transitions], [False, True, False])

    def test_collision_on_a_tick_belongs_to_the_interval_that_ends_there(self):
        ts = self.build([0.0, 3.0, 6.0], trace_end_s=9.0, collision_times=[3.0])
        self.assertEqual([tr.collision for tr in ts.transitions], [True, False, False])

    def test_collision_before_any_decision_is_not_attributed(self):
        ts = self.build([0.0, 3.0], trace_end_s=6.0, collision_times=[0.0])
        self.assertEqual(ts.collisions_in_interval, ())
        self.assertEqual(ts.collisions_outside, (0.0,))
        self.assertFalse(any(tr.collision for tr in ts.transitions))

    def test_the_collision_penalty_is_applied_once(self):
        ts = self.build([0.0, 3.0, 6.0], trace_end_s=9.0, collision_times=[1.0, 1.1, 4.0, 7.0])
        self.assertEqual([tr.collision for tr in ts.transitions], [True, False, False])
        self.assertAlmostEqual(sum(ts.rewards), -0.015 - 1.0)
        self.assertEqual(len(ts.collisions_in_interval), 4)

    def test_time_cost_is_exact_for_any_end(self):
        for end in (0.7, 3.0, 4.0, 299.9, 300.0):
            ts = self.build([float(t) for t in range(0, 301, 3)], trace_end_s=300.0, event_s=end)
            self.assertAlmostEqual(sum(ts.rewards), 1.0 - 0.005 * end / 3.0, places=9)
            self.assertAlmostEqual(sum(tr.duration_s for tr in ts.transitions), end, places=9)

    def test_every_trained_decision_precedes_the_end(self):
        for end in (0.05, 2.9, 3.0, 3.1, 150.0, 300.0):
            ts = self.build([float(t) for t in range(0, 301, 3)], trace_end_s=300.0, event_s=end)
            self.assertTrue(
                all(tr.t_decision_s < end and tr.duration_s > 0 for tr in ts.transitions)
            )

    def test_invalid_times_are_rejected(self):
        from joint_interception.rl.transitions import TransitionError

        bad = [
            dict(ticks=[0.0, float("nan")], trace_end_s=300.0),
            dict(ticks=[0.0, float("inf")], trace_end_s=300.0),
            dict(ticks=[0.0, 3.0, 3.0], trace_end_s=300.0),
            dict(ticks=[3.0, 0.0], trace_end_s=300.0),
            dict(ticks=[0.0], trace_end_s=float("nan")),
            dict(ticks=[0.0], trace_end_s=300.0, event_s=float("inf")),
            dict(ticks=[0.0], trace_end_s=10.0, event_s=11.0),
            dict(ticks=[0.0], trace_end_s=10.0, collision_times=[float("nan")]),
            dict(ticks=[0.0], trace_end_s=10.0, decide_s=0.0),
        ]
        for case in bad:
            ticks = case.pop("ticks")
            with self.assertRaises(TransitionError):
                self.build(ticks, **case)

    def test_gae_ends_with_a_zero_value(self):
        from joint_interception.rl.transitions import discounted_returns, gae

        rewards, values = [-0.005, -0.005, 0.995], [0.2, 0.4, 0.7]
        adv = gae(rewards, values, 0.99, 0.95)
        self.assertAlmostEqual(adv[-1], 0.995 - 0.7)
        d1 = -0.005 + 0.99 * 0.7 - 0.4
        self.assertAlmostEqual(adv[1], d1 + 0.99 * 0.95 * adv[2])
        # lambda = 1: advantage = discounted return - value
        full = gae(rewards, values, 0.99, 1.0)
        for a, g, v in zip(full, discounted_returns(rewards, 0.99), values, strict=True):
            self.assertAlmostEqual(a, g - v)


@requires_contracts
class TestEarliestCapture(unittest.TestCase):
    def extract(self, trace):
        from joint_interception.evaluation.capture_time import earliest_capture

        return earliest_capture(trace, "e1", _params(), STEP)

    def judged(self, trace):
        from joint_interception.evaluation.capture_time import judge_earliest_capture

        return judge_earliest_capture(trace, "e1", _params(), STEP)

    def test_an_absent_pursuer_resets_its_run(self):
        got = self.extract(_gap_trace())
        self.assertEqual((got.time_s, got.pursuer_id, got.run_start_s), (4.1, "p1", 2.1))
        self.assertEqual(self.judged(_gap_trace()), got)

    def test_an_absent_evader_resets_every_run(self):
        trace = [_frame(i / 10, missing=("e1",) if i == 10 else ()) for i in range(40)]
        got = self.extract(trace)
        self.assertEqual((got.time_s, got.run_start_s), (3.1, 1.1))
        self.assertEqual(self.judged(trace), got)

    def test_a_trace_that_ends_inside_the_gap_has_no_capture(self):
        trace = _gap_trace()[:35]  # the run from 2.1 s lasts 1.3 s
        self.assertIsNone(self.extract(trace))
        self.assertIsNone(self.judged(trace))

    def test_agrees_with_the_earlier_helper_on_a_complete_trace(self):
        from run_test_confirmation import _capture_time

        trace = [_frame(i / 10, hold=i >= 13) for i in range(60)]
        got = self.extract(trace)
        self.assertEqual(got.time_s, 3.3)
        self.assertEqual(_capture_time(SimpleNamespace(trace=trace)), 3.3)
        self.assertEqual(self.judged(trace), got)

    def test_the_earliest_pursuer_wins_and_another_pursuer_being_absent_is_irrelevant(self):
        from joint_interception.evaluation.capture_judge import VehicleFrame

        def frame(i):
            # p2 holds from 0.5 s in the same slot; p1 holds only from 3.0 s and vanishes at 1.0 s
            p2 = VehicleFrame("p2", 6.0, 0.0, 0.0, 0.0 if i >= 5 else 2.0, 5.0, 1.8)
            f = _frame(i / 10, hold=i >= 30, extra={"p2": p2}, missing=("p1",) if i == 10 else ())
            return f

        trace = [frame(i) for i in range(60)]
        got = self.extract(trace)
        self.assertEqual((got.time_s, got.pursuer_id), (2.5, "p2"))
        self.assertEqual(self.judged(trace), got)

    def test_irregular_cadence_is_refused(self):
        from joint_interception.evaluation.capture_time import TraceIntegrityError

        trace = [_frame(i / 10) for i in range(40) if i != 7]
        with self.assertRaises(TraceIntegrityError):
            self.extract(trace)

    def test_invalid_values_are_refused(self):
        from joint_interception.evaluation.capture_time import TraceIntegrityError

        trace = [_frame(i / 10, evader_speed=float("nan") if i == 3 else 0.0) for i in range(40)]
        with self.assertRaises(TraceIntegrityError):
            self.extract(trace)

    def test_absent_frames_separates_inner_gaps_from_a_final_disappearance(self):
        from joint_interception.evaluation.capture_time import absent_frames

        trace = [
            _frame(i / 10, missing=(("p1",) if 1 <= i <= 20 else ()) + (("e1",) if i >= 40 else ()))
            for i in range(44)
        ]
        got = absent_frames(trace, ["e1", "p1", "p9"])
        self.assertEqual(got["p1"], {"absent": 20, "inner_gap_frames": 20, "never_present": False})
        self.assertEqual(got["e1"], {"absent": 4, "inner_gap_frames": 0, "never_present": False})
        self.assertTrue(got["p9"]["never_present"])


@requires_contracts
class TestJudgeRejectsInvalidValues(unittest.TestCase):
    def judge(self, trace):
        from joint_interception.evaluation.capture_judge import judge_capture

        return judge_capture(trace, "e1", _params(), STEP)

    def with_vehicle(self, vid, **changes):
        import dataclasses

        out = []
        for i in range(30):
            f = _frame(i / 10)
            if i == 12:
                f.vehicles[vid] = dataclasses.replace(f.vehicles[vid], **changes)
            out.append(f)
        return out

    def test_a_valid_trace_is_still_supported(self):
        v = self.judge([_frame(i / 10) for i in range(30)])
        self.assertEqual(v.verdict.value, "SUPPORTED")
        self.assertEqual(v.witness_start_s, 0.0)

    def test_invalid_values_make_the_verdict_unknown(self):
        nan, inf = float("nan"), float("inf")
        cases = [
            ("e1", {"speed_mps": nan}, "non_finite_value"),
            ("p1", {"speed_mps": nan}, "non_finite_value"),
            ("e1", {"speed_mps": inf}, "non_finite_value"),
            ("e1", {"speed_mps": -inf}, "non_finite_value"),
            ("p1", {"x": inf}, "non_finite_value"),
            ("e1", {"y": nan}, "non_finite_value"),
            ("p1", {"heading_rad": nan}, "non_finite_value"),
            ("e1", {"length_m": nan}, "non_finite_value"),
            ("e1", {"speed_mps": -1073741824.0}, "negative_speed"),
            ("p1", {"speed_mps": -0.5}, "negative_speed"),
            ("e1", {"length_m": 0.0}, "non_positive_dimension"),
            ("p1", {"width_m": -1.8}, "non_positive_dimension"),
        ]
        for vid, changes, defect in cases:
            v = self.judge(self.with_vehicle(vid, **changes))
            self.assertEqual(v.verdict.value, "UNKNOWN", (vid, changes))
            self.assertEqual(v.reason, "trace_has_invalid_values")
            self.assertEqual(v.detail["defect"], defect, (vid, changes))
            self.assertEqual(v.detail["vehicle_id"], vid)
            self.assertEqual(v.detail["time_s"], 1.2)

    def test_every_frame_nan_was_supported_before_the_check(self):
        """The reviewer's counterexample: NaN evader speed in every frame."""
        trace = [_frame(i / 10, evader_speed=float("nan")) for i in range(22)]
        self.assertEqual(self.judge(trace).verdict.value, "UNKNOWN")

    def test_non_finite_time_and_step_are_unknown(self):
        from joint_interception.evaluation.capture_judge import TraceFrame, judge_capture

        trace = [_frame(i / 10) for i in range(30)]
        trace[4] = TraceFrame(float("nan"), trace[4].vehicles)
        self.assertEqual(self.judge(trace).reason, "trace_has_invalid_values")
        good = [_frame(i / 10) for i in range(30)]
        for step in (float("nan"), 0.0, -0.1, float("inf")):
            v = judge_capture(good, "e1", _params(), step)
            self.assertEqual(v.reason, "invalid_physical_step")

    def test_the_predicate_never_holds_on_an_invalid_frame(self):
        import dataclasses

        from joint_interception.evaluation.capture_judge import _conditions_hold

        f = _frame(0.0)
        e, p = f.vehicles["e1"], f.vehicles["p1"]
        self.assertTrue(_conditions_hold(p, e, _params())[0])
        for vehicle, field in ((e, "speed_mps"), (p, "x"), (e, "heading_rad"), (p, "width_m")):
            broken = dataclasses.replace(vehicle, **{field: float("nan")})
            pair = (broken, e) if vehicle is p else (p, broken)
            self.assertEqual(_conditions_hold(*pair, _params()), (False, "invalid_frame_values"))

    def test_numpy_scalars_are_accepted_as_numbers(self):
        import numpy as np

        from joint_interception.evaluation.capture_judge import VehicleFrame, vehicle_frame_defect

        ok = VehicleFrame("p1", np.float32(6.0), np.float64(0.0), 0, np.float32(0.0), 5, 1.8)
        self.assertIsNone(vehicle_frame_defect(ok))
        self.assertEqual(
            vehicle_frame_defect(VehicleFrame("p1", "6.0", 0.0, 0.0, 0.0, 5.0, 1.8)),
            "non_finite_value",
        )


class TestEpisodeRecord(unittest.TestCase):
    def test_episode_carries_timed_collision_events(self):
        from joint_interception.rl.rollout import Episode

        a, b = Episode(), Episode()
        self.assertEqual(a.collision_events, [])
        a.collision_events.append({"t": 1.0, "vehicles": ["p1", "e1"]})
        self.assertEqual(b.collision_events, [])  # no shared default
        self.assertFalse(math.isnan(a.collision_events[0]["t"]))


if __name__ == "__main__":
    unittest.main()
