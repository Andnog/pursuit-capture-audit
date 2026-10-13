"""A-146 (sixth review, F6-2): sealing checks that no process still writes to the package."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

HAVE_LSOF = bool(shutil.which("lsof")) or os.path.exists("/usr/sbin/lsof")
HOLD = (
    "import sys,time; f=open(sys.argv[1], sys.argv[2]); print('ready', flush=True); time.sleep(120)"
)


def _package(folder):
    with open(os.path.join(folder, "results.jsonl"), "w", encoding="utf-8") as h:
        h.write('{"key": "a"}\n')
    with open(os.path.join(folder, "run.log"), "w", encoding="utf-8") as h:
        h.write("episode 1 ok\n")
    return folder


def _hold(path, mode):
    child = subprocess.Popen([sys.executable, "-c", HOLD, path, mode], stdout=subprocess.PIPE)
    child.stdout.readline()  # the file is open
    return child


class TestParseLsof(unittest.TestCase):
    def test_only_handles_open_for_writing_are_listed(self):
        import package_tools as pt

        text = "\n".join(
            [
                "p100", "csumo", "f1", "aw", "n/pkg/run.log", "f2", "aw", "n/pkg/run.log",
                "f5", "ar", "n/pkg/results.jsonl",
                "p200", "cPython", "f3", "au", "n/pkg/state.pkl", "fcwd", "a ", "n/pkg",
                "p300", "cself", "f4", "aw", "n/pkg/own.log",
            ]
        )  # fmt: skip
        got = pt.parse_lsof(text, own_pid=300)
        self.assertEqual(
            [(w["pid"], w["fd"], w["access"]) for w in got],
            [(100, "1", "w"), (100, "2", "w"), (200, "3", "u")],
        )
        self.assertEqual(got[0]["command"], "sumo")
        self.assertEqual(got[2]["name"], "/pkg/state.pkl")
        self.assertEqual(pt.parse_lsof(""), [])


@unittest.skipUnless(HAVE_LSOF, "lsof not available")
class TestSealChecksWriters(unittest.TestCase):
    def setUp(self):
        import package_tools as pt

        self.pt = pt

    def test_a_live_writer_blocks_the_seal_and_nothing_is_written(self):
        with tempfile.TemporaryDirectory() as folder:
            _package(folder)
            child = _hold(os.path.join(folder, "run.log"), "a")
            try:
                with self.assertRaises(SystemExit) as raised:
                    self.pt.seal(folder)
                self.assertIn("open for writing", str(raised.exception))
                self.assertIn(str(child.pid), str(raised.exception))
                self.assertFalse(os.path.exists(os.path.join(folder, "checksums.json")))
                report = self.pt.writers_report([folder])
                self.assertEqual(report["packages_with_a_writer"], 1)
            finally:
                child.kill()
                child.wait()
                child.stdout.close()
            out = self.pt.seal(folder)  # the writer has ended
            self.assertEqual(out["schema_version"], 2)
            self.assertIs(out["sealed_after_all_writers_ended"], True)
            self.assertTrue(out["writers_check"]["performed"])
            self.assertEqual(out["writers_check"]["open_for_writing"], [])
            self.assertEqual(sorted(out["files"]), ["results.jsonl", "run.log"])
            self.assertEqual(self.pt.verify(folder)["changed"], [])
            with open(os.path.join(folder, "checksums.json"), encoding="utf-8") as h:
                self.assertEqual(json.load(h)["writers_check"]["method"], self.pt.LSOF_METHOD)

    def test_a_reader_does_not_block_the_seal(self):
        with tempfile.TemporaryDirectory() as folder:
            _package(folder)
            child = _hold(os.path.join(folder, "results.jsonl"), "r")
            try:
                self.assertIs(self.pt.seal(folder)["sealed_after_all_writers_ended"], True)
            finally:
                child.kill()
                child.wait()
                child.stdout.close()

    def test_a_sealed_package_is_not_resealed(self):
        with tempfile.TemporaryDirectory() as folder:
            self.pt.seal(_package(folder))
            with self.assertRaises(SystemExit):
                self.pt.seal(folder)


class TestSealWithoutACheck(unittest.TestCase):
    def test_without_lsof_the_seal_needs_the_operator_and_says_so(self):
        import package_tools as pt

        with (
            tempfile.TemporaryDirectory() as folder,
            patch.object(pt, "open_for_writing", return_value=None),
        ):
            _package(folder)
            with self.assertRaises(SystemExit) as raised:
                pt.seal(folder)
            self.assertIn("cannot be checked", str(raised.exception))
            self.assertFalse(os.path.exists(os.path.join(folder, "checksums.json")))
            out = pt.seal(folder, operator_certifies=True)
            self.assertEqual(
                out["sealed_after_all_writers_ended"], "declared by the operator; not checked"
            )
            self.assertFalse(out["writers_check"]["performed"])
            self.assertIsNone(out["writers_check"]["open_for_writing"])
            self.assertFalse(pt.writers_report([folder])["performed"])


if __name__ == "__main__":
    unittest.main()
