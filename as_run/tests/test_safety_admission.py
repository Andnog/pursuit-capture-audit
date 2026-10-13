"""Safety admission: trivalent, and UNKNOWN is never permission to execute."""

from __future__ import annotations

import unittest

from _w2_support import document_text, requires_contracts  # noqa: E402


@requires_contracts
class TestStoppingDistance(unittest.TestCase):
    def test_ordinary_braking_formula(self):
        """v^2 / (2a): 10 m/s at 4.5 m/s^2 gives 100/9 = 11.111... m."""
        from joint_interception.safety.admission import stopping_distance_m

        self.assertAlmostEqual(stopping_distance_m(10.0, 4.5), 100.0 / 9.0, places=9)
        self.assertEqual(stopping_distance_m(0.0, 4.5), 0.0)

    def test_invalid_inputs_are_refused(self):
        from joint_interception.safety.admission import stopping_distance_m

        with self.assertRaises(ValueError):
            stopping_distance_m(10.0, 0.0)
        with self.assertRaises(ValueError):
            stopping_distance_m(-1.0, 4.5)


@requires_contracts
class TestImmediateStepAdmission(unittest.TestCase):
    def setUp(self):
        from joint_interception.domain.geometry import Rectangle

        self.actor = Rectangle(0.0, 0.0, 0.0, 5.0, 1.8)
        self.Rectangle = Rectangle
        self.tolerance = 0.01
        self.step = 0.1

    def _admit(self, others, speed=3.0, unresolved=frozenset()):
        from joint_interception.safety.admission import admit_immediate_step

        return admit_immediate_step(
            self.actor, speed, others, self.step, self.tolerance, unresolved
        )

    def test_clear_step_is_supported(self):
        """Neighbour in line at 10.0 m: separation 5.0 m; a 0.1 s step at 3 m/s covers 0.3 m."""
        from joint_interception.opportunities.types import Verdict

        result = self._admit({"p2": self.Rectangle(10.0, 0.0, 0.0, 5.0, 1.8)})
        self.assertEqual(result.verdict, Verdict.SUPPORTED)
        self.assertTrue(result.permits_execution)
        self.assertAlmostEqual(result.detail["gap_m"], 5.0, places=9)

    def test_overlap_is_rejected(self):
        """Neighbour at 4.0 m in line with length 5.0: the bodies already overlap."""
        from joint_interception.opportunities.types import Verdict

        result = self._admit({"p2": self.Rectangle(4.0, 0.0, 0.0, 5.0, 1.8)})
        self.assertEqual(result.verdict, Verdict.REJECTED)
        self.assertEqual(result.reason, "body_overlap_at_current_state")
        self.assertFalse(result.permits_execution)

    def test_step_that_could_close_the_gap_is_rejected(self):
        """Separation 0.2 m; the step covers 0.3 m, so the gap can close within tolerance."""
        from joint_interception.opportunities.types import Verdict

        result = self._admit({"p2": self.Rectangle(5.2, 0.0, 0.0, 5.0, 1.8)})
        self.assertEqual(result.verdict, Verdict.REJECTED)
        self.assertEqual(result.reason, "step_could_close_gap_within_tolerance")

    def test_unresolved_neighbour_yields_unknown_not_permission(self):
        """The central property: unresolved admission is NOT permission to execute."""
        from joint_interception.opportunities.types import Verdict

        result = self._admit(
            {"p2": self.Rectangle(10.0, 0.0, 0.0, 5.0, 1.8)}, unresolved=frozenset({"p2"})
        )
        self.assertEqual(result.verdict, Verdict.UNKNOWN)
        self.assertFalse(result.permits_execution)

    def test_rejection_beats_unresolved(self):
        """A proof of overlap is not weakened by ignorance about the same neighbour."""
        from joint_interception.opportunities.types import Verdict

        result = self._admit(
            {"p2": self.Rectangle(4.0, 0.0, 0.0, 5.0, 1.8)}, unresolved=frozenset({"p2"})
        )
        self.assertEqual(result.verdict, Verdict.REJECTED)

    def test_unresolved_distant_neighbour_still_blocks_support(self):
        from joint_interception.opportunities.types import Verdict

        others = {
            "p2": self.Rectangle(10.0, 0.0, 0.0, 5.0, 1.8),
            "p3": self.Rectangle(80.0, 0.0, 0.0, 5.0, 1.8),
        }
        result = self._admit(others, unresolved=frozenset({"p3"}))
        self.assertEqual(result.verdict, Verdict.UNKNOWN)


@requires_contracts
class TestSequenceAdmission(unittest.TestCase):
    def test_kleene_conjunction_over_steps(self):
        from joint_interception.opportunities.types import Verdict
        from joint_interception.safety.admission import admit_sequence

        supported = [Verdict.SUPPORTED] * 5
        self.assertEqual(admit_sequence(supported).verdict, Verdict.SUPPORTED)
        self.assertEqual(admit_sequence(supported + [Verdict.UNKNOWN]).verdict, Verdict.UNKNOWN)
        self.assertEqual(
            admit_sequence(supported + [Verdict.UNKNOWN, Verdict.REJECTED]).verdict,
            Verdict.REJECTED,
        )

    def test_empty_sequence_is_unknown_nothing_was_checked(self):
        from joint_interception.opportunities.types import Verdict
        from joint_interception.safety.admission import admit_sequence

        result = admit_sequence([])
        self.assertEqual(result.verdict, Verdict.UNKNOWN)
        self.assertFalse(result.permits_execution)

    def test_one_supported_step_does_not_certify_a_sequence(self):
        """Finite case F5, at the admission layer rather than the opportunity layer."""
        from joint_interception.opportunities.types import Verdict
        from joint_interception.safety.admission import admit_sequence

        self.assertEqual(
            admit_sequence([Verdict.SUPPORTED, Verdict.UNKNOWN]).verdict, Verdict.UNKNOWN
        )


@requires_contracts
class TestGuardIsNotAShield(unittest.TestCase):
    def test_contract_records_that_o22_remains_open(self):
        """The admission interface must not be described as a verified shield anywhere."""
        text = document_text("contracts", "TASK_CONTRACT_EN.md")
        self.assertIn("not a formally synthesised shield", text, "shield disclaimer missing")
        self.assertIn("O22", text, "O22 not referenced in the task contract")


if __name__ == "__main__":
    unittest.main()
