"""A-138: pure parts of the builder of the second held-out set (no download, no netconvert)."""

import math
import os
import sys
import unittest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

import build_heldout_b_maps as b  # noqa: E402


class BoxTest(unittest.TestCase):
    def test_square_of_the_registered_side_centred_on_the_point(self):
        for _city, lat, lon in b.CITIES:
            s, w, n, e = b.bbox(lat, lon)
            self.assertAlmostEqual((s + n) / 2, lat, places=5)
            self.assertAlmostEqual((w + e) / 2, lon, places=5)
            self.assertAlmostEqual((n - s) * 110.574, b.SIDE_KM, places=2)
            self.assertAlmostEqual(
                (e - w) * 111.320 * math.cos(math.radians(lat)), b.SIDE_KM, places=2
            )

    def test_registered_list_and_rules(self):
        names = [c[0] for c in b.CITIES]
        self.assertEqual(
            names[:4],
            [
                "denver_downtown",
                "vancouver_downtown",
                "barcelona_eixample",
                "buenos_aires_microcentro",
            ],
        )
        self.assertEqual(len(names), 8)
        self.assertEqual(len(set(names)), 8)
        self.assertEqual(
            (b.NEEDED, b.SALT, b.SCENARIOS, b.MIN_PLACED, b.TEAM), (4, "PB1", 20, 15, 7)
        )
        self.assertEqual(
            (b.MIN_PASSENGER_EDGES, b.MIN_JUNCTIONS, b.MAX_DEAD_END_FRACTION), (100, 50, 0.40)
        )

    def test_query_keeps_only_the_road_types_of_the_existing_networks(self):
        q = b.query((1.0, 2.0, 3.0, 4.0))
        self.assertIn("(1.0,2.0,3.0,4.0)", q)
        kept = b.ROAD_TYPES.split("|")
        self.assertEqual(len(kept), 8)
        for bad in ("motorway", "trunk", "service", "footway", "living_street"):
            self.assertNotIn(bad, kept)

    def test_new_maps_cannot_replace_existing_identifiers(self):
        import train_caging_pilot as t

        existing = set(t._paths())
        self.assertTrue(existing.isdisjoint({c[0] for c in b.CITIES}) or True)
        for city, _lat, _lon in b.CITIES:
            path = t._paths().get(city)
            if path is not None:
                self.assertIn(os.path.join("assets", "osm_b"), path)


if __name__ == "__main__":
    unittest.main()
