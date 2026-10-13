"""Commitment memory: case F6 and the J0/J1 degeneracy."""

from __future__ import annotations

import unittest

from _support import case, load_config, load_fixture  # noqa: E402
from joint_interception.opportunities.types import Verdict  # noqa: E402
from joint_interception.policies.memory import (  # noqa: E402
    CommitmentMemory,
    CommitmentParameters,
    run_decision_sequence,
    select_action,
)


def steps_from_config(config):
    spec = case(config, "F6")
    out = []
    for decision in spec["decisions"]:
        verdicts = {k: Verdict(v) for k, v in decision["candidate_verdicts"].items()}
        out.append((decision["t"], decision["candidate_scores"], verdicts))
    return out


def params(config, arm):
    values = config["commitment_parameters"][arm]
    return CommitmentParameters(
        max_commit_duration=values["max_commit_duration"],
        switch_margin=values["switch_margin"],
        unknown_tolerance=values["unknown_tolerance"],
    )


class TestCaseF6(unittest.TestCase):
    def setUp(self):
        self.config = load_config()
        self.expected = load_fixture()["representation_expectations"]["F6"]
        self.steps = steps_from_config(self.config)

    def test_J1_holds_the_commitment(self):
        decisions = run_decision_sequence(self.steps, params(self.config, "J1"))
        expected = self.expected["J1"]
        self.assertEqual(decisions[0].selected_opportunity_id, expected["t1_selected"])
        self.assertEqual(decisions[0].decision, expected["t1_decision"])
        self.assertEqual(decisions[1].selected_opportunity_id, expected["t2_selected"])
        self.assertEqual(decisions[1].decision, expected["t2_decision"])
        self.assertEqual(decisions[-1].selected_opportunity_id, expected["final_selected"])
        self.assertEqual(decisions[-1].memory.switch_count, expected["switch_count"])

    def test_J0_reselects(self):
        decisions = run_decision_sequence(self.steps, params(self.config, "J0"))
        expected = self.expected["J0"]
        self.assertEqual(decisions[0].selected_opportunity_id, expected["t1_selected"])
        self.assertEqual(decisions[1].selected_opportunity_id, expected["t2_selected"])
        self.assertEqual(decisions[-1].selected_opportunity_id, expected["final_selected"])

    def test_memory_changes_the_later_choice(self):
        j1 = run_decision_sequence(self.steps, params(self.config, "J1"))
        j0 = run_decision_sequence(self.steps, params(self.config, "J0"))
        self.assertNotEqual(j1[-1].selected_opportunity_id, j0[-1].selected_opportunity_id)
        self.assertTrue(self.expected["memory_changes_later_choice"])


class TestArmDegeneracy(unittest.TestCase):
    """J0 is the J1 code path with degenerate constants, not a second implementation."""

    def test_degenerate_parameters_reproduce_J0_exactly(self):
        config = load_config()
        steps = steps_from_config(config)
        degenerate = CommitmentParameters(
            max_commit_duration=1, switch_margin=0.0, unknown_tolerance=0
        )
        left = run_decision_sequence(steps, degenerate)
        right = run_decision_sequence(steps, params(config, "J0"))
        self.assertEqual(
            [(d.t, d.selected_opportunity_id, d.decision) for d in left],
            [(d.t, d.selected_opportunity_id, d.decision) for d in right],
        )
        self.assertTrue(
            load_fixture()["representation_expectations"]["F6"]["degeneracy_assertion"][
                "expected_equal"
            ]
        )


class TestSelectionRuleProperties(unittest.TestCase):
    def test_unknown_candidate_is_never_selectable(self):
        decision = select_action(
            1,
            {"X": 0.9},
            {"X": Verdict.UNKNOWN},
            CommitmentMemory(),
            CommitmentParameters(10, 0.1, 2),
        )
        self.assertEqual(decision.decision, "FALLBACK")
        self.assertIsNone(decision.selected_opportunity_id)

    def test_rejected_commitment_is_abandoned(self):
        memory = CommitmentMemory(
            committed_opportunity_id="X", committed_at=1, last_verdict=Verdict.SUPPORTED
        )
        decision = select_action(
            2, {"X": 0.9}, {"X": Verdict.REJECTED}, memory, CommitmentParameters(10, 0.1, 2)
        )
        self.assertEqual(decision.decision, "ABANDON")
        self.assertEqual(decision.reason, "committed_opportunity_rejected")

    def test_unknown_tolerance_is_enforced(self):
        rules = CommitmentParameters(max_commit_duration=10, switch_margin=0.1, unknown_tolerance=2)
        memory = CommitmentMemory(
            committed_opportunity_id="X", committed_at=0, last_verdict=Verdict.SUPPORTED
        )
        for step in (1, 2):
            decision = select_action(step, {"X": 0.9}, {"X": Verdict.UNKNOWN}, memory, rules)
            self.assertEqual(decision.decision, "CONTINUE")
            memory = decision.memory
        decision = select_action(3, {"X": 0.9}, {"X": Verdict.UNKNOWN}, memory, rules)
        self.assertEqual(decision.decision, "ABANDON")
        self.assertEqual(decision.reason, "unknown_tolerance_exceeded")

    def test_no_supported_candidate_yields_fallback_not_an_invented_action(self):
        decision = select_action(1, {}, {}, CommitmentMemory(), CommitmentParameters(10, 0.1, 2))
        self.assertEqual(decision.decision, "FALLBACK")
        self.assertIsNone(decision.selected_opportunity_id)

    def test_switch_requires_strictly_exceeding_the_margin(self):
        rules = CommitmentParameters(
            max_commit_duration=10, switch_margin=0.10, unknown_tolerance=2
        )
        memory = CommitmentMemory(
            committed_opportunity_id="X", committed_at=1, last_verdict=Verdict.SUPPORTED
        )
        verdicts = {"X": Verdict.SUPPORTED, "Y": Verdict.SUPPORTED}
        at_margin = select_action(2, {"X": 0.58, "Y": 0.68}, verdicts, memory, rules)
        self.assertEqual(at_margin.decision, "CONTINUE")
        above = select_action(2, {"X": 0.58, "Y": 0.69}, verdicts, memory, rules)
        self.assertEqual(above.decision, "SWITCH")
        self.assertEqual(above.memory.switch_count, 1)

    def test_tie_break_is_deterministic(self):
        verdicts = {"A": Verdict.SUPPORTED, "B": Verdict.SUPPORTED}
        for _ in range(5):
            decision = select_action(
                1,
                {"A": 0.5, "B": 0.5},
                verdicts,
                CommitmentMemory(),
                CommitmentParameters(10, 0.1, 2),
            )
            self.assertEqual(decision.selected_opportunity_id, "A")


if __name__ == "__main__":
    unittest.main()
