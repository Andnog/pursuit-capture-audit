#!/usr/bin/env python3
"""Run the W3 adapter checks and write the evidence rows for one package.

Nine checks, frozen in the protocol before any W3 implementation existed. **No SUMO
process is started**: native execution is gated behind W4 and W5.

Usage:
    uv run python scripts/run_adapter_checks.py --package experiments/<experiment_id>
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import resource
import subprocess
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

# Each planned check maps to the test classes that decide it. The mapping is explicit so a
# check cannot silently lose its evidence by a test being renamed away.
CHECKS = {
    "R1_state_restoration_exact": [
        "test_snapshot_replay.TestStateRestoration",
        "test_snapshot_replay.TestDeterminism",
    ],
    "R2_shared_seed_insufficient_after_divergence": [
        "test_snapshot_replay.TestSharedSeedIsNotSharedNoise",
        "test_snapshot_replay.TestCoupledReplayFromAVerifiedPrefix",
    ],
    "R3_information_boundary_every_decision": [
        "test_adapter_contract.TestInformationBoundary",
    ],
    "R4_masks_and_fallback": ["test_adapter_contract.TestMasksAndFallback"],
    "R5_deadline_enforced": ["test_adapter_contract.TestDeadline"],
    "R6_proposed_vs_executed_logged_separately": [
        "test_adapter_contract.TestProposedVersusExecuted",
    ],
    "R7_generator_pruning_accounted": [
        "test_generator.TestGenerationAccounting",
        "test_generator.TestPairwiseIsLabelledAsAnApproximation",
    ],
    "R8_episode_result_rows_validate": ["test_generator.TestEvidenceRows"],
    "R9_no_legacy_import_lint_clean_earlier_tests_pass": [
        "test_adapter_contract.TestNoSumoProcessIsStarted",
        "test_information_boundary.TestSelectorInputs",
        "test_source_hygiene.TestImplicitStringConcatenation",
        "test_source_hygiene.TestNoLegacyRuntimePathIsExecutable",
    ],
}


def run_named(names: list[str]) -> tuple[bool, int, list[str]]:
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)
    with open(os.devnull, "w") as stream:
        outcome = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    problems = [str(f[0]) for f in outcome.failures + outcome.errors]
    return outcome.wasSuccessful(), outcome.testsRun, problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--reseal", action="store_true")
    args = parser.parse_args()
    package = args.package if os.path.isabs(args.package) else os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    if os.path.isfile(os.path.join(package, "checksums.json")) and not args.reseal:
        print(f"REFUSED: {os.path.basename(package)} is sealed.", file=sys.stderr)
        return 2

    started_wall = time.time()
    started_cpu = resource.getrusage(resource.RUSAGE_SELF)
    stamp = datetime.datetime.now(datetime.UTC).isoformat()
    events: list = [{"ts": stamp, "event": "run_started", "package": os.path.basename(package)}]
    results: list = []

    all_ok = True
    for check_id, names in CHECKS.items():
        ok, ran, problems = run_named(names)
        all_ok = all_ok and ok
        results.append(
            {
                "group": "adapter_checks",
                "case_id": check_id,
                "status": "PASS" if ok else "FAIL",
                "test_classes": names,
                "tests_run": ran,
                "problems": problems,
            }
        )
        events.append({"ts": stamp, "event": "check_executed", "check": check_id, "ok": ok})

    full = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "tests"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    bare = subprocess.run(
        ["/opt/homebrew/bin/python3", "-m", "unittest", "discover", "-s", "tests", "-t", "tests"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    lint = subprocess.run(
        [
            "uv",
            "run",
            "--quiet",
            "ruff",
            "check",
            "--output-format",
            "concise",
            "src",
            "tests",
            "scripts",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    results.append(
        {
            "group": "regression",
            "case_id": "full_suite_and_bare_interpreter",
            "status": "PASS"
            if full.returncode == 0 and bare.returncode == 0 and lint.returncode == 0
            else "FAIL",
            "full_suite_returncode": full.returncode,
            "bare_interpreter_returncode": bare.returncode,
            "lint_returncode": lint.returncode,
        }
    )
    regression_ok = results[-1]["status"] == "PASS"

    ended_cpu = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu_seconds = (
        (ended_cpu.ru_utime - started_cpu.ru_utime)
        + (ended_cpu.ru_stime - started_cpu.ru_stime)
        + children.ru_utime
        + children.ru_stime
    )

    for name, rows in (("events.jsonl", events), ("results.jsonl", results)):
        with open(os.path.join(package, name), "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, default=str) + "\n")

    checks = [r for r in results if r["group"] == "adapter_checks"]
    summary = {
        "package": os.path.basename(package),
        "stage": "W3",
        "checks": {
            "planned": len(CHECKS),
            "executed": len(checks),
            "passed": sum(1 for r in checks if r["status"] == "PASS"),
            "tests_run": sum(r["tests_run"] for r in checks),
        },
        "regression": {
            "full_suite_ok": full.returncode == 0,
            "bare_interpreter_ok": bare.returncode == 0,
            "lint_clean": lint.returncode == 0,
        },
        "gate": {
            "name": "W3_adapter_and_state_restoration",
            "rule": "SUPPORTED only if all nine planned checks pass",
            "verdict": "SUPPORTED" if all_ok and regression_ok else "NOT_SUPPORTED",
            "claim_class": "engineering_acceptance_only",
            "explicitly_not_validated": [
                "the TraCI call surface: no SUMO process was started in W3",
                "arrival sets computed from a real road network",
                "anything physical, learned or comparative",
            ],
        },
        "resources": {
            "cpu_seconds": round(cpu_seconds, 3),
            "wall_seconds": round(time.time() - started_wall, 3),
            "sumo_process_starts": 0,
            "sumo_episodes": 0,
            "optimizer_updates": 0,
            "checkpoint_loads": 0,
            "test_split_accesses": 0,
        },
    }
    with open(os.path.join(package, "result.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")

    environment = {
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "backend_used_for_validation": "DeterministicBackend (in-memory kinematic fixture)",
        "traci_backend_executed": False,
        "sumo_process_starts": 0,
        "sumo_episodes_executed": 0,
        "optimizer_run": False,
        "checkpoint_loaded": False,
        "test_split_accessed": False,
        "legacy_module_imported": False,
    }
    with open(os.path.join(package, "environment.json"), "w", encoding="utf-8") as handle:
        json.dump(environment, handle, indent=2)
        handle.write("\n")

    print(json.dumps(summary, indent=2))
    return 0 if summary["gate"]["verdict"] == "SUPPORTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
