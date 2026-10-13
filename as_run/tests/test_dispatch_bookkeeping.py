"""A-119 (second review, R9): dispatch bookkeeping distinguishes accepted, rejected, no-route and
fallback orders; the legacy mode reproduces the behaviour of runs sealed before A-119."""

from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


class TestDispatch(unittest.TestCase):
    def setUp(self):
        from joint_interception.native.engine import record_dispatch

        self.record = record_dispatch
        self.cmd = ("seg", "edgeA", 12.0, 1)

    def _run(self, status, mode, applied=None):
        pending, applied = {"p1": self.cmd}, dict(applied or {})
        self.record(status, "p1", pending, applied, mode=mode)
        return pending, applied

    def test_checked_accepted_is_applied(self):
        pending, applied = self._run("accepted", "checked")
        self.assertEqual(applied["p1"], self.cmd)
        self.assertEqual(pending, {})

    def test_checked_no_route_is_not_recorded_as_applied(self):
        before = {"p1": ("seg", "old", None)}
        pending, applied = self._run("no_route", "checked", before)
        self.assertEqual(applied, before)  # the previous command stays in force
        self.assertEqual(pending, {})

    def test_checked_rejected_keeps_previous(self):
        pending, applied = self._run("rejected", "checked")
        self.assertNotIn("p1", applied)

    def test_checked_fallback_is_marked_and_retriable(self):
        _, applied = self._run("fallback", "checked")
        self.assertEqual(applied["p1"][0], "fallback")
        self.assertNotEqual(applied["p1"], self.cmd)  # an identical request is not suppressed

    def test_legacy_reproduces_the_historical_defect(self):
        for status in ("accepted", "no_route", "fallback"):
            _, applied = self._run(status, "legacy")
            self.assertEqual(applied["p1"], self.cmd)
        _, applied = self._run("rejected", "legacy")
        self.assertNotIn("p1", applied)

    def test_default_mode_is_checked(self):
        from joint_interception.native import engine

        self.assertEqual(engine.DISPATCH_MODE, "checked")


if __name__ == "__main__":
    unittest.main()
