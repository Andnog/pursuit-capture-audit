"""Verify the public snapshot against a versioned inventory outside the frozen evidence."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from importlib import resources

from .package import EvidencePackage, sha256_of


@dataclass
class SnapshotVerification:
    """Counts and actionable problems from an inventory-aware verification."""

    matched: int = 0
    absent: int = 0
    damaged: int = 0
    archive_absent: int = 0
    errors: list[str] = field(default_factory=list)


def load_inventory(path: str | None = None) -> dict:
    """Read the checked-in inventory or an explicitly supplied alternative."""
    if path:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(resources.files(__package__).joinpath("inventory.json").read_text())


def verify_snapshot(
    snapshot: str, *, complete: bool = False, inventory_path: str | None = None
) -> SnapshotVerification:
    """Check expected packages, seal hashes and only the explicitly permitted omissions.

    Complete mode also requires every companion-archive file, including unsealed demo assets.
    Neither mode writes to the snapshot. These hashes establish consistency, not authenticity
    or an external timestamp for the original experiments.
    """
    result = SnapshotVerification()
    try:
        inventory = load_inventory(inventory_path)
        manifest_path = os.path.join(snapshot, "SNAPSHOT.json")
        if sha256_of(manifest_path) != inventory["snapshot_sha256"]:
            raise ValueError("SNAPSHOT.json differs from the public inventory")
        with open(manifest_path, encoding="utf-8") as handle:
            archive = json.load(handle)["archive_only"]
        expected = inventory["packages"]
        if not isinstance(expected, dict) or not expected:
            raise ValueError("inventory must name the expected packages")
        companion_hashes = inventory.get("companion_hashes", {})
        permitted = {
            entry["path"]: entry["sha256"] or companion_hashes.get(entry["path"])
            for entry in archive
        }
        if any(not digest for digest in permitted.values()):
            raise ValueError("companion file lacks both a sealed hash and an inventory hash")
        root = os.path.join(snapshot, "experiments")
        present = {name for name in os.listdir(root) if os.path.isdir(os.path.join(root, name))}
    except (OSError, ValueError, KeyError, TypeError) as error:
        result.errors.append(f"inventory: {error}")
        return result

    result.errors += [f"missing package: {name}" for name in sorted(set(expected) - present)]
    result.errors += [f"unlisted package: {name}" for name in sorted(present - set(expected))]
    for name in sorted(set(expected) & present):
        entry = expected[name]
        package = EvidencePackage(os.path.join(root, name))
        if entry["kind"] == "demonstration":
            if package.has("checksums.json"):
                result.errors.append(f"{name}: unexpected seal on a demonstration directory")
            continue
        try:
            if sha256_of(os.path.join(package.path, "checksums.json")) != entry["seal_sha256"]:
                result.errors.append(f"{name}: checksums.json differs from the inventory")
        except OSError as error:
            result.errors.append(f"{name}: {error}")
        checked = package.verify()
        result.matched += len(checked.matched)
        result.absent += len(checked.absent)
        result.damaged += bool(checked.mismatched)
        result.errors += [f"{name}: {error}" for error in checked.errors]
        result.errors += [f"DIFFERS {name}/{path}" for path in checked.mismatched]
        for path in checked.absent:
            if f"experiments/{name}/{path}" not in permitted:
                result.errors.append(f"missing required file: {name}/{path}")

    _check_companion(snapshot, permitted, complete, result)
    return result


def _check_companion(
    snapshot: str, permitted: dict, complete: bool, result: SnapshotVerification
) -> None:
    """Check listed companion files independently of package seals."""
    for relative, digest in permitted.items():
        path = os.path.join(snapshot, relative)
        if not os.path.isfile(path):
            result.archive_absent += 1
            if complete:
                result.errors.append(f"missing companion file: {relative}")
        else:
            try:
                if sha256_of(path) != digest:
                    result.errors.append(f"companion file differs from inventory: {relative}")
            except OSError as error:
                result.errors.append(f"companion file unreadable: {relative}: {error}")
