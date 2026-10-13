#!/usr/bin/env python3
"""Run the scripted-evader checks E1-E6 and write the evidence rows.

Checks were frozen in the package protocol before running. Each maps to the test classes
that decide it, so a renamed test cannot leave a check without evidence.

No SUMO process is started.
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

CHECKS = {
    "E1_determinism": ["test_evader_levels.TestDeterminism"],
    "E2_keyed_not_sequential_randomness": ["test_evader_levels.TestDeterminism"],
    "E3_levels_differ_in_difficulty": [
        "test_evader_levels.TestLevelOrdering",
        "test_evader_levels.TestScoreSentinelsDoNotCollide",
        "test_evader_levels.TestDifficultyOrderingIsMonotone",
    ],
    "E4_decision_record_supports_d06": [
        "test_evader_levels.TestDecisionRecordSupportsTheD06DeadEndRule"
    ],
    "E5_information_boundary": ["test_evader_levels.TestInformationBoundaryOfTheEvader"],
    "E6_contract_agreement": [
        "test_capture_judge.TestEvaderIsAScriptedDifficultyLevel",
        "test_evader_levels.TestTopology",
    ],
}


def run_named(names: list[str]) -> tuple[bool, int, list[str]]:
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)
    with open(os.devnull, "w") as stream:
        outcome = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    return (
        outcome.wasSuccessful(),
        outcome.testsRun,
        [str(f[0]) for f in outcome.failures + outcome.errors],
    )


def measure_levels() -> dict:
    """Report what the three levels actually do, so the numbers are in the record."""
    from joint_interception.simulator.evader import EvaderLevel, ScriptedEvader
    from joint_interception.simulator.topology import Edge, Topology

    topology = Topology.build(
        [
            Edge("e1", "A", "B", 100.0),
            Edge("e_open", "B", "C", 100.0),
            Edge("e_dead", "B", "D", 100.0),
            Edge("e_onward", "C", "E", 100.0),
        ]
    )
    trials = 200
    out: dict = {"trials_per_level": trials, "topology": "A->B, B branches to open C or dead D"}
    for level in EvaderLevel:
        entered_dead_end = 0
        for seed in range(trials):
            evader = ScriptedEvader(level, seed, topology)
            if evader.choose(0, "e1", {"p1": "E"}).chosen == "e_dead":
                entered_dead_end += 1
        out[level.name] = {
            "level": int(level),
            "entered_dead_end": entered_dead_end,
            "dead_end_rate": round(entered_dead_end / trials, 4),
        }
    out["difficulty_ordering_holds"] = (
        out["OPTIMAL_ESCAPE"]["entered_dead_end"] == 0 and out["RANDOM"]["entered_dead_end"] > 0
    )
    return out


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
    events = [{"ts": stamp, "event": "run_started", "package": os.path.basename(package)}]
    results = []

    all_ok = True
    for check_id, names in CHECKS.items():
        ok, ran, problems = run_named(names)
        all_ok = all_ok and ok
        results.append(
            {
                "group": "evader_checks",
                "case_id": check_id,
                "status": "PASS" if ok else "FAIL",
                "test_classes": names,
                "tests_run": ran,
                "problems": problems,
            }
        )
        events.append({"ts": stamp, "event": "check_executed", "check": check_id, "ok": ok})

    measured = measure_levels()
    results.append(
        {
            "group": "levels",
            "case_id": "difficulty_measurement",
            "status": "REPORTED",
            "measured": measured,
        }
    )

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
    regression_ok = full.returncode == 0 and bare.returncode == 0 and lint.returncode == 0
    results.append(
        {
            "group": "regression",
            "case_id": "full_suite_bare_and_lint",
            "status": "PASS" if regression_ok else "FAIL",
            "full_suite_returncode": full.returncode,
            "bare_interpreter_returncode": bare.returncode,
            "lint_returncode": lint.returncode,
        }
    )

    ended_cpu = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu_seconds = (
        (ended_cpu.ru_utime - started_cpu.ru_utime)
        + (ended_cpu.ru_stime - started_cpu.ru_stime)
        + children.ru_utime
        + children.ru_stime
    )

    for name, out in (("events.jsonl", events), ("results.jsonl", results)):
        with open(os.path.join(package, name), "w", encoding="utf-8") as handle:
            for row in out:
                handle.write(json.dumps(row, default=str) + "\n")

    checks = [r for r in results if r["group"] == "evader_checks"]
    summary = {
        "package": os.path.basename(package),
        "stage": "W3_COMPLETION",
        "checks": {
            "planned": len(CHECKS),
            "executed": len(checks),
            "passed": sum(1 for r in checks if r["status"] == "PASS"),
            "tests_run": sum(r["tests_run"] for r in checks),
        },
        "levels": measured,
        "regression": {
            "full_suite_ok": full.returncode == 0,
            "bare_interpreter_ok": bare.returncode == 0,
            "lint_clean": lint.returncode == 0,
        },
        "gate": {
            "name": "W3_scripted_evader",
            "rule": (
                "SUPPORTED only if all six checks pass, both interpreters pass, and lint is clean"
            ),
            "verdict": "SUPPORTED" if all_ok and regression_ok else "NOT_SUPPORTED",
            "claim_class": "engineering_acceptance_only",
            "explicitly_not_established": [
                "that any of this runs against a real network; no SUMO process was started",
                "physical feasibility, assistance, learning, benefit or transfer",
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
    with open(os.path.join(package, "environment.json"), "w", encoding="utf-8") as handle:
        json.dump(
            {
                "python_version": sys.version.split()[0],
                "platform": platform.platform(),
                "machine": platform.machine(),
                "topology": "in-memory directed graph, not one of the 12 audited OSM networks",
                "sumo_process_starts": 0,
                "sumo_episodes_executed": 0,
                "optimizer_run": False,
                "checkpoint_loaded": False,
                "test_split_accessed": False,
            },
            handle,
            indent=2,
        )
        handle.write("\n")

    print(
        json.dumps(
            {"checks": summary["checks"], "levels": measured, "gate": summary["gate"]["verdict"]},
            indent=2,
        )
    )
    return 0 if summary["gate"]["verdict"] == "SUPPORTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
