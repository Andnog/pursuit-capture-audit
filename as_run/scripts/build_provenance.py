#!/usr/bin/env python3
"""Rebuild governance/SOURCE_PROVENANCE.json from the files actually on disk.

Every hash is computed at build time. Nothing is copied from a document. A file that is
absent is recorded as UNRESOLVED, never invented.

This lives in the repository rather than in a scratch directory because the provenance
record must be reproducible by a third party without this conversation.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.dirname(ROOT)
BUILD_DATE = datetime.date.today().isoformat()

SEALED_README_SHA = "c9e3ba1c16571e2ed03f0ffc2793077827c7b220673dba91580a1ce579c204d2"


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def file_entry(source_id: str, path: str, role: str, use_policy: str, notes: str) -> dict:
    entry = {
        "source_id": source_id,
        "path": path,
        "role": role,
        "use_policy": use_policy,
        "notes": notes,
    }
    if os.path.isfile(path):
        stat = os.stat(path)
        entry.update(
            {
                "exists": True,
                "real_path": os.path.realpath(path),
                "size_bytes": stat.st_size,
                "sha256": sha256_of(path),
                "mtime_utc": datetime.datetime.fromtimestamp(stat.st_mtime, datetime.UTC).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            }
        )
    else:
        entry.update(
            {
                "exists": False,
                "real_path": None,
                "size_bytes": None,
                "sha256": "UNRESOLVED_FILE_ABSENT",
                "mtime_utc": None,
            }
        )
    return entry


def git_facts(path: str) -> dict:
    def run(args: list[str]) -> str | None:
        try:
            out = subprocess.run(
                ["git", "-C", path, *args], capture_output=True, text=True, timeout=60
            )
            return out.stdout.strip() if out.returncode == 0 else None
        except Exception:  # noqa: BLE001
            return None

    head = run(["rev-parse", "HEAD"])
    if head is None:
        return {"is_git_repository": False}
    entries = [ln for ln in (run(["status", "--porcelain"]) or "").splitlines() if ln.strip()]
    return {
        "is_git_repository": True,
        "head_commit": head,
        "head_subject": run(["log", "-1", "--format=%s"]),
        "head_committed_at": run(["log", "-1", "--format=%cI"]),
        "working_tree_entry_count": len(entries),
        "working_tree_clean": not entries,
    }


AUTHORITATIVE = [
    (
        "AUTH01",
        "README.md",
        "new_project_entry_point",
        "Updated after the seal; see AMENDMENTS_EN.md A-05.",
    ),
    (
        "AUTH02",
        "docs/DOCTORAL_MASTER_PLAN_EN_v3.md",
        "governing_specification",
        "Sealed, unchanged.",
    ),
    ("AUTH03", "docs/FINAL_REVIEW_EN.md", "documentary_review", "Sealed, unchanged."),
    (
        "AUTH04",
        "governance/DECISIONS_EN.md",
        "frozen_decision_register",
        "Sealed, unchanged; resolutions go in AMENDMENTS_EN.md.",
    ),
    (
        "AUTH05",
        "governance/REVIEW_MANIFEST.json",
        "documentary_integrity_manifest",
        "Historical seal of the 2026-09-20 review; not updated as work proceeds.",
    ),
]

HISTORICAL = [
    (
        "HIST01",
        f"{WORKSPACE}/urban_capture_cooperation_v3/PLAN_MAESTRO_DOCTORAL_IMPLEMENTACION_ES_v2.md",
        "original_spanish_master_plan_v2",
    ),
    (
        "HIST02",
        f"{WORKSPACE}/urban_capture_cooperation_v3/PREGUNTA_DOCTORAL_Y_CONTRIBUCION_ES.md",
        "original_fixed_research_question",
    ),
    (
        "HIST03",
        f"{WORKSPACE}/urban_capture_cooperation_v3/START_HERE_EN.md",
        "updated_english_pointer",
    ),
    (
        "HIST04",
        f"{WORKSPACE}/urban_capture_cooperation_v3/START_HERE_ES.md",
        "superseded_spanish_entry_point",
    ),
    (
        "HIST05",
        f"{WORKSPACE}/urban_capture_cooperation_v3/research/20260919_novelty_audit_01/METHOD_SPEC_EN.md",
        "historical_assistance_method_specification",
    ),
    (
        "HIST06",
        f"{WORKSPACE}/urban_capture_cooperation_v3/research/20260919_novelty_audit_01/LITERATURE_MATRIX_EN.md",
        "historical_literature_matrix_S01_S28",
    ),
    (
        "HIST07",
        f"{WORKSPACE}/urban_capture_cooperation_v3/research/20260919_novelty_audit_01/SEARCH_PROTOCOL_EN.md",
        "historical_search_protocol",
    ),
    (
        "HIST08",
        f"{WORKSPACE}/urban_capture_cooperation_v3/research/20260919_systematic_review_results_03/PRIMARY_FINDINGS_EN.md",
        "primary_source_findings",
    ),
    (
        "HIST09",
        f"{WORKSPACE}/urban_capture_cooperation_v3/research/20260919_research_pivot_05/PRIMARY_SOURCE_DELTA_EN.md",
        "primary_source_delta",
    ),
    (
        "HIST10",
        (
            "/Users/andrei/Documents/PHD/Union/urban_dynamic_containment/docs/HANDOFF_TRAINING_2026091 "
            "0.md"
        ),
        "historical_runtime_handoff",
    ),
]

AUTHORED = [
    ("docs/RESEARCH_QUESTION_EN.md", "b0_research_question", "B0"),
    ("docs/HANDOFF_EN.md", "handoff", "B0-W2"),
    ("docs/METHOD_SPEC_EN.md", "w1_method_spec", "W1"),
    ("docs/BASELINE_SPEC_EN.md", "w0_baseline_spec", "W0"),
    ("governance/PROJECT_STATE.json", "project_state", "B0; updated through W2"),
    ("governance/LEGACY_OBLIGATIONS_EN.md", "obligations", "B0"),
    ("governance/RESOURCE_LEDGER.jsonl", "resource_ledger", "B0; appended through W2"),
    ("governance/AMENDMENTS_EN.md", "amendments", "B0-W2"),
    ("research/novelty/SEARCH_PROTOCOL_EN.md", "w0_search_protocol", "W0"),
    ("research/novelty/search_log.jsonl", "w0_search_log", "W0"),
    ("research/novelty/sources.bib", "w0_bibliography", "W0"),
    ("research/novelty/claim_evidence_matrix.csv", "w0_claim_matrix", "W0"),
    ("research/novelty/TECHNICAL_GAP_EN.md", "w0_technical_gap", "W0"),
    ("configs/finite_examples_v1.json", "w1_case_inputs", "W1, frozen before implementation"),
    (
        "tests/fixtures/finite_cases_v1.json",
        "w1_frozen_expectations",
        "W1, derived by hand before implementation",
    ),
    ("contracts/TASK_CONTRACT_EN.md", "w2_task_contract", "W2"),
    ("contracts/task_contract.json", "w2_task_contract_machine", "W2"),
    ("contracts/REWARD_CONTRACT_EN.md", "w2_reward_contract", "W2"),
    ("contracts/ASSISTANCE_PROTOCOL_EN.md", "w2_assistance_protocol", "W2"),
    ("contracts/SPLIT_PROTOCOL_EN.md", "w2_split_protocol", "W2"),
    ("contracts/maps_manifest.json", "w2_maps_manifest", "W2, declared empty"),
    ("contracts/split_manifest.json", "w2_split_manifest", "W2, declared empty, TEST closed"),
    ("configs/domain_v1.json", "w2_domain_config_D06_D07", "W2, PROPOSED not frozen"),
    ("THIRD_PARTY_NOTICES.md", "w2_dependency_notices_D16", "W2"),
    ("pyproject.toml", "w2_dependency_pins", "W2"),
    ("uv.lock", "w2_dependency_lock", "W2"),
]

RUNTIME_ROOTS = [
    (
        "RUNTIME_HOME",
        "/Users/andrei/Documents/PHD/Union/urban_dynamic_containment",
        "CANONICAL_FOR_OBLIGATION_TEXT",
        "Later HEAD commit date, and the only root containing docs/HANDOFF_TRAINING_20260910.md.",
    ),
    (
        "RUNTIME_SSD",
        f"{WORKSPACE}/urban_dynamic_containment",
        "DIVERGENT_OLDER_COPY",
        (
            "Different HEAD, smaller working-tree difference set, no handoff document. Not a copy or "
            "symlink."
        ),
    ),
]


def main() -> int:
    manifest_path = os.path.join(ROOT, "governance", "REVIEW_MANIFEST.json")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)

    file_matches, mismatches = 0, []
    for rel, expected in manifest["files"].items():
        target = os.path.join(WORKSPACE, rel)
        if os.path.isfile(target) and sha256_of(target) == expected:
            file_matches += 1
        else:
            mismatches.append(rel)

    seal_matches = sum(
        1
        for check in manifest["original_documentary_seal_checks"]
        if os.path.isfile(os.path.join(WORKSPACE, check["file"]))
        and sha256_of(os.path.join(WORKSPACE, check["file"])) == check["expected_sha256"]
    )

    runtime_roots = []
    for source_id, path, designation, basis in RUNTIME_ROOTS:
        record = {
            "source_id": source_id,
            "path": path,
            "exists": os.path.isdir(path),
            "real_path": os.path.realpath(path),
            "designation": designation,
            "use_policy": "READ_ONLY_EVIDENCE_NO_IMPORT_NO_EXECUTION",
            "git": git_facts(path),
            "basis_for_designation": basis,
        }
        readme = os.path.join(path, "README.md")
        record["readme_sha256"] = (
            sha256_of(readme) if os.path.isfile(readme) else "UNRESOLVED_FILE_ABSENT"
        )
        for sub in ("docs", "tests", "runs", "src"):
            sub_path = os.path.join(path, sub)
            record[f"{sub}_entry_count"] = (
                len(os.listdir(sub_path)) if os.path.isdir(sub_path) else None
            )
        runtime_roots.append(record)

    evidence_root = os.path.join(WORKSPACE, "urban_dynamic_containment_evidence", "v2_20260907")
    packages = []
    for name in ("recovery_20260919_26", "recovery_20260919_27", "recovery_20260919_28"):
        package = os.path.join(evidence_root, name)
        record = {
            "package_id": name,
            "path": package,
            "exists": os.path.isdir(package),
            "use_policy": "READ_ONLY_EVIDENCE_NO_IMPORT_NO_REUSE_OF_SUCCESS_LABELS",
        }
        if record["exists"]:
            record["entry_count"] = len(os.listdir(package))
            for doc in ("checksums.json", "SCIENTIFIC_DECISION.md", "NEXT_WORK.md", "REPORT.md"):
                target = os.path.join(package, doc)
                record[f"{doc}_sha256"] = (
                    sha256_of(target) if os.path.isfile(target) else "UNRESOLVED_FILE_ABSENT"
                )
        packages.append(record)

    document = {
        "schema_version": 2,
        "document_id": "SOURCE_PROVENANCE",
        "stage": "B0-W2",
        "build_date": BUILD_DATE,
        "built_by": "scripts/build_provenance.py",
        "project_root": ROOT,
        "workspace_root": WORKSPACE,
        "hash_algorithm": "sha256",
        "purpose": (
            "Record the actual on-disk identity of every authoritative, historical and authored "
            "input, so later work can detect silent substitution. Hashes are integrity aids; they "
            "are not scientific validation."
        ),
        "fresh_start_policy": {
            "statement": (
                "No mutable legacy research module, learned weight, optimizer state, replay buffer "
                "or demonstration is imported, symlinked or executed by this project."
            ),
            "verified_through": "W2",
            "verification_method": (
                "tests/test_information_boundary.py parses every module in the package and asserts "
                "that no import resolves to a legacy runtime and that every third-party import is "
                "a "
                "pinned declared dependency."
            ),
        },
        "authoritative_documents": [
            file_entry(sid, os.path.join(ROOT, rel), role, "GOVERNING_DOCUMENT", note)
            for sid, rel, role, note in AUTHORITATIVE
        ],
        "historical_documents": [
            file_entry(sid, path, role, "EVIDENCE_AND_PROVENANCE_READ_ONLY", "")
            for sid, path, role in HISTORICAL
        ],
        "project_authored_artifacts": [
            file_entry(f"NEW{i:02d}", os.path.join(ROOT, rel), role, "AUTHORED_HERE", stage)
            for i, (rel, role, stage) in enumerate(AUTHORED, start=1)
        ],
        "legacy_runtime_roots": runtime_roots,
        "legacy_runtime_root_equivalence": {
            "established": False,
            "verdict": "DISTINCT_DIVERGENT_ROOTS",
            "consequence": (
                "Obligation text is read from RUNTIME_HOME only. No statement in this project may "
                "cite 'the runtime' without naming which root it came from."
            ),
        },
        "historical_evidence_packages": packages,
        "external_system_dependencies": [
            {
                "name": "Eclipse SUMO",
                "version": "1.21.0",
                "channel": (
                    "external system installation; eclipse-sumo publishes no macOS arm64 wheel"
                ),
                "installed_python_package_wheel_tag": "cp310-cp310-macosx_14_0_arm64",
                "usable_from_project_interpreter": False,
                "why_it_matters": (
                    "Binary and Python bindings come from different channels and can drift apart "
                    "silently; a binding speaking a different TraCI version returns wrong state "
                    "rather than raising. scripts/preflight.py blocks on any mismatch."
                ),
                "episodes_executed": 0,
                "invoked_for": "--version only",
                "license": "EPL-2.0",
            }
        ],
        "documentary_seal_reverification": {
            "performed_on": BUILD_DATE,
            "source_manifest": "governance/REVIEW_MANIFEST.json",
            "files_checked": len(manifest["files"]),
            "files_matching": file_matches,
            "original_seal_checks_rechecked": len(manifest["original_documentary_seal_checks"]),
            "original_seal_checks_matching": seal_matches,
            "mismatches": mismatches,
            "all_match": not mismatches,
            "note": (
                "README.md was updated after the seal under amendment A-05, so exactly one "
                "mismatch "
                "is expected. Any other mismatch is unexplained and must be investigated."
            ),
            "limit": (
                "Documentary bytes only. Certifies no runtime behaviour and no scientific claim."
            ),
        },
        "post_seal_changes": [
            {
                "file": "doctoral_joint_interception/README.md",
                "sealed_sha256": SEALED_README_SHA,
                "current_sha256": sha256_of(os.path.join(ROOT, "README.md")),
                "reason": (
                    "The delivered README stated 'Implementation status: NOT STARTED', which "
                    "became false."
                ),
                "authorization": "governance/AMENDMENTS_EN.md A-05",
                "review_manifest_updated": False,
            },
            {
                "file": "experiments/20260920_w01_finite_examples_r01/{events.jsonl,result.json}",
                "reason": (
                    "A W2 reproducibility check re-ran the finite examples against the sealed W1 "
                    "package."
                ),
                "authorization": "that package's SEAL_EVENT_EN.md; W2 DEVIATIONS_EN.md D-11",
                "scientific_impact": "none; results.jsonl is byte-identical to the original seal",
                "original_hashes_preserved_in": (
                    "that package's checksums.json under superseded_seal"
                ),
                "corrective_action": (
                    "both runners refuse to write into a sealed package without --reseal"
                ),
            },
        ],
        "repository_instructions": {
            "agents_md_files_found": 0,
            "claude_md_files_found": 0,
            "conclusion": (
                "No AGENTS.md or equivalent exists in either tree. The master plan and the "
                "decision "
                "register are the only binding repository instructions."
            ),
        },
        "version_control_state": {
            "project_root_under_git": os.path.isdir(os.path.join(ROOT, ".git")),
            "note": (
                "The project root is not inside a git repository. Evidence integrity relies on "
                "package checksums.json files, not on commit identity."
            ),
        },
        "limits": [
            "A matching hash proves byte identity, not scientific correctness.",
            "Historical evidence may inform diagnostics only; its success labels were produced "
            "under "
            "an incompatible capture contract and are not reused.",
            (
                "Absence of an AGENTS.md file was established by search; a later addition is not "
                "reflected."
            ),
        ],
    }

    out_path = os.path.join(ROOT, "governance", "SOURCE_PROVENANCE.json")
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print(
        json.dumps(
            {
                "written": os.path.relpath(out_path, ROOT),
                "authoritative": len(document["authoritative_documents"]),
                "historical": len(document["historical_documents"]),
                "authored": len(document["project_authored_artifacts"]),
                "seal_files_matching": f"{file_matches}/{len(manifest['files'])}",
                "seal_originals_matching": f"{seal_matches}/{len(manifest['original_documentary_seal_checks'])}",
                "unexplained_mismatches": [m for m in mismatches if not m.endswith("README.md")],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
