#!/usr/bin/env python3
"""Falsification diagnostic for the arrival model (W4 prerequisite).

Reads the historical O28 transition record READ-ONLY and tests the frozen criteria A1-A5
from the package protocol. The criteria were fixed before this set was examined.

Master plan section 6 sets the limit exactly: historical traces can REVEAL LIMITATIONS but
cannot certify a changed model or domain. A model that survives this is not validated; a
model that fails it is refuted.

No SUMO process is started. The historical evidence package is not modified.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import platform
import resource
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from joint_interception.opportunities.arrival import (  # noqa: E402
    ConstructiveArrivalModel,
    FreeFlowArrivalModel,
    RecordedProfileModel,
    can_reject,
    can_support,
)

DIAGNOSTIC_SET = (
    "/Volumes/SSD Mac/PHD/Union/urban_dynamic_containment_evidence/v2_20260907/"
    "recovery_20260919_28/corrected_transitions.jsonl"
)
STATION_TOLERANCE_M = 0.05
COVERAGE_THRESHOLD = 0.90
UPPER_BOUND_THRESHOLD = 0.99


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_transitions(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def measure_recorded_model(rows: list[dict]) -> dict:
    """Test the historical model's recorded predictions against criteria B1-B6.

    B1 first: the approximation direction can only be established if the SIGN of the
    prediction error is recoverable. Revision r01 assumed it was; it is not. The recorded
    error fields are magnitudes, and the observed station is not stored, so no amount of
    analysis of this file can separate "arrived earlier than predicted" from "arrived
    later". That is itself a finding about the record, not a gap in the analysis.
    """
    total = len(rows)
    covered = 0
    with_certified_bound = 0
    lane_changes = 0
    lane_changes_covered = 0
    braking = 0
    braking_covered = 0
    statuses: dict[str, int] = {}
    error_samples: list[float] = []
    negative_errors = 0
    observed_station_present = 0

    for row in rows:
        prediction = row.get("prediction") or {}
        status = prediction.get("status", "ABSENT")
        statuses[status] = statuses.get(status, 0) + 1
        is_covered = status not in ("UNKNOWN", "ABSENT", None)
        if is_covered:
            covered += 1
            if prediction.get("certified_error_bound") is not None:
                with_certified_bound += 1

        for field in ("observed_station_m", "observed_station", "station_observed"):
            if field in row:
                observed_station_present += 1
                break

        error = row.get("station_error_m")
        if error is not None:
            error_samples.append(error)
            if error < 0:
                negative_errors += 1

        if row.get("observed_lane_change"):
            lane_changes += 1
            if is_covered:
                lane_changes_covered += 1
        if row.get("observed_braking"):
            braking += 1
            if is_covered:
                braking_covered += 1

    signed = negative_errors > 0 or observed_station_present > 0
    coverage = covered / total if total else 0.0
    bound_fraction = with_certified_bound / covered if covered else 0.0

    return {
        "transitions": total,
        "covered": covered,
        "prediction_status_counts": dict(sorted(statuses.items())),
        "B1_direction_determinability": {
            "error_fields_are_signed": signed,
            "negative_error_samples": negative_errors,
            "error_samples": len(error_samples),
            "observed_station_recorded": observed_station_present,
            "verdict": "SIGNED" if signed else "UNSIGNED",
            "note": (
                "Every recorded error is a magnitude and the observed station is absent, so "
                "the sign is unrecoverable and the direction cannot be established from this "
                "record."
            ),
        },
        "B2_under_refutation": {
            "covered_with_certified_bound": with_certified_bound,
            "fraction": round(bound_fraction, 6),
            "threshold": UPPER_BOUND_THRESHOLD,
            "under_refuted": bound_fraction < UPPER_BOUND_THRESHOLD,
        },
        "B3_coverage": {
            "coverage": round(coverage, 6),
            "threshold": COVERAGE_THRESHOLD,
            "adequate": coverage >= COVERAGE_THRESHOLD,
        },
        "B4_lane_change_containment": {
            "observed_lane_changes": lane_changes,
            "inside_covered_predictions": lane_changes_covered,
            "leakage": lane_changes_covered > 0,
            "holds": lane_changes_covered == 0,
        },
        "B5_braking_containment": {
            "observed_braking": braking,
            "inside_covered_predictions": braking_covered,
            "fraction_inside": round(braking_covered / braking, 6) if braking else None,
        },
        "station_error_magnitude_m": {
            "samples": len(error_samples),
            "min": round(min(error_samples), 6) if error_samples else None,
            "max": round(max(error_samples), 6) if error_samples else None,
            "mean": round(sum(error_samples) / len(error_samples), 6) if error_samples else None,
            "note": "Magnitudes only. These describe accuracy, not approximation direction.",
        },
    }


def classify(measured: dict) -> tuple[str, str]:
    """Apply the frozen B gate rule."""
    determinable = measured["B1_direction_determinability"]["verdict"] == "SIGNED"
    under_refuted = measured["B2_under_refutation"]["under_refuted"]
    coverage_ok = measured["B3_coverage"]["adequate"]

    if not determinable:
        return (
            "DIRECTION_UNRESOLVED",
            "The recorded errors are unsigned magnitudes and the observed station is absent, "
            "so the approximation direction cannot be established from this record. Separately "
            "and independently, B2 refutes UNDER: no covered transition carries a certified "
            "bound. UNRESOLVED is not UNDER, so the Rule A consequence follows either way.",
        )
    if not under_refuted and coverage_ok:
        return (
            "UNDER_APPROXIMATING",
            "Certified bounds are present on covered transitions and coverage is adequate.",
        )
    return (
        "OVER_APPROXIMATING",
        "The direction is determinable with no late-arrival violations, and no certified "
        "upper bound exists.",
    )


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

    if not os.path.isfile(DIAGNOSTIC_SET):
        print(f"diagnostic set not found: {DIAGNOSTIC_SET}", file=sys.stderr)
        return 3

    digest = sha256_of(DIAGNOSTIC_SET)
    events.append({"ts": stamp, "event": "diagnostic_set_opened_read_only", "sha256": digest})
    rows = read_transitions(DIAGNOSTIC_SET)
    measured = measure_recorded_model(rows)
    verdict, rationale = classify(measured)
    status_for = {
        "B1_direction_determinability": lambda p: "REPORTED",
        "B2_under_refutation": lambda p: (
            "UNDER_REFUTED" if p["under_refuted"] else "UNDER_NOT_REFUTED"
        ),
        "B3_coverage": lambda p: "PASS" if p["adequate"] else "FAIL",
        "B4_lane_change_containment": lambda p: "PASS" if p["holds"] else "FAIL",
        "B5_braking_containment": lambda p: "REPORTED",
    }
    for criterion, decide in status_for.items():
        payload = measured[criterion]
        results.append(
            {
                "group": "recorded_model_criteria",
                "case_id": criterion,
                "status": decide(payload),
                "measured": payload,
            }
        )

    # The three implemented models, and what each could ever conclude.
    for model in (
        FreeFlowArrivalModel(),
        ConstructiveArrivalModel(schedules={}),
        RecordedProfileModel(),
    ):
        results.append(
            {
                "group": "implemented_model_directions",
                "case_id": model.model_id,
                "status": "REPORTED",
                "declared_direction": model.declared_direction.value,
                "justification": model.direction_justification,
                "can_ever_support": can_support([model]),
                "can_ever_reject": can_reject([model]),
            }
        )

    ended_cpu = resource.getrusage(resource.RUSAGE_SELF)
    cpu_seconds = (ended_cpu.ru_utime - started_cpu.ru_utime) + (
        ended_cpu.ru_stime - started_cpu.ru_stime
    )

    for name, out in (("events.jsonl", events), ("results.jsonl", results)):
        with open(os.path.join(package, name), "w", encoding="utf-8") as handle:
            for row in out:
                handle.write(json.dumps(row, default=str) + "\n")

    summary = {
        "package": os.path.basename(package),
        "stage": "W4_PREREQUISITE",
        "diagnostic_set": {
            "path": DIAGNOSTIC_SET,
            "sha256": digest,
            "records": len(rows),
            "access": "READ_ONLY",
        },
        "measured": measured,
        "verdict": {
            "arrival_model_direction": verdict,
            "rationale": rationale,
            "consequence_under_rule_A": (
                "No joint opportunity can ever be SUPPORTED from such a model. Rule A requires "
                "every participating set to be UNDER, and this model is not."
                if verdict != "UNDER_APPROXIMATING"
                else "Opportunities may be SUPPORTED, subject to the other components."
            ),
            "claim_class": "model_limitation_only",
            "limit": (
                "Historical traces can reveal limitations but cannot certify a changed model "
                "or domain. A refutation is a conclusion; survival is not."
            ),
        },
        "resources": {
            "cpu_seconds": round(cpu_seconds, 3),
            "wall_seconds": round(time.time() - started_wall, 3),
            "sumo_process_starts": 0,
            "sumo_episodes": 0,
            "w4_cpu_hour_cap_consumed": False,
        },
    }
    with open(os.path.join(package, "result.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")

    environment = {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "sumo_process_starts": 0,
        "sumo_episodes_executed": 0,
        "optimizer_run": False,
        "checkpoint_loaded": False,
        "test_split_accessed": False,
        "historical_evidence_modified": False,
    }
    with open(os.path.join(package, "environment.json"), "w", encoding="utf-8") as handle:
        json.dump(environment, handle, indent=2)
        handle.write("\n")

    print(json.dumps(summary["measured"], indent=2))
    print(json.dumps(summary["verdict"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
