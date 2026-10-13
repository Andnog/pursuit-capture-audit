"""Split integrity: TEST closed, no city in two splits, inherited exposure recorded."""

from __future__ import annotations

import json
import os
import unittest

from _support import ROOT  # noqa: E402

CONTRACTS = os.path.join(ROOT, "contracts")
HISTORICAL_MAPS = {"Condesa", "Berlin", "Boston", "Roma"}


def load(name: str) -> dict:
    with open(os.path.join(CONTRACTS, name), encoding="utf-8") as handle:
        return json.load(handle)


def city_of(map_id: str, maps_manifest: dict) -> str:
    """The city a map lies in, from the maps manifest - never from the identifier.

    The first version of the exposure guard compared historical CITY names ("Berlin")
    against map IDENTIFIERS ("berlin_mitte_large"). Those never intersect, so the guard
    passed whatever the split contained - it would have admitted the exposed Berlin map
    to TEST without complaint.
    """
    for entry in maps_manifest["maps"]:
        if entry["map_id"] == map_id:
            return entry["city"]
    raise KeyError(f"{map_id} has no entry in the maps manifest")


def exposed_maps_in(split_cities: list[str], maps_manifest: dict) -> set[str]:
    return {
        m
        for m in split_cities
        if any(h.lower() in city_of(m, maps_manifest).lower() for h in HISTORICAL_MAPS)
    }


class TestSplitManifest(unittest.TestCase):
    def setUp(self):
        self.manifest = load("split_manifest.json")

    def test_test_split_is_closed_and_never_accessed(self):
        self.assertEqual(self.manifest["splits"]["TEST"]["state"], "CLOSED")
        self.assertEqual(self.manifest["test_accesses_in_this_project"], 0)
        self.assertEqual(self.manifest["test_access_events"], [])

    def test_test_split_permits_nothing_while_closed(self):
        self.assertEqual(self.manifest["splits"]["TEST"]["permits"], [])

    def test_development_forbids_gradient_updates(self):
        forbids = self.manifest["splits"]["DEVELOPMENT"]["forbids"]
        self.assertIn("gradient_updates", forbids)
        self.assertIn("adding_trajectories_to_training_data", forbids)

    def test_no_city_appears_in_two_splits(self):
        seen: dict[str, str] = {}
        for split, content in self.manifest["splits"].items():
            for city in content["cities"]:
                self.assertNotIn(city, seen, f"{city} is in both {seen.get(city)} and {split}")
                seen[city] = split

    def test_no_scenario_appears_in_two_splits(self):
        seen: dict[str, str] = {}
        for split, content in self.manifest["splits"].items():
            for scenario in content["scenarios"]:
                self.assertNotIn(scenario, seen)
                seen[scenario] = split

    def test_exposure_log_exists_even_while_empty(self):
        self.assertIn("exposure_log", self.manifest)
        self.assertIsInstance(self.manifest["exposure_log"], list)

    def test_opening_test_has_explicit_preconditions(self):
        preconditions = self.manifest["test_open_preconditions"]
        self.assertIn("method frozen", preconditions)
        self.assertTrue(
            any("historical TEST" in p for p in preconditions),
            "locating the sealed historical TEST set must be a precondition",
        )


class TestMapsManifest(unittest.TestCase):
    def setUp(self):
        self.manifest = load("maps_manifest.json")

    def test_maps_have_been_adopted_under_d15(self):
        """Replaces `test_no_map_has_been_adopted_yet`, which encoded the W2 state."""
        self.assertEqual(self.manifest["status"], "POPULATED")
        self.assertEqual(len(self.manifest["maps"]), 12)

    def test_an_unresolved_field_carries_a_reason_never_a_bare_label(self):
        """A missing fact is recorded as missing, with why - never silently filled in."""
        for entry in self.manifest["maps"]:
            for field, value in entry.items():
                if value == "UNRESOLVED":
                    self.fail(f"{entry['map_id']}.{field} is a bare UNRESOLVED with no reason")
                if isinstance(value, dict) and value.get("value") == "UNRESOLVED":
                    self.assertTrue(
                        value.get("reason"), f"{entry['map_id']}.{field} lacks a reason"
                    )

    def test_split_assignment_agrees_with_the_split_manifest(self):
        splits = load("split_manifest.json")
        where = {}
        for name in ("TRAINING", "DEVELOPMENT", "TEST"):
            for city in splits["splits"][name]["cities"]:
                where[city] = name
        for city in splits["excluded"]["cities"]:
            where[city] = "EXCLUDED"
        for entry in self.manifest["maps"]:
            self.assertEqual(entry["split_assignment"], where[entry["map_id"]], entry["map_id"])

    def test_required_provenance_fields_are_declared(self):
        required = set(self.manifest["required_fields_per_map"])
        for field in (
            "source_license",
            "road_data_version",
            "clipping_boundary",
            "source_asset_sha256",
            "generated_asset_sha256",
            "split_assignment",
        ):
            self.assertIn(field, required)

    def test_any_future_map_entry_must_carry_every_required_field(self):
        required = set(self.manifest["required_fields_per_map"])
        for entry in self.manifest["maps"]:
            missing = required - set(entry)
            self.assertEqual(missing, set(), f"map entry missing {sorted(missing)}")

    def test_inherited_exposure_records_the_four_historical_maps(self):
        exposed = set(self.manifest["inherited_exposure"]["historically_exposed_cities"])
        self.assertEqual(exposed, HISTORICAL_MAPS)

    def test_historical_test_set_is_resolved_and_is_exactly_the_test_split(self):
        """Replaces the W2 assertion that its identity was UNRESOLVED; it was found 2026-09-21."""
        historical = self.manifest["sealed_historical_test_set"]
        self.assertEqual(historical["identity"], "RESOLVED")
        test_split = load("split_manifest.json")["splits"]["TEST"]["cities"]
        self.assertEqual(sorted(historical["maps"]), sorted(test_split))


class TestExposedCitiesAreNotSilentlyReused(unittest.TestCase):
    def setUp(self):
        self.splits = load("split_manifest.json")
        self.maps = load("maps_manifest.json")

    def test_no_historically_exposed_city_is_assigned_to_test(self):
        found = exposed_maps_in(self.splits["splits"]["TEST"]["cities"], self.maps)
        self.assertEqual(found, set())

    def test_no_historically_exposed_city_is_used_for_a_transfer_claim(self):
        """Transfer requires city-level separation from every exposed historical map."""
        for split in ("DEVELOPMENT", "TEST"):
            found = exposed_maps_in(self.splits["splits"][split]["cities"], self.maps)
            self.assertEqual(found, set(), f"{split} reuses a historically exposed city")

    def test_the_guard_would_catch_an_actual_violation(self):
        """The previous guard could not fire. This one must.

        Putting the excluded Berlin map into TEST has to be detected. Under the old
        name-against-identifier comparison it was not.
        """
        poisoned = list(self.splits["splits"]["TEST"]["cities"]) + ["berlin_mitte_large"]
        self.assertEqual(exposed_maps_in(poisoned, self.maps), {"berlin_mitte_large"})

    def test_the_old_comparison_really_was_vacuous(self):
        """Kept as a record: names and identifiers never intersect."""
        self.assertEqual({"berlin_mitte_large"} & HISTORICAL_MAPS, set())

    def test_the_excluded_map_is_in_no_split(self):
        excluded = set(self.splits["excluded"]["cities"])
        for name in ("TRAINING", "DEVELOPMENT", "TEST"):
            self.assertEqual(set(self.splits["splits"][name]["cities"]) & excluded, set(), name)


if __name__ == "__main__":
    unittest.main()
