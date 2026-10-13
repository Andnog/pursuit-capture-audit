"""Shared fixtures: the frozen snapshot and the frozen code as the reference implementation."""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAPSHOT = os.path.join(ROOT, "as_run")

# The frozen code is importable in the tests, and only there: it is what the library is compared
# with, never something the library depends on.
sys.path.insert(0, os.path.join(SNAPSHOT, "src"))


@pytest.fixture(scope="session")
def snapshot() -> str:
    """Path of the frozen layer."""
    return SNAPSHOT


@pytest.fixture(scope="session")
def experiments(snapshot: str) -> str:
    """Path of the sealed evidence packages."""
    return os.path.join(snapshot, "experiments")


@pytest.fixture(scope="session")
def examples(snapshot: str) -> str:
    """Path of the example traces."""
    return os.path.join(snapshot, "audit_kit", "examples")
