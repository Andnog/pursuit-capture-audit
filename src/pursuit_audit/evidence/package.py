"""Sealed evidence packages: one directory per study, with a checksum for every file.

A package is sealed once, after every process that wrote to it has ended. Its ``checksums.json``
lists the SHA-256 of each file. This module reads packages and verifies them; it never writes to
one.

The repository holds the packages without their heavy files (run logs, pickled training states,
animations), which are in the data archive. Verification therefore distinguishes three cases for
a sealed file: present and matching, present and different, and absent from this copy.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass, field

_BLOCK_BYTES = 1 << 20


def sha256_of(path: str) -> str:
    """Return the SHA-256 of a file, as lowercase hexadecimal."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(_BLOCK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass
class Verification:
    """The result of comparing a package with its seal.

    Attributes:
        package: Name of the package.
        matched: Sealed files that are present and identical.
        absent: Sealed files that are not in this copy.
        mismatched: Sealed files that are present and differ.
        errors: Missing, malformed or unsafe seals.
    """

    package: str
    matched: list[str] = field(default_factory=list)
    absent: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def intact(self) -> bool:
        """Tell whether no present file differs from its seal."""
        return not self.mismatched and not self.errors

    @property
    def complete(self) -> bool:
        """Tell whether every sealed file is present and identical."""
        return self.intact and not self.absent


class EvidencePackage:
    """Read-only access to one sealed package."""

    def __init__(self, path: str) -> None:
        self.path = os.path.abspath(path)
        self.name = os.path.basename(self.path)
        parent = os.path.dirname(self.path)
        self.boundary = os.path.realpath(
            os.path.dirname(parent) if os.path.basename(parent) == "experiments" else self.path
        )

    def _read_json(self, name: str) -> dict:
        with open(os.path.join(self.path, name), encoding="utf-8") as handle:
            return json.load(handle)

    def has(self, name: str) -> bool:
        """Tell whether the package holds a file of that name."""
        return os.path.exists(os.path.join(self.path, name))

    @property
    def sealed_files(self) -> dict[str, str]:
        """Return the sealed checksum of every file, by relative path."""
        seal = self._read_json("checksums.json")
        files = seal.get("files") if isinstance(seal, dict) else None
        if not isinstance(files, dict) or not files:
            raise ValueError("checksums.json must contain a non-empty files mapping")
        for relative, digest in files.items():
            if (
                not relative
                or os.path.isabs(relative)
                or os.path.commonpath(
                    [self.boundary, os.path.realpath(os.path.join(self.path, relative))]
                )
                != self.boundary
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
            ):
                raise ValueError(f"invalid sealed entry: {relative!r}")
        return files

    def summary(self, name: str = "summary.json") -> dict:
        """Return a summary file of the package."""
        return self._read_json(name)

    def records(self, name: str = "results.jsonl") -> dict[str, dict]:
        """Return the per-episode records by key; a later record replaces an earlier one."""
        records = {}
        with open(os.path.join(self.path, name), encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    record = json.loads(line)
                    records[record["key"]] = record
        return records

    def verify(self) -> Verification:
        """Compare every sealed file that is present with its checksum."""
        result = Verification(self.name)
        try:
            files = self.sealed_files
        except (OSError, ValueError) as error:
            result.errors.append(str(error))
            return result
        for relative, sealed in sorted(files.items()):
            path = os.path.join(self.path, relative)
            if not os.path.exists(path):
                result.absent.append(relative)
            else:
                try:
                    if sha256_of(path) == sealed:
                        result.matched.append(relative)
                    else:
                        result.mismatched.append(relative)
                except OSError as error:
                    result.errors.append(f"{relative}: {error}")
        return result


def packages(root: str) -> Iterator[EvidencePackage]:
    """Yield the packages under a directory, in name order."""
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if os.path.isdir(path):
            yield EvidencePackage(path)
