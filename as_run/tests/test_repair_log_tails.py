"""A-145: sealed logs with interrupt lines appended by leftover simulator processes."""

from __future__ import annotations

import hashlib
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


class TestRepairLogTails(unittest.TestCase):
    def setUp(self):
        import repair_log_tails as r

        self.r = r
        self.sealed = b"episode 1 ok\nWarning: something\nepisode 2 ok\n"
        self.digest = hashlib.sha256(self.sealed).hexdigest()

    def test_the_sealed_prefix_is_found_under_appended_lines(self):
        data = self.sealed + (self.r.LINE + b"\n") * 3
        cut = self.r.sealed_length(data, self.digest)
        self.assertEqual(cut, len(self.sealed))
        self.assertTrue(self.r.only_interrupt_lines(data[cut:]))

    def test_a_sealed_file_without_final_newline_is_found(self):
        sealed = self.sealed[:-1]
        data = sealed + self.r.LINE + b"\n"
        cut = self.r.sealed_length(data, hashlib.sha256(sealed).hexdigest())
        self.assertEqual(cut, len(sealed))

    def test_nul_bytes_left_by_a_non_append_descriptor_are_accepted(self):
        tail = b"\x00" * 54 + self.r.LINE + b"\n"
        self.assertTrue(self.r.only_interrupt_lines(tail))

    def test_any_other_appended_text_is_refused(self):
        for tail in (b"episode 3 ok\n", self.r.LINE + b"\nepisode 3 ok\n", b"", b"\n", b"\x00\x00"):
            self.assertFalse(self.r.only_interrupt_lines(tail), tail)

    def test_a_changed_body_has_no_sealed_prefix(self):
        data = self.sealed.replace(b"episode 1", b"episode 9") + self.r.LINE + b"\n"
        self.assertIsNone(self.r.sealed_length(data, self.digest))


if __name__ == "__main__":
    unittest.main()
