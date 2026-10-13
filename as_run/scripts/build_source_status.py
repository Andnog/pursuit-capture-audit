"""Recoverability map of package sources (A-133, R4-C).

For every evidence package that recorded source hashes at launch, each recorded file is looked up
in the source archives under `provenance/` and in the current working tree. A package is fully
recoverable when every recorded file is found with the recorded hash in at least one archive.
Writes `provenance/PACKAGE_SOURCE_STATUS.json`; the map of 4 October is kept beside it.
"""

from __future__ import annotations

import hashlib
import json
import os
import tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experiments")
PROV = os.path.join(ROOT, "provenance")
SOURCE_KEYS = ("sources", "sources_sha256", "scripts", "script")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_index(path):
    """{member path: sha256} of one source archive."""
    out = {}
    with tarfile.open(path, "r:gz") as tar:
        for member in tar.getmembers():
            if member.isfile():
                out[member.name] = sha(tar.extractfile(member).read())
    return out


def recorded_sources(inputs: dict) -> dict:
    """{path: sha256} recorded by a package at launch, across the key names used over time."""
    out = {}
    for key in SOURCE_KEYS:
        value = inputs.get(key)
        if isinstance(value, dict):
            out.update({k: v for k, v in value.items() if isinstance(v, str) and len(v) == 64})
    return out


def classify(path, digest, archives, root=ROOT):
    """Where a recorded file can be recovered with its recorded hash."""
    for name, index in archives.items():
        if index.get(path) == digest:
            return f"in {name}"
    current = os.path.join(root, path)
    if os.path.isfile(current):
        with open(current, "rb") as h:
            if sha(h.read()) == digest:
                return "matches the working tree only (not yet archived)"
    return "launch version not recoverable"


def build():
    names = sorted(
        n for n in os.listdir(PROV) if n.startswith("SOURCE_ARCHIVE") and n.endswith(".tar.gz")
    )
    archives = {n: archive_index(os.path.join(PROV, n)) for n in names}
    packages = {}
    for package in sorted(os.listdir(EXP)):
        ipath = os.path.join(EXP, package, "inputs.json")
        if not os.path.isfile(ipath):
            continue
        try:
            with open(ipath, encoding="utf-8") as h:
                recorded = recorded_sources(json.load(h))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not recorded:
            continue
        files = {p: classify(p, d, archives) for p, d in sorted(recorded.items())}
        archived = sum(v.startswith("in ") for v in files.values())
        packages[package] = {
            "recorded_sources": len(files),
            "recoverable_from_archives": archived,
            "status": "fully recoverable" if archived == len(files) else "partially recoverable",
            "files": files,
        }
    counts = {}
    for p in packages.values():
        counts[p["status"]] = counts.get(p["status"], 0) + 1
    with_inputs = sum(os.path.isfile(os.path.join(EXP, p, "inputs.json")) for p in os.listdir(EXP))
    return {
        "archives": {
            f"provenance/{n}": sha(open(os.path.join(PROV, n), "rb").read()) for n in names
        },
        "note": (
            "A recorded file is recoverable when an archive holds it with the hash recorded at "
            "launch. Packages without recorded source hashes are not listed."
        ),
        "packages_on_disk": len(os.listdir(EXP)),
        "packages_with_inputs": with_inputs,
        "packages_with_recorded_sources": len(packages),
        "summary": counts,
        "packages": packages,
    }


def main() -> int:
    out = build()
    with open(os.path.join(PROV, "PACKAGE_SOURCE_STATUS.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "packages"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
