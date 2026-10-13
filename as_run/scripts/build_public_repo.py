"""Assemble the frozen snapshot (`as_run/`) of the public repository from this project (A-176).

The public repository has two layers. `as_run/` is a copy of the code, the registration records
and the sealed evidence packages exactly as they are here, in the same layout, so that every
script runs from it unchanged. The clean library and the web site are written by hand next to it
and are not touched by this script.

    uv run python scripts/build_public_repo.py <path to the public repository> [--check]

What is not copied, and why:

- heavy files of the evidence packages (run logs, pickled states, animations): they go to the
  data archive, and `SNAPSHOT.json` lists each one with its size and its sealed checksum;
- third-party code, published articles, publisher templates, manuscript sources and reviews;
- internal planning notes.

One file is written instead of copied: `MAPS_STATUS.json`, whose network paths are made relative
to the snapshot (the originals point to a folder of this machine). The networks themselves are
copied to `assets/osm/` and their checksums are compared with the recorded ones.

`--check` copies nothing and reports what would change.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DIRECTORIES = (
    "src",
    "scripts",
    "tests",
    "configs",
    "contracts",
    "protocols",
    "audit_kit",
    "governance",
    "provenance",
    "experiments",
    "assets",
)
FILES = ("pyproject.toml", "uv.lock", "README.md", "THIRD_PARTY_NOTICES.md", "MAPS_STATUS.md")
SKIPPED_NAMES = {"__pycache__", ".DS_Store", ".pytest_cache", ".ruff_cache", ".venv"}
# Tooling of the manuscript, which is not part of the repository until the article is accepted.
SKIPPED_SCRIPTS = {
    "build_draft_v2_elsevier_twocolumn.py",
    "build_reference_sheet.py",
    "convert_manuscript_to_elsevier.py",
    "convert_manuscript_to_iop.py",
    "generate_fresh_manuscript_simpat.py",
}
ARCHIVE_ONLY_SUFFIXES = (".log", ".pkl", ".gif")
ARCHIVE_ONLY_BYTES = 40 * 1024 * 1024
SENSITIVE = {
    "e-mail address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "IPv4 address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "credential word": re.compile(r"(?i)\b(?:password|passwd|api[_-]?key|secret|token)\b\s*[:=]"),
}


def sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as h:
        for block in iter(lambda: h.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass
class Report:
    copied: int = 0
    copied_bytes: int = 0
    archive_only: list = field(default_factory=list)
    skipped_scripts: list = field(default_factory=list)
    sensitive: list = field(default_factory=list)


def sealed_checksums(package_dir: str) -> dict:
    path = os.path.join(package_dir, "checksums.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as h:
        data = json.load(h)
    files = data.get("files", data)
    return files if isinstance(files, dict) else {}


def is_archive_only(relative: str, size: int) -> bool:
    if not relative.startswith("experiments" + os.sep):
        return False
    return relative.endswith(ARCHIVE_ONLY_SUFFIXES) or size > ARCHIVE_ONLY_BYTES


def scan(path: str, relative: str, report: Report) -> None:
    """Record text that looks like personal or secret data, for a human to read first."""
    if not relative.endswith((".py", ".md", ".json", ".toml", ".yml", ".txt", ".jsonl")):
        return
    if os.path.getsize(path) > 3 * 1024 * 1024:
        return
    with open(path, encoding="utf-8", errors="replace") as h:
        text = h.read()
    for kind, pattern in SENSITIVE.items():
        found = sorted(set(pattern.findall(text)))
        if kind == "IPv4 address":
            found = [f for f in found if not f.startswith(("0.", "1.", "2.", "3."))]
        if found:
            report.sensitive.append({"file": relative, "kind": kind, "examples": found[:5]})


def copy_tree(name: str, target_root: str, report: Report, check: bool) -> None:
    source_root = os.path.join(ROOT, name)
    for directory, subdirs, files in os.walk(source_root):
        subdirs[:] = sorted(d for d in subdirs if d not in SKIPPED_NAMES)
        for file_name in sorted(files):
            if file_name in SKIPPED_NAMES:
                continue
            source = os.path.join(directory, file_name)
            relative = os.path.relpath(source, ROOT)
            if name == "scripts" and file_name in SKIPPED_SCRIPTS:
                report.skipped_scripts.append(relative)
                continue
            size = os.path.getsize(source)
            if is_archive_only(relative, size):
                package = os.path.join(ROOT, *relative.split(os.sep)[:2])
                inside = os.sep.join(relative.split(os.sep)[2:])
                sealed = sealed_checksums(package).get(inside)
                report.archive_only.append({"path": relative, "bytes": size, "sha256": sealed})
                continue
            scan(source, relative, report)
            report.copied += 1
            report.copied_bytes += size
            if not check:
                target = os.path.join(target_root, relative)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(source, target)


def copy_networks(target_root: str, check: bool) -> dict:
    """Copy the city networks named in MAPS_STATUS.json, after checking their checksums."""
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as h:
        status = json.load(h)
    folder = os.path.join(target_root, "assets", "osm")
    if not check:
        os.makedirs(folder, exist_ok=True)
    for entry in status["maps"]:
        source = entry["path"]
        if sha256(source) != entry["sha256"]:
            raise SystemExit(f"checksum of {source} differs from MAPS_STATUS.json")
        entry["path"] = f"assets/osm/{os.path.basename(source)}"
        if not check:
            shutil.copy2(source, os.path.join(folder, os.path.basename(source)))
    status["source_manifest"] = "assets/osm (copied from the original asset folder)"
    status["snapshot_note"] = (
        "Paths were made relative to the snapshot when it was assembled; every other field is "
        "as generated. Run the scripts from the snapshot root."
    )
    if not check:
        with open(os.path.join(target_root, "MAPS_STATUS.json"), "w", encoding="utf-8") as h:
            json.dump(status, h, indent=2)
            h.write("\n")
    return {"networks": len(status["maps"])}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repository")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target_root = os.path.join(os.path.abspath(args.repository), "as_run")
    if not os.path.isdir(os.path.join(args.repository, ".git")):
        raise SystemExit(f"{args.repository} is not a git repository")
    report = Report()
    if not args.check and os.path.isdir(target_root):
        shutil.rmtree(target_root)
    for name in DIRECTORIES:
        copy_tree(name, target_root, report, args.check)
    for name in FILES:
        report.copied += 1
        report.copied_bytes += os.path.getsize(os.path.join(ROOT, name))
        if not args.check:
            os.makedirs(target_root, exist_ok=True)
            shutil.copy2(os.path.join(ROOT, name), os.path.join(target_root, name))
    networks = copy_networks(target_root, args.check)
    snapshot = {
        "schema_version": 1,
        "assembled_by": "scripts/build_public_repo.py",
        "files_copied": report.copied,
        "bytes_copied": report.copied_bytes,
        **networks,
        "written_not_copied": ["MAPS_STATUS.json (network paths made relative)"],
        "not_copied_scripts": sorted(report.skipped_scripts),
        "archive_only": sorted(report.archive_only, key=lambda e: e["path"]),
        "archive_only_bytes": sum(e["bytes"] for e in report.archive_only),
        "not_published": [
            "third_party/ (code of other authors; see THIRD_PARTY.md for addresses and commits)",
            "docs/manuscript/ and reviews/ (until the article is accepted)",
            "docs/*.md and research/ (internal planning notes)",
            "published articles and publisher templates",
        ],
    }
    if not args.check:
        with open(os.path.join(target_root, "SNAPSHOT.json"), "w", encoding="utf-8") as h:
            json.dump(snapshot, h, indent=1)
            h.write("\n")
    megabytes = report.copied_bytes / 1e6
    print(f"{report.copied} files, {megabytes:.1f} MB copied; {networks['networks']} networks")
    held_back = snapshot["archive_only_bytes"] / 1e6
    print(f"{len(report.archive_only)} heavy files left to the archive ({held_back:.1f} MB)")
    kinds = {}
    for item in report.sensitive:
        kinds.setdefault(item["kind"], []).append(item)
    for kind, items in kinds.items():
        print(f"to read before publishing, {kind}: {len(items)} files")
        for item in items[:12]:
            print(f"   {item['file']}: {item['examples']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
