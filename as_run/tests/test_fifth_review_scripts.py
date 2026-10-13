"""A-139: the pure parts of the scan, the reconstruction and the offline delimitation."""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "src"))

from _w2_support import requires_contracts  # noqa: E402


def _frame(t, hold=True, missing=()):
    from joint_interception.evaluation.capture_judge import TraceFrame, VehicleFrame

    vehicles = {
        "e1": VehicleFrame("e1", 0.0, 0.0, 0.0, 0.0, 5.0, 1.8),
        "p1": VehicleFrame("p1", 6.0, 0.0, 0.0, 0.0 if hold else 2.0, 5.0, 1.8),
    }
    for vid in missing:
        vehicles.pop(vid, None)
    return TraceFrame(round(t, 1), vehicles)


@requires_contracts
class TestScanComparison(unittest.TestCase):
    def setUp(self):
        import scan_capture_instants as scan

        self.scan = scan

    def test_a_complete_trace_is_unaffected(self):
        trace = [_frame(i / 10, hold=i >= 13) for i in range(80)]
        row = self.scan.compare(trace, 3.3, "p1", ["e1", "p1"])
        self.assertTrue(row["reproduced"])
        self.assertTrue(row["same_instant"])
        self.assertEqual(row["legacy"], [3.3, "p1"])
        self.assertEqual(row["corrected"], [3.3, "p1"])
        self.assertEqual(row["judge"], [3.3, "p1"])
        self.assertEqual((row["absent"], row["inner_gap_frames"], row["invalid"]), ({}, 0, None))

    def test_a_gap_in_the_pursuer_record_is_reported_as_affected(self):
        """The reviewer's counterexample: the sealed instant would be 2.1 s, the valid one 4.1 s."""
        trace = [_frame(i / 10, missing=("p1",) if 1 <= i <= 20 else ()) for i in range(60)]
        row = self.scan.compare(trace, 2.1, "p1", ["e1", "p1"])
        self.assertTrue(row["reproduced"])  # the earlier helper gives the sealed value again
        self.assertFalse(row["same_instant"])  # and the corrected instant differs
        self.assertEqual(row["corrected"], [4.1, "p1"])
        self.assertEqual(row["judge"], [4.1, "p1"])
        self.assertEqual(row["inner_gap_frames"], 20)

    def test_a_final_disappearance_is_not_an_inner_gap(self):
        trace = [_frame(i / 10, missing=("e1",) if i >= 70 else ()) for i in range(80)]
        row = self.scan.compare(trace, 2.0, "p1", ["e1", "p1"])
        self.assertTrue(row["same_instant"])
        self.assertEqual(row["absent"]["e1"]["absent"], 10)
        self.assertEqual(row["inner_gap_frames"], 0)

    def test_summary_lists_what_differs(self):
        good = {
            "key": "a", "sealed": [3.3, "p1"], "legacy": [3.3, "p1"], "corrected": [3.3, "p1"],
            "judge": [3.3, "p1"], "reproduced": True, "same_instant": True, "captured": True,
            "absent": {}, "inner_gap_frames": 0, "invalid": None, "frames": 3001, "collisions": 1,
            "collision_times": [200.0],
        }  # fmt: skip
        bad = dict(good, key="b", corrected=[4.1, "p1"], judge=[4.1, "p1"], same_instant=False)
        bad.update(
            inner_gap_frames=20, absent={"p1": {"absent": 20}}, collisions=0, collision_times=[]
        )
        out = self.scan.summarise([good, bad, {"key": "c", "failed": "x"}])
        self.assertEqual((out["replays"], out["failed"], out["same_instant_all_four"]), (3, 1, 1))
        self.assertEqual([d["key"] for d in out["instants_that_differ"]], ["b"])
        self.assertEqual(out["traces_with_an_inner_gap"], 1)
        self.assertEqual(out["absent_vehicle_counts"], {"p1": 1})
        self.assertEqual(out["episodes_with_a_collision"], 1)
        self.assertEqual(out["episodes_with_collisions_only_after_capture"], 1)
        self.assertEqual(out["frames_scanned"], 6002)


class TestDelimitation(unittest.TestCase):
    def setUp(self):
        import delimit_fifth_review as d

        self.d = d

    def test_denominators_are_recovered_from_rounded_rates(self):
        # 23 of 61, 23 of 61 and 58 of 61, as logged for the first batch of a run
        self.assertEqual(self.d.candidates([0.377, 0.377, 0.951]), [61])
        self.assertEqual(self.d.numerator(0.377, 61), 23)
        # a rate that several denominators can produce stays ambiguous
        self.assertGreater(len(self.d.candidates([0.5, 0.5, 1.0])), 1)

    def test_the_registered_test_schedule_is_1680_per_policy(self):
        out = self.d.schedule()
        self.assertEqual(out["scheduled_per_policy"], 1680)
        self.assertEqual(out["protocol_text_says"], 840)
        self.assertEqual(out["scheduled_total"], out["rows_in_the_sealed_package"])
        self.assertEqual(out["rows_per_policy_in_the_sealed_package"], [1680])
        self.assertEqual(out["completed_per_policy"], [1636])


class TestReconstructionTasks(unittest.TestCase):
    def test_tasks_are_the_first_batches_of_v3_without_tensors(self):
        import reconstruct_v3_first_batches as rec
        import train_mappo_v3 as v3

        tasks = rec.tasks()
        self.assertEqual(len(tasks), 8 * 64)
        self.assertEqual(len({t[0] for t in tasks}), 512)
        self.assertEqual({t[0].split("|")[0] for t in tasks}, set(v3.ORDER))
        self.assertTrue(all(t[10] == "sample" and t[12] is False for t in tasks))
        self.assertEqual({t[4][:4] for t in tasks}, {"PT23"})
        self.assertEqual(set(rec.sealed_rates()), set(v3.ORDER))


if __name__ == "__main__":
    unittest.main()
