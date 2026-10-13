#!/usr/bin/env python3
"""Run the constructive-witness checks C1-C6 and write the evidence rows.

Criteria were frozen in the package protocol before any implementation existed. Each maps
to the test classes that decide it, so a renamed test cannot leave a criterion without
evidence.

No SUMO process is started. W4's two-CPU-hour cap is not consumed.
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
    "C1_earliest_arrives_exactly": ["test_constructive_schedule.TestC1EarliestArrival"],
    "C2_interval_fullness": ["test_constructive_schedule.TestC2IntervalFullness"],
    "C3_legality": ["test_constructive_schedule.TestC3Legality"],
    "C4_under_is_earned": [
        "test_constructive_schedule.TestC4UnderIsEarned",
        "test_arrival_model.TestScheduledArrivalModel",
    ],
    "C5_nonconvexity": ["test_constructive_schedule.TestC5Nonconvexity"],
    "C6_end_to_end": ["test_constructive_schedule.TestC6EndToEnd"],
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


def measure_witness() -> dict:
    """Report the witness actually produced, so the numbers are in the record."""
    from joint_interception.opportunities.schedule import (
        arrival_at,
        constructive_arrival_set,
        earliest_arrival,
    )

    distance, speed, limit, accel, decel, horizon = 100.0, 3.0, 13.89, 2.6, 4.5, 300.0
    plain = constructive_arrival_set("p1", distance, speed, limit, accel, decel, horizon)
    blocked = constructive_arrival_set(
        "p1",
        distance,
        speed,
        limit,
        accel,
        decel,
        horizon,
        blocking_windows=((20.0, 40.0), (60.0, 75.0)),
    )
    independent, _ = earliest_arrival(distance, speed, limit, accel)

    worst_distance_error = 0.0
    worst_time_error = 0.0
    violations = 0
    samples = 0
    for index in range(400):
        t = independent + (150.0 - independent) * index / 399
        profile = arrival_at(distance, speed, limit, accel, decel, t)
        if profile is None:
            continue
        covered, _ = profile.integrate()
        worst_distance_error = max(worst_distance_error, abs(covered - distance))
        worst_time_error = max(worst_time_error, abs(profile.duration_s - t))
        violations += len(profile.violations(limit, accel, decel))
        samples += 1

    return {
        "unblocked_witness": {
            "intervals": [list(i) for i in plain.arrival_set.intervals],
            "direction": plain.arrival_set.direction.value,
            "earliest_s": round(plain.earliest_s, 9),
            "certified_upper_bound_s": plain.latest_s,
            "verified_sample_count": plain.verified_sample_count,
        },
        "blocked_witness": {
            "intervals": [list(i) for i in blocked.arrival_set.intervals],
            "interval_count": len(blocked.arrival_set.intervals),
            "nonconvex": len(blocked.arrival_set.intervals) > 1,
        },
        "independent_earliest_s": round(independent, 9),
        "earliest_agrees_with_witness": abs(independent - plain.earliest_s) < 1e-9,
        "integration_check": {
            "samples": samples,
            "worst_distance_error_m": worst_distance_error,
            "worst_time_error_s": worst_time_error,
            "legality_violations": violations,
        },
    }


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
                "group": "constructive_checks",
                "case_id": check_id,
                "status": "PASS" if ok else "FAIL",
                "test_classes": names,
                "tests_run": ran,
                "problems": problems,
            }
        )
        events.append({"ts": stamp, "event": "check_executed", "check": check_id, "ok": ok})

    measured = measure_witness()
    results.append(
        {
            "group": "witness",
            "case_id": "produced_witness",
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
    regression_ok = full.returncode == 0 and lint.returncode == 0
    results.append(
        {
            "group": "regression",
            "case_id": "full_suite_and_lint",
            "status": "PASS" if regression_ok else "FAIL",
            "full_suite_returncode": full.returncode,
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

    checks = [r for r in results if r["group"] == "constructive_checks"]
    summary = {
        "package": os.path.basename(package),
        "stage": "W4_PREREQUISITE",
        "checks": {
            "planned": len(CHECKS),
            "executed": len(checks),
            "passed": sum(1 for r in checks if r["status"] == "PASS"),
            "tests_run": sum(r["tests_run"] for r in checks),
        },
        "witness": measured,
        "regression": {"full_suite_ok": full.returncode == 0, "lint_clean": lint.returncode == 0},
        "gate": {
            "name": "W4_prereq_constructive_arrival_witnesses",
            "rule": "SUPPORTED only if all six criteria pass",
            "verdict": "SUPPORTED" if all_ok and regression_ok else "NOT_SUPPORTED",
            "claim_class": "analytical_correctness_in_a_finite_abstraction_only",
            "claim_supported": (
                "An UNDER-approximating arrival set can be produced and its label EARNED, "
                "in the declared finite abstraction."
            ),
            "explicitly_not_established": [
                "that constructive witnesses can be produced on a real SUMO network",
                "handling of interaction between participants' committed plans",
                "physical feasibility, assistance, learning, benefit, transfer or novelty",
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
            "w4_cpu_hour_cap_consumed": False,
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
                "abstraction": (
                    "one-dimensional path with bounded acceleration; no junctions, lane "
                    "changes, traffic or signals"
                ),
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
            {"checks": summary["checks"], "gate": summary["gate"]["verdict"], "witness": measured},
            indent=2,
        )
    )
    return 0 if summary["gate"]["verdict"] == "SUPPORTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
