"""Design and pairing of the kinematic sensitivity study (A-127 K); no simulator."""

import os
import sys
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

from run_kinematic_sensitivity import VARIANTS, cell_means, paired, tasks  # noqa: E402


class DesignTest(unittest.TestCase):
    def test_registered_size_and_unique_keys(self):
        t = tasks()
        self.assertEqual(len(t), 7 * 20 * 2 * 2 * 3 * 2 * 3)
        self.assertEqual(len({x[0] for x in t}), len(t))

    def test_variants_share_scenarios_and_seeds(self):
        by = {}
        for _key, m, i, seed, level, team, method, variant in tasks():
            by.setdefault(variant, set()).add((m, i, seed, level, team, method))
        self.assertEqual(set(by), set(VARIANTS))
        self.assertEqual(by["K0"], by["K1"])
        self.assertEqual(by["K0"], by["K2"])


class PairingTest(unittest.TestCase):
    def test_seed_average_then_family_pairs(self):
        rows = {
            "K|K0|plus_opt|a|0|1|AVOIDANT|3": {"d06": True},
            "K|K0|plus_opt|a|0|2|AVOIDANT|3": {"d06": False},
            "K|K0|pursuit|a|0|1|AVOIDANT|3": {"d06": False},
            "K|K0|pursuit|a|0|2|AVOIDANT|3": {"d06": False},
            "K|K0|plus_opt|a|0|1|AVOIDANT|5": {"d06": True},
            "K|K0|pursuit|a|0|1|AVOIDANT|5": {"d06": True},
            "K|K0|pursuit|b|0|1|AVOIDANT|5": {"failed": "x"},
        }
        cm = cell_means(rows, "d06")
        self.assertEqual(cm[("K0", "plus_opt", "a", 0, "AVOIDANT", 3)], 0.5)
        plb = {k[2:]: v for k, v in cm.items() if k[:2] == ("K0", "plus_opt")}
        pur = {k[2:]: v for k, v in cm.items() if k[:2] == ("K0", "pursuit")}
        fams = paired(plb, pur)
        self.assertEqual(list(fams), [("a", 0, "AVOIDANT")])
        self.assertEqual(sorted(fams[("a", 0, "AVOIDANT")]), [0.0, 0.5])


class TrafficDesignTest(unittest.TestCase):
    def test_traffic_arm_reuses_the_reference_scenarios(self):
        import run_traffic_sensitivity as traffic

        t = traffic.tasks()
        self.assertEqual(len(t), 7 * 20 * 2 * 2 * 3 * 2)
        reference = {x[0] for x in tasks() if x[7] == "K0"}
        self.assertEqual({x[0].replace("|KT|", "|K0|") for x in t}, reference)
        self.assertTrue(all(x[0].startswith("K|KT|") for x in t))

    def test_traffic_file_per_city(self):
        import os

        import run_traffic_sensitivity as traffic

        for city in {x[1] for x in traffic.tasks()}:
            args = traffic.traffic_args(city)
            self.assertEqual(args[0], "-r")
            self.assertTrue(os.path.exists(args[1]), city)


if __name__ == "__main__":
    unittest.main()
