"""Design and selection logic of the tuned-evader study (A-127 E); no simulator."""

import os
import sys
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

import run_tuned_evader_study as study  # noqa: E402


class CandidateTest(unittest.TestCase):
    def test_registered_candidate_set(self):
        a, b = study.candidates(), study.candidates()
        self.assertEqual(a, b)
        self.assertEqual(len(a), 33)
        self.assertEqual(a["ref"], (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
        for name, w in a.items():
            self.assertEqual(len(w), 7, name)
            self.assertTrue(all(-1.0 <= x <= 1.0 for x in w))
        self.assertEqual(len({w for w in a.values()}), 33)


class TaskTest(unittest.TestCase):
    def setUp(self):
        self.c = study.candidates()

    def test_rung_sizes(self):
        r1 = study.rung1_tasks(self.c)
        self.assertEqual(len(r1), 33 * 4 * 6)
        kept = [f"c{k:02d}" for k in range(8)]
        r2 = study.rung2_tasks(self.c, kept + ["ref"])
        self.assertEqual(len(r2), 9 * 4 * 20 * 3)
        self.assertEqual(len({t[0] for t in r1 + r2}), len(r1) + len(r2))

    def test_test_design_and_shared_scenarios(self):
        t = study.test_tasks(self.c, "c03")
        self.assertEqual(len(t), 7 * 20 * 2 * 3 * 5)
        by = {}
        for _key, m, i, seed, salt, team, method, w in t:
            self.assertEqual(salt, "PE21")
            by.setdefault((method, w), set()).add((m, i, seed, team))
        self.assertEqual(len(by), 5)
        sets = list(by.values())
        self.assertTrue(all(s == sets[0] for s in sets))


class SelectionTest(unittest.TestCase):
    def test_lowest_with_ties_by_name(self):
        rates = {"c02": 0.3, "c01": 0.3, "c00": 0.5, "c03": 0.1}
        self.assertEqual(study.lowest(rates, list(rates), 3), ["c03", "c01", "c02"])

    def test_rates_use_common_cells_only(self):
        rows = {
            "R1|a|x|0|1|5": {"d06": True},
            "R1|a|x|1|1|5": {"d06": True},
            "R1|b|x|0|1|5": {"d06": False},
            "R1|b|x|1|1|5": {"failed": "placement"},
        }
        rates, n = study.rung_rates(rows, "R1", ["a", "b"])
        self.assertEqual(n, 1)
        self.assertEqual(rates, {"a": 1.0, "b": 0.0})

    def test_cells_and_pairs(self):
        rows = {
            "T|sel|plus_opt|x|0|1|TUNED|3": {"d06": True},
            "T|sel|plus_opt|x|0|2|TUNED|3": {"d06": False},
            "T|sel|pursuit|x|0|1|TUNED|3": {"d06": False},
            "T|sel|pursuit|x|0|2|TUNED|3": {"d06": False},
            "T|sel|plus_opt|x|0|1|TUNED|5": {"d06": True},
            "T|sel|pursuit|x|0|1|TUNED|5": {"d06": False},
        }
        a, b = study.cells(rows, "sel", "plus_opt"), study.cells(rows, "sel", "pursuit")
        self.assertEqual(a[("x", 0, "TUNED", 3)], 0.5)
        fams = study.paired(a, b)
        self.assertEqual(sorted(fams[("x", 0, "TUNED")]), [0.5, 1.0])
        self.assertEqual(study.paired(a, b, team=5), {("x", 0, "TUNED"): [1.0]})


if __name__ == "__main__":
    unittest.main()
