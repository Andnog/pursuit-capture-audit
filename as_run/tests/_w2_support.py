"""Support for the W2 contract tests.

W2 introduces the project's first third-party dependency (`jsonschema`). The W0-W1 finite
examples must stay reproducible on the standard library alone, so every W2 test module
SKIPS rather than errors when the dependency is absent. Both invocations therefore work:

    python3 -m unittest discover -s tests -t tests      # W1 runs, W2 skips
    uv run python -m unittest discover -s tests -t tests  # everything runs
"""

from __future__ import annotations

import importlib.util
import unittest

from _support import ROOT  # noqa: F401  (re-exported for W2 modules)

HAVE_JSONSCHEMA = importlib.util.find_spec("jsonschema") is not None
requires_contracts = unittest.skipUnless(
    HAVE_JSONSCHEMA,
    "jsonschema not installed; run `uv sync` and use `uv run python -m unittest ...`",
)


def document_text(*relative_parts: str) -> str:
    """Read a project document with whitespace collapsed to single spaces.

    Assertions about document content must not depend on where a line happens to wrap or
    on markdown emphasis inside a phrase. Comparing collapsed text removes that whole
    class of brittleness; three separate test failures in W1 and W2 came from it.
    """
    import os
    import re

    path = os.path.join(ROOT, *relative_parts)
    with open(path, encoding="utf-8") as handle:
        return re.sub(r"\s+", " ", handle.read().replace("**", ""))
