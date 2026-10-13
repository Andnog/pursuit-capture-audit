"""Assistance accounting: cases A1-A8 against the frozen fixture."""

from __future__ import annotations

import unittest

from _support import assistance_case, load_config, load_fixture  # noqa: E402
from joint_interception.evaluation.assistance_audit import (  # noqa: E402
    Admission,
    Alternative,
    AssistanceLabel,
    audit_assistance,
    contrast_bounds,
    effects_are_additive,
    endpoint_bounds,
    outcome_bounds,
)


def build_family(spec):
    return [
        Alternative(
            alternative=item["alternative"],
            admission=Admission(item["admission"]),
            outcome=item["outcome"],
        )
        for item in spec["declared_family"]
    ]


class TestBounds(unittest.TestCase):
    def test_unknown_outcome_is_zero_one_not_assumed_zero(self):
        self.assertEqual(outcome_bounds("UNKNOWN"), (0.0, 1.0))
        self.assertEqual(outcome_bounds(0), (0.0, 0.0))
        self.assertEqual(outcome_bounds(1), (1.0, 1.0))

    def test_contrast_bounds_formula(self):
        self.assertEqual(contrast_bounds(1, 0), (1.0, 1.0))
        self.assertEqual(contrast_bounds(1, 1), (0.0, 0.0))
        self.assertEqual(contrast_bounds(1, "UNKNOWN"), (0.0, 1.0))

    def test_non_binary_outcome_rejected(self):
        with self.assertRaises(ValueError):
            outcome_bounds(0.5)

    def test_endpoint_bounds_are_logical_not_statistical(self):
        self.assertEqual(endpoint_bounds(supported=3, unresolved=2, executed=10), (0.3, 0.5))
        with self.assertRaises(ValueError):
            endpoint_bounds(0, 0, 0)


class TestAssistanceCases(unittest.TestCase):
    def setUp(self):
        self.config = load_config()
        self.fixture = load_fixture()["assistance_expectations"]

    def _run(self, case_id):
        spec = assistance_case(self.config, case_id)
        return spec, audit_assistance(spec["helper"], spec["factual_outcome"], build_family(spec))

    def _check_common(self, case_id):
        spec, result = self._run(case_id)
        expected = self.fixture[case_id]
        with self.subTest(case=case_id, field="label"):
            self.assertEqual(result.label.value, expected["label"])
        with self.subTest(case=case_id, field="envelope"):
            self.assertAlmostEqual(result.envelope[0], expected["envelope"][0])
            self.assertAlmostEqual(result.envelope[1], expected["envelope"][1])
        with self.subTest(case=case_id, field="incomplete_family"):
            self.assertEqual(result.incomplete_family, expected["incomplete_family"])
        with self.subTest(case=case_id, field="complete_family_conclusion_permitted"):
            self.assertEqual(
                result.complete_family_conclusion_permitted,
                expected["complete_family_conclusion_permitted"],
            )
        with self.subTest(case=case_id, field="per_alternative_bounds"):
            observed = {k: list(v) for k, v in result.per_alternative_bounds.items()}
            self.assertEqual(observed, expected["per_alternative_bounds"])
        return spec, result, expected

    def test_A1_necessary_helper(self):
        _, result, _ = self._check_common("A1")
        self.assertIs(result.label, AssistanceLabel.POSITIVE_ACROSS_FAMILY)

    def test_A2_redundant_pair_does_not_sum(self):
        spec, result, expected = self._check_common("A2")
        individual = [0.0, 0.0]
        coalition = float(1 - spec["coalition_note"]["joint_withdrawal_of_h1_and_h2_outcome"])
        self.assertAlmostEqual(coalition, expected["coalition_effect"])
        self.assertEqual(effects_are_additive(individual, coalition), expected["additivity_holds"])
        self.assertFalse(expected["absence_of_coordination_inferred"])

    def test_A3_occupancy_unchanged_by_policy_substitution(self):
        spec, result, expected = self._check_common("A3")
        self.assertTrue(spec["effect_not_identifiable_by_policy_substitution"])
        self.assertTrue(expected["effect_not_identifiable_by_policy_substitution"])
        self.assertIs(result.label, AssistanceLabel.NO_POSITIVE_EFFECT_DEMONSTRATED)

    def test_A4_guard_equivalent_commands(self):
        spec, _, expected = self._check_common("A4")
        execution = spec["execution"]
        self.assertEqual(
            execution["factual_executed_command"] == execution["alternative_executed_command"],
            expected["executed_commands_identical"],
        )
        self.assertEqual(
            execution["factual_intent"] == execution["alternative_intent"],
            expected["intentions_identical"],
        )

    def test_A5_baseline_dependent(self):
        _, result, _ = self._check_common("A5")
        self.assertIs(result.label, AssistanceLabel.BASELINE_DEPENDENT)

    def test_A6_unresolved_transition(self):
        _, result, expected = self._check_common("A6")
        self.assertIs(result.label, AssistanceLabel.INSUFFICIENT_SUPPORT)
        # The two completions reverse the conclusion.
        self.assertEqual(contrast_bounds(1, 0), (1.0, 1.0))
        self.assertEqual(contrast_bounds(1, 1), (0.0, 0.0))
        self.assertTrue(expected["completions_reverse_conclusion"])

    def test_A7_delayed_memory_effect(self):
        spec, _, expected = self._check_common("A7")
        execution = spec["execution"]
        self.assertTrue(execution["step_1_next_state_identical"])
        self.assertFalse(execution["step_2_executed_command_identical"])
        self.assertFalse(expected["one_step_equality_implies_trajectory_equality"])

    def test_A8_time_varying_admission(self):
        _, result, expected = self._check_common("A8")
        self.assertTrue(result.incomplete_family)
        self.assertFalse(result.complete_family_conclusion_permitted)
        self.assertEqual(result.excluded_members, expected["excluded_members"])
        self.assertFalse(expected["one_step_admission_certifies_sequence"])


class TestAssistanceProperties(unittest.TestCase):
    def test_family_expansion_cannot_narrow_the_envelope(self):
        base = [Alternative("b1", Admission.SUPPORTED_ADMISSIBLE, 0)]
        expanded = base + [Alternative("b3", Admission.SUPPORTED_ADMISSIBLE, 1)]
        before = audit_assistance("h1", 1, base).envelope
        after = audit_assistance("h1", 1, expanded).envelope
        self.assertLessEqual(after[0], before[0])
        self.assertGreaterEqual(after[1], before[1])

    def test_unresolved_member_blocks_complete_family_conclusion(self):
        family = [
            Alternative("b1", Admission.SUPPORTED_ADMISSIBLE, 0),
            Alternative("b2", Admission.UNRESOLVED, "UNKNOWN"),
        ]
        result = audit_assistance("h1", 1, family)
        self.assertTrue(result.incomplete_family)
        self.assertFalse(result.complete_family_conclusion_permitted)

    def test_no_resolved_member_yields_insufficient_support(self):
        family = [Alternative("b1", Admission.UNRESOLVED, "UNKNOWN")]
        result = audit_assistance("h1", 1, family)
        self.assertIs(result.label, AssistanceLabel.INSUFFICIENT_SUPPORT)

    def test_capture_with_unresolved_audit_is_never_a_positive_Z(self):
        family = [Alternative("b1", Admission.SUPPORTED_ADMISSIBLE, "UNKNOWN")]
        result = audit_assistance("h1", 1, family)
        self.assertIs(result.label, AssistanceLabel.INSUFFICIENT_SUPPORT)
        self.assertFalse(result.complete_family_conclusion_permitted)


if __name__ == "__main__":
    unittest.main()
