"""A-138: design and summary of the second held-out evaluation; no simulator."""

import os
import random
import sys
import tempfile
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

import run_heldout_b as hb  # noqa: E402


class DesignTest(unittest.TestCase):
    def test_registered_size(self):
        t = hb.tasks(hb.REGISTERED)
        self.assertEqual(len(t), 4 * 20 * 2 * (3 * 3 * 3 + 2))
        self.assertEqual(len({x[0] for x in t}), len(t))
        self.assertEqual(sum(x[0].startswith("HN|") for x in t), 320)
        self.assertEqual({x[1] for x in t}, set(hb.REGISTERED))

    def test_null_team_shares_scenarios_and_seeds_with_the_controllers(self):
        t = hb.tasks(hb.REGISTERED)
        ctrl = {(x[1], x[2], x[3], x[4]) for x in t if x[0].startswith("HB|") and x[5] == 5}
        null = {(x[1], x[2], x[3], x[4]) for x in t if x[0].startswith("HN|")}
        self.assertTrue(null <= ctrl)

    def test_registered_cities_are_not_any_earlier_city(self):
        from run_endpoint_validation import DEVELOPMENT, TRAINING
        from run_test_confirmation import TEST_CITIES

        self.assertTrue(set(hb.REGISTERED).isdisjoint(set(TRAINING + DEVELOPMENT + TEST_CITIES)))


class SummaryTest(unittest.TestCase):
    def test_primaries_on_synthetic_rows(self):
        rng, rows = random.Random(1), {}
        rate = {"plus_opt": 0.6, "ambush_a95": 0.4, "pursuit": 0.2}
        for m in hb.REGISTERED:
            for i in range(8):
                for level in hb.LEVELS:
                    for team in hb.TEAMS:
                        for method in hb.METHODS:
                            d06 = rng.random() < rate[method]
                            centre = d06 or rng.random() < 0.5
                            key = f"HB|{method}|{m}|{i}|1|{level}|{team}"
                            rows[key] = {"d06": d06, "prox_5m": True, "prox_5m_centre": centre}
                for level in hb.PRIMARY_LEVELS:
                    null = {"d06": False, "prox_5m": i % 2 == 0, "prox_5m_centre": False}
                    rows[f"HN|null|{m}|{i}|1|{level}|5"] = null
        rows["HB|pursuit|denver_downtown|99|1|RANDOM|7"] = {"failed": "placement"}
        with tempfile.TemporaryDirectory() as tmp:
            out = hb.summarise(tmp, rows, hb.REGISTERED)
        self.assertEqual(out["failed"], 1)
        self.assertEqual(out["families"], 4 * 8 * 2)
        self.assertEqual(out["cells"], 4 * 8 * 2 * 3)
        self.assertTrue(out["B1_passes"])
        self.assertTrue(out["B2_passes"])
        self.assertEqual(out["null_team"], {"d06": 0.0, "prox_5m": 0.5, "prox_5m_centre": 0.0})
        self.assertEqual(set(out["by_city_plb_minus_pursuit"]), set(hb.REGISTERED))
        self.assertEqual(out["plb_minus_pursuit_under_body_gap_5m"][0], 0.0)
        self.assertEqual(set(out["by_team_plb_minus_pursuit"]), {"team3", "team5", "team7"})


if __name__ == "__main__":
    unittest.main()
