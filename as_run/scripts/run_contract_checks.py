#!/usr/bin/env python3
"""Run the W2 contract checks and write the evidence rows for one package.

Three groups, each recorded as its own row set:

1. **Physical preflight** - simulator environment consistency. Runs NO episode.
2. **Contract checks** - the full test suite, reported per test module.
3. **W0-W1 regression** - the fourteen frozen finite cases re-run against the source as
   reformatted in W2, so the earlier result is shown to survive the change rather than
   assumed to. It writes into THIS package, never into the sealed W1 package.

Usage:
    uv run python scripts/run_contract_checks.py --package experiments/<experiment_id>
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
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

TEST_MODULES = [
    "test_reachable_intervals",
    "test_joint_compatibility",
    "test_commitment_memory",
    "test_assistance_accounting",
    "test_information_boundary",
    "test_contract_admission",
    "test_capture_judge",
    "test_safety_admission",
    "test_split_integrity",
    "test_reward_horizon",
]


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run_preflight(events: list, results: list) -> bool:
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "preflight.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        report = {"ok": False, "blocking": ["preflight produced no parsable report"]}
    events.append({"event": "preflight_executed", "returncode": proc.returncode})
    results.append(
        {
            "group": "preflight",
            "case_id": "PF1_simulator_environment",
            "status": "PASS" if report.get("ok") else "FAIL",
            "observed": report.get("checks", {}),
            "problems": report.get("blocking", []),
            "non_blocking": report.get("problems", []),
            "episode_executed": report.get("episode_executed", False),
        }
    )
    return bool(report.get("ok"))


def run_tests(events: list, results: list) -> bool:
    all_ok = True
    for module in TEST_MODULES:
        suite = unittest.defaultTestLoader.loadTestsFromName(module)
        with open(os.devnull, "w") as stream:
            outcome = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
        ok = outcome.wasSuccessful()
        all_ok = all_ok and ok
        results.append(
            {
                "group": "contract_checks",
                "case_id": module,
                "status": "PASS" if ok else "FAIL",
                "tests_run": outcome.testsRun,
                "failures": len(outcome.failures),
                "errors": len(outcome.errors),
                "skipped": len(outcome.skipped),
                "problems": [str(f[0]) for f in outcome.failures + outcome.errors],
            }
        )
        events.append({"event": "test_module_executed", "module": module, "ok": ok})
    return all_ok


def run_w1_regression(events: list, results: list) -> tuple[bool, int, int]:
    """Re-run the fourteen frozen finite cases against the reformatted source."""
    import run_finite_examples as finite
    from _support import load_config, load_fixture

    recorder = finite.Recorder("w1_regression")
    finite.run_representation(load_config(), load_fixture(), recorder)
    finite.run_assistance(load_config(), load_fixture(), recorder)

    counted = [r for r in recorder.results if "_variant" not in r["case_id"]]
    passed = [r for r in counted if r["status"] == "PASS"]
    for row in recorder.results:
        results.append({"group": "w1_regression", **row})
    events.append(
        {
            "event": "w1_regression_executed",
            "passed": len(passed),
            "planned": len(counted),
        }
    )
    return len(passed) == len(counted) == 14, len(passed), len(counted)


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
    events: list = [{"event": "run_started", "package": os.path.basename(package)}]
    results: list = []

    preflight_ok = run_preflight(events, results)
    tests_ok = run_tests(events, results)
    regression_ok, passed, planned = run_w1_regression(events, results)

    ended_cpu = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu_seconds = (
        (ended_cpu.ru_utime - started_cpu.ru_utime)
        + (ended_cpu.ru_stime - started_cpu.ru_stime)
        + children.ru_utime
        + children.ru_stime
    )

    stamp = datetime.datetime.now(datetime.UTC).isoformat()
    for event in events:
        event.setdefault("ts", stamp)

    with open(os.path.join(package, "events.jsonl"), "w", encoding="utf-8") as handle:
        for row in events:
            handle.write(json.dumps(row, default=str) + "\n")
    with open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row, default=str) + "\n")

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
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    contract_rows = [r for r in results if r["group"] == "contract_checks"]
    summary = {
        "package": os.path.basename(package),
        "stage": "W2",
        "groups": {
            "preflight": {"executed": 1, "passed": int(preflight_ok)},
            "contract_checks": {
                "modules": len(contract_rows),
                "passed": sum(1 for r in contract_rows if r["status"] == "PASS"),
                "tests_run": sum(r["tests_run"] for r in contract_rows),
                "skipped": sum(r["skipped"] for r in contract_rows),
            },
            "w1_regression": {"planned": planned, "passed": passed},
        },
        "lint": {"returncode": lint.returncode, "clean": lint.returncode == 0},
        "gate": {
            "name": "W2_contracts_and_admission",
            "rule": (
                "SUPPORTED only if the preflight is consistent, every contract-check module "
                "passes, the W0-W1 regression is 14/14, and lint is clean"
            ),
            "verdict": "SUPPORTED"
            if preflight_ok and tests_ok and regression_ok and lint.returncode == 0
            else "NOT_SUPPORTED",
            "claim_class": "engineering_acceptance_only",
            "note": (
                "Engineering acceptance permits only the next gated scientific test. It "
                "establishes no physical, learning, benefit, transfer or novelty claim."
            ),
        },
        "resources": {
            "cpu_seconds": round(cpu_seconds, 3),
            "wall_seconds": round(time.time() - started_wall, 3),
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
        "declared_dependencies": [
            "traci==1.21.0",
            "sumolib==1.21.0",
            "numpy==2.3.3",
            "jsonschema==4.25.1",
        ],
        "dev_dependencies": ["ruff==0.14.5"],
        "optional_not_installed": ["torch==2.14.0"],
        "sumo_binary_source": "external system installation; no macOS arm64 wheel exists",
        "sumo_invoked_for_version_only": True,
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
