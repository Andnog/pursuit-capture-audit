#!/usr/bin/env python3
"""Verify artifact integrity and local document links for this project.

Checks performed:
  1. every required B0/W0/W1 artifact exists;
  2. every experiment package contains the file set required by master plan section 4;
  3. every local markdown link resolves to an existing file;
  4. every JSON and JSONL artifact parses;
  5. sealed package checksums still match, when a checksums.json is present.

Integrity checks are not scientific validation. A matching hash proves byte identity only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_ARTIFACTS = [
    "README.md",
    "docs/DOCTORAL_MASTER_PLAN_EN_v3.md",
    "docs/FINAL_REVIEW_EN.md",
    "docs/RESEARCH_QUESTION_EN.md",
    "docs/METHOD_SPEC_EN.md",
    "docs/BASELINE_SPEC_EN.md",
    "governance/DECISIONS_EN.md",
    "governance/REVIEW_MANIFEST.json",
    "governance/PROJECT_STATE.json",
    "governance/SOURCE_PROVENANCE.json",
    "governance/LEGACY_OBLIGATIONS_EN.md",
    "governance/RESOURCE_LEDGER.jsonl",
    "research/novelty/SEARCH_PROTOCOL_EN.md",
    "research/novelty/search_log.jsonl",
    "research/novelty/sources.bib",
    "research/novelty/claim_evidence_matrix.csv",
    "research/novelty/TECHNICAL_GAP_EN.md",
    "configs/finite_examples_v1.json",
    "tests/fixtures/finite_cases_v1.json",
    "scripts/run_finite_examples.py",
    "scripts/run_contract_checks.py",
    "scripts/preflight.py",
    "scripts/build_provenance.py",
    "pyproject.toml",
    "uv.lock",
    "THIRD_PARTY_NOTICES.md",
    "contracts/TASK_CONTRACT_EN.md",
    "contracts/task_contract.json",
    "contracts/public_observation.schema.json",
    "contracts/action.schema.json",
    "contracts/opportunity.schema.json",
    "contracts/episode_result.schema.json",
    "contracts/REWARD_CONTRACT_EN.md",
    "contracts/ASSISTANCE_PROTOCOL_EN.md",
    "contracts/SPLIT_PROTOCOL_EN.md",
    "contracts/maps_manifest.json",
    "contracts/split_manifest.json",
    "configs/domain_v1.json",
    "docs/HANDOFF_EN.md",
    "governance/AMENDMENTS_EN.md",
]

REQUIRED_PACKAGE_FILES = [
    "PROTOCOL_EN.md",
    "plan.json",
    "inputs.json",
    "domain.json",
    "environment.json",
    "events.jsonl",
    "results.jsonl",
    "result.json",
    "DEVIATIONS_EN.md",
    "SCIENTIFIC_DECISION_EN.md",
]

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    problems: list[str] = []
    checked = {"artifacts": 0, "links": 0, "json": 0, "packages": 0, "sealed_hashes": 0}

    for rel in REQUIRED_ARTIFACTS:
        checked["artifacts"] += 1
        if not os.path.isfile(os.path.join(ROOT, rel)):
            problems.append(f"MISSING REQUIRED ARTIFACT: {rel}")

    experiments = os.path.join(ROOT, "experiments")
    if os.path.isdir(experiments):
        for name in sorted(os.listdir(experiments)):
            package = os.path.join(experiments, name)
            if not os.path.isdir(package):
                continue
            checked["packages"] += 1
            for required in REQUIRED_PACKAGE_FILES:
                if not os.path.isfile(os.path.join(package, required)):
                    problems.append(f"PACKAGE {name}: missing {required}")
            sealed = os.path.join(package, "checksums.json")
            if os.path.isfile(sealed):
                with open(sealed, encoding="utf-8") as handle:
                    manifest = json.load(handle)
                for rel, expected in manifest.get("files", {}).items():
                    checked["sealed_hashes"] += 1
                    target = os.path.join(package, rel)
                    if not os.path.isfile(target):
                        problems.append(f"PACKAGE {name}: sealed file absent: {rel}")
                    elif sha256_of(target) != expected:
                        problems.append(f"PACKAGE {name}: sealed hash mismatch: {rel}")

    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".git"}]
        for name in files:
            path = os.path.join(base, name)
            if name.endswith(".json"):
                checked["json"] += 1
                try:
                    with open(path, encoding="utf-8") as handle:
                        json.load(handle)
                except Exception as exc:  # noqa: BLE001
                    problems.append(f"INVALID JSON: {os.path.relpath(path, ROOT)}: {exc}")
            elif name.endswith(".jsonl"):
                checked["json"] += 1
                with open(path, encoding="utf-8") as handle:
                    for number, line in enumerate(handle, 1):
                        if not line.strip():
                            continue
                        try:
                            json.loads(line)
                        except Exception as exc:  # noqa: BLE001
                            problems.append(
                                f"INVALID JSONL: {os.path.relpath(path, ROOT)}:{number}: {exc}"
                            )
            elif name.endswith(".md"):
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
                for target in LINK.findall(text):
                    if target.startswith(("http://", "https://", "#", "mailto:")):
                        continue
                    checked["links"] += 1
                    # Accept the angle-bracket form <path> and a trailing :<line> anchor,
                    # both of which appear in the delivered documentary baseline and are
                    # editor conventions rather than dangling references.
                    clean = target.strip("<>").split("#", 1)[0]
                    clean = re.sub(r":\d+$", "", clean)
                    if not clean:
                        continue
                    resolved = os.path.normpath(
                        clean if os.path.isabs(clean) else os.path.join(base, clean)
                    )
                    if not os.path.exists(resolved):
                        problems.append(f"BROKEN LINK: {os.path.relpath(path, ROOT)} -> {target}")

    print(json.dumps({"checked": checked, "problems": problems}, indent=2))
    if problems:
        print(f"\nFAILED: {len(problems)} problem(s)", file=sys.stderr)
        return 1
    print("\nOK: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
