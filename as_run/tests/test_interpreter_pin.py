"""The tests must run on the interpreter the project pins.

This exists because they did not. `pyproject.toml` pins `requires-python = "==3.14.*"`,
but `pytest` was never installed into the virtual environment, so `uv run pytest` fell
through to a `pytest` on PATH belonging to a **Python 3.10** framework install. Every test
result recorded before 2026-09-21 was therefore measured on 3.10 while the environment
records alongside it said 3.14.6.

It was not a harmless difference. Python 3.12 changed the tokenizer, and a source-hygiene
check that passed on 3.10 was silently inert on 3.14.

Deliberately written with no third-party import and no `tomllib`, so that it runs on the
wrong interpreter and reports it, rather than failing to collect.
"""

from __future__ import annotations

import re
import sys
import unittest

from _support import ROOT  # noqa: E402

PYPROJECT = f"{ROOT}/pyproject.toml"


def pinned_specifier() -> str:
    with open(PYPROJECT, encoding="utf-8") as handle:
        for line in handle:
            match = re.match(r'\s*requires-python\s*=\s*["\']([^"\']+)["\']', line)
            if match:
                return match.group(1)
    raise AssertionError("pyproject.toml declares no requires-python")


class TestInterpreterMatchesThePin(unittest.TestCase):
    def test_running_interpreter_satisfies_requires_python(self):
        specifier = pinned_specifier()
        match = re.fullmatch(r"==(\d+)\.(\d+)\.\*", specifier.strip())
        self.assertIsNotNone(
            match,
            f"this check understands only an '==X.Y.*' pin; pyproject declares {specifier!r}",
        )
        major, minor = int(match.group(1)), int(match.group(2))
        running = (sys.version_info.major, sys.version_info.minor)
        self.assertEqual(
            running,
            (major, minor),
            f"tests are running on Python {running[0]}.{running[1]} but the project pins "
            f"{specifier}. Interpreter: {sys.executable}. "
            f"Use `uv run python -m unittest discover -s tests`, or install the runner into "
            f"the virtual environment. A test result from an unpinned interpreter does not "
            f"describe this project.",
        )


if __name__ == "__main__":
    unittest.main()
