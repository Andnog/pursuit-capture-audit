"""Input hashing for evidence rows."""

from __future__ import annotations

import hashlib
import os


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_inputs(paths: list[str], root: str = ".") -> dict[str, str]:
    """Hash every input an evidence row depends on.

    A missing input raises rather than being silently skipped: a row whose provenance is
    incomplete cannot be distinguished later from one whose inputs were never recorded.
    """
    out: dict[str, str] = {}
    for relative in sorted(paths):
        full = relative if os.path.isabs(relative) else os.path.join(root, relative)
        if not os.path.isfile(full):
            raise FileNotFoundError(f"input not found, cannot record provenance: {relative}")
        out[relative] = sha256_of(full)
    return out
