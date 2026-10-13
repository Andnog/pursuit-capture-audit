"""The capture predicate must be SATISFIABLE in the simulator, not only consistent on paper.

A-45 measured that D06 passed every consistency check and was nonetheless impossible in
SUMO: the default collision semantics called the whole capture band a collision, and safe
following stopped every vehicle outside it. The checks below were missing. Each has a test
that it fires, because a guard with no such test is how the original gap went unnoticed.
"""

from __future__ import annotations

import copy
import unittest

from _support import ROOT  # noqa: F401
from joint_interception.domain.contracts import (  # noqa: E402
    CaptureParameters,
    load_domain,
    min_gap_for,
    simulator_arguments,
)


def problems(domain: dict) -> list[str]:
    return CaptureParameters.from_domain(domain).consistency_problems(domain)


class TestTheFrozenDomainIsSatisfiable(unittest.TestCase):
    def test_the_current_domain_has_no_consistency_problems(self):
        self.assertEqual(problems(load_domain()), [])

    def test_a_trailing_pursuer_stops_outside_the_band(self):
        d = load_domain()
        band_max = d["capture_predicate"]["parameters"]["contact_gap_max_m"]["value"]
        self.assertGreater(min_gap_for("pursuer", d), band_max)

    def test_an_evader_stopped_behind_a_pursuer_rests_inside_the_band(self):
        d = load_domain()
        params = d["capture_predicate"]["parameters"]
        low, high = params["contact_gap_min_m"]["value"], params["contact_gap_max_m"]["value"]
        self.assertTrue(low <= min_gap_for("evader", d) <= high)

    def test_collision_means_physical_overlap(self):
        self.assertEqual(simulator_arguments(), ["--collision.mingap-factor", "0"])


class TestEachCheckFires(unittest.TestCase):
    """Break the domain one way at a time; the consistency check must object each time."""

    def mutate(self, edit):
        d = copy.deepcopy(load_domain())
        edit(d)
        return problems(d)

    def test_missing_evader_min_gap_is_caught(self):
        found = self.mutate(lambda d: d["vehicle"]["min_gap_m_by_class"].pop("evader"))
        self.assertTrue(any("evader min_gap" in p for p in found), found)

    def test_evader_min_gap_outside_the_band_is_caught(self):
        found = self.mutate(lambda d: d["vehicle"]["min_gap_m_by_class"].update(evader=2.5))
        self.assertTrue(any("evader min_gap" in p for p in found), found)

    def test_pursuer_min_gap_inside_the_band_is_caught(self):
        """This is the configuration that would let ordinary following count as capture."""
        found = self.mutate(lambda d: d["vehicle"]["min_gap_m_by_class"].update(pursuer=1.0))
        self.assertTrue(any("pursuer min_gap" in p for p in found), found)

    def test_sumo_default_collision_semantics_are_caught(self):
        found = self.mutate(lambda d: d["simulator"].update(collision_mingap_factor=None))
        self.assertTrue(any("collision_mingap_factor" in p for p in found), found)

    def test_a_nonzero_factor_is_caught(self):
        found = self.mutate(lambda d: d["simulator"].update(collision_mingap_factor=1))
        self.assertTrue(any("collision_mingap_factor" in p for p in found), found)


class TestTheAdmissionModuleIsAlignedWithTheSimulator(unittest.TestCase):
    """`safety/admission.py` judges collision by PHYSICAL separation and never reads min_gap.

    That is correct only while the simulator also means physical overlap by a collision.
    Under SUMO's default it reproduced the O22 Roma failure class (A-45). This test ties the
    module's soundness to the setting it depends on.
    """

    def test_the_module_assumption_holds_in_the_frozen_configuration(self):
        self.assertEqual(load_domain()["simulator"]["collision_mingap_factor"], 0)


if __name__ == "__main__":
    unittest.main()
