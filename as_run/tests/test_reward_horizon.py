"""Horizon and reward semantics at the CONTRACT level.

The reward function is not implemented: it is W6 work under D17. What can be checked now
is that the contract's own arithmetic is consistent and that the horizon is enforced by
the episode-result invariants. Tests that would require a learner are deliberately absent
rather than faked.
"""

from __future__ import annotations

import json
import os
import unittest

from _support import ROOT  # noqa: E402
from _w2_support import document_text, requires_contracts  # noqa: E402


class TestHorizonArithmetic(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "configs", "domain_v1.json"), encoding="utf-8") as h:
            self.timing = json.load(h)["timing"]

    def test_step_and_decision_counts_are_consistent(self):
        t = self.timing
        self.assertAlmostEqual(
            t["decision_interval_s"] / t["physical_step_s"],
            t["physical_steps_per_decision"],
        )
        self.assertAlmostEqual(
            t["horizon_s"] / t["decision_interval_s"], t["decisions_per_episode"]
        )
        self.assertAlmostEqual(
            t["horizon_s"] / t["physical_step_s"], t["physical_steps_per_episode"]
        )

    def test_decision_interval_is_a_whole_number_of_physical_steps(self):
        ratio = self.timing["decision_interval_s"] / self.timing["physical_step_s"]
        self.assertAlmostEqual(ratio, round(ratio), places=9)

    def test_time_cost_accumulates_to_exactly_one_over_the_horizon(self):
        """The base reward's time term is -dt/300, so a full episode accrues -1.0.

        This is arithmetic on the CONTRACT, not a test of an implementation: no reward
        function exists yet.
        """
        horizon = self.timing["horizon_s"]
        step = self.timing["physical_step_s"]
        total = sum(step / horizon for _ in range(self.timing["physical_steps_per_episode"]))
        self.assertAlmostEqual(total, 1.0, places=9)

    def test_partial_episode_accrues_proportionally(self):
        horizon = self.timing["horizon_s"]
        self.assertAlmostEqual(sum(1.0 / horizon for _ in range(150)), 0.5, places=9)


@requires_contracts
class TestHorizonIsEnforcedOnResults(unittest.TestCase):
    def _record(self, **overrides):
        from test_contract_admission import valid_result

        record = valid_result()
        record.update(overrides)
        return record

    def test_endpoint_at_the_horizon_is_accepted(self):
        from joint_interception.domain.contracts import validate_episode_result

        validate_episode_result(self._record(endpoint_time_s=300.0))

    def test_endpoint_beyond_the_horizon_is_refused(self):
        from joint_interception.domain.contracts import ContractViolation, validate_episode_result

        with self.assertRaises(ContractViolation):
            validate_episode_result(self._record(endpoint_time_s=300.1))

    def test_capture_requires_an_endpoint_time(self):
        from joint_interception.domain.contracts import episode_result_invariants

        record = self._record(
            Y=1,
            Z="UNKNOWN",
            endpoint_cause="CAPTURE_MOVING_CIRCULATION",
            endpoint_time_s=None,
            audit_coverage=0.0,
        )
        self.assertTrue(
            any("requires endpoint_time_s" in p for p in episode_result_invariants(record))
        )


class TestRewardContractIsRecordedButNotImplemented(unittest.TestCase):
    def setUp(self):
        self.text = document_text("contracts", "REWARD_CONTRACT_EN.md")

    def test_no_reward_or_learner_module_exists(self):
        """W2 must not quietly build the W6 pipeline."""
        package = os.path.join(ROOT, "src", "joint_interception")
        self.assertFalse(os.path.isdir(os.path.join(package, "learning")))
        for directory, _, files in os.walk(package):
            for name in files:
                self.assertNotIn(
                    name,
                    {"ppo.py", "behavior_cloning.py", "reward.py"},
                    f"unexpected learner module {name} at {directory}",
                )

    def test_contract_distinguishes_truncation_from_termination(self):
        self.assertIn("Storage truncation is not termination", self.text, "missing")

    def test_contract_forbids_assigning_zero_to_unknown_evidence(self):
        self.assertIn("quarantined", self.text, "quarantine rule missing")
        self.assertIn("not assigned an invented reward", self.text, "invented-reward rule missing")

    def test_contract_records_the_telescoping_caution_for_shaping(self):
        self.assertIn("telescopes", self.text, "telescoping caution missing")


if __name__ == "__main__":
    unittest.main()
