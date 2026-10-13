#!/usr/bin/env python3
"""Run the W0-W1 finite examples and write the evidence rows for one package.

Every planned case appears in `results.jsonl`, including failures. Nothing is dropped,
retried after modification, or excluded from the denominator.

Usage:
    python3 scripts/run_finite_examples.py --package experiments/<experiment_id>
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from _support import (  # noqa: E402
    assistance_case,
    build_opportunity,
    case,
    intervals_equal,
    load_config,
    load_fixture,
)
from joint_interception.evaluation.assistance_audit import (  # noqa: E402
    Admission,
    Alternative,
    audit_assistance,
)
from joint_interception.opportunities.reachability import (  # noqa: E402
    canonicalize,
    convex_hull,
    intersect,
    max_contiguous,
    total_width,
)
from joint_interception.opportunities.types import Verdict, verdict_and  # noqa: E402
from joint_interception.policies.memory import (  # noqa: E402
    CommitmentParameters,
    run_decision_sequence,
)

TOLERANCE = 1e-9


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Recorder:
    def __init__(self, package: str):
        self.package = package
        self.events: list[dict] = []
        self.results: list[dict] = []

    def event(self, kind: str, **payload) -> None:
        self.events.append(
            {"ts": datetime.datetime.now(datetime.UTC).isoformat(), "event": kind, **payload}
        )

    def result(self, row: dict) -> None:
        self.results.append(row)


def compare(observed, expected, field: str) -> tuple[bool, str]:
    """Compare one asserted field. Numbers use an absolute tolerance; others are exact."""
    if field.endswith("window"):
        # Any window-valued field is compared as an interval union, so that a tuple and
        # an equal list of pairs are not reported as different values.
        ok = intervals_equal(observed or (), expected or ())
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        ok = observed is not None and abs(float(observed) - float(expected)) <= TOLERANCE
    else:
        ok = observed == expected
    return ok, f"observed={observed!r} expected={expected!r}"


def check_case(case_id: str, observed: dict, expected: dict, asserted: list[str]) -> dict:
    mismatches = []
    for field in asserted:
        ok, detail = compare(observed.get(field), expected.get(field), field)
        if not ok:
            mismatches.append({"field": field, "detail": detail})
    return {
        "case_id": case_id,
        "status": "PASS" if not mismatches else "FAIL",
        "asserted_fields": asserted,
        "observed": observed,
        "mismatches": mismatches,
    }


def run_representation(config, fixture, rec: Recorder) -> None:
    exp = fixture["representation_expectations"]

    # --- F1 -------------------------------------------------------------------
    opportunity, pairwise = build_opportunity(config, "F1")
    occ_detail = json.loads(
        next(r.detail for r in opportunity.reasons if r.code.startswith("lane_capacity")).replace(
            "'", '"'
        )
    )
    lane = occ_detail["lane"]
    observed = {
        "joint_window": opportunity.joint_window,
        "max_contiguous": opportunity.max_contiguous,
        "temporal_verdict": opportunity.temporal_verdict.value,
        "occupancy_verdict": opportunity.occupancy_verdict.value,
        "movement_verdict": opportunity.movement_verdict.value,
        "joint_verdict": opportunity.verdict.value,
        "pairwise_verdict": pairwise.value,
        "pairwise_joint_discrepancy": pairwise != opportunity.verdict,
        "pairwise_is_certificate": pairwise == opportunity.verdict,
        "occupancy_required_length_m": occ_detail["required_m"],
        "occupancy_available_length_m": occ_detail["available_m"],
    }
    rec.event("case_evaluated", case_id="F1", lane=lane)
    rec.result(
        check_case(
            "F1",
            observed,
            exp["F1"],
            [
                "joint_window",
                "max_contiguous",
                "temporal_verdict",
                "occupancy_verdict",
                "movement_verdict",
                "joint_verdict",
                "pairwise_verdict",
                "pairwise_joint_discrepancy",
                "pairwise_is_certificate",
                "occupancy_required_length_m",
                "occupancy_available_length_m",
            ],
        )
    )

    variant, _ = build_opportunity(config, "F1", direction_override="PREDICTION")
    rec.result(
        check_case(
            "F1_variant_unknown_temporal",
            {
                "temporal_verdict": variant.temporal_verdict.value,
                "occupancy_verdict": variant.occupancy_verdict.value,
                "joint_verdict": variant.verdict.value,
            },
            exp["F1"]["variant_unknown_temporal"],
            ["temporal_verdict", "occupancy_verdict", "joint_verdict"],
        )
    )

    # --- F2 -------------------------------------------------------------------
    opportunity, pairwise = build_opportunity(config, "F2")
    rec.result(
        check_case(
            "F2",
            {
                "joint_window": opportunity.joint_window,
                "joint_window_total_width": total_width(opportunity.joint_window),
                "max_contiguous": opportunity.max_contiguous,
                "margin": opportunity.margin,
                "temporal_verdict": opportunity.temporal_verdict.value,
                "occupancy_verdict": opportunity.occupancy_verdict.value,
                "movement_verdict": opportunity.movement_verdict.value,
                "joint_verdict": opportunity.verdict.value,
                "pairwise_verdict": pairwise.value,
                "pairwise_joint_discrepancy": pairwise != opportunity.verdict,
            },
            exp["F2"],
            [
                "joint_window",
                "joint_window_total_width",
                "max_contiguous",
                "margin",
                "temporal_verdict",
                "occupancy_verdict",
                "movement_verdict",
                "joint_verdict",
                "pairwise_verdict",
                "pairwise_joint_discrepancy",
            ],
        )
    )

    # --- F3 -------------------------------------------------------------------
    opportunity, _ = build_opportunity(config, "F3")
    spec = case(config, "F3")
    p1 = canonicalize(spec["arrival_sets"]["p1"]["intervals"])
    p2 = canonicalize(spec["arrival_sets"]["p2"]["intervals"])
    hull_window = intersect(convex_hull(p1), p2)
    rec.result(
        check_case(
            "F3",
            {
                "joint_window": opportunity.joint_window,
                "max_contiguous": opportunity.max_contiguous,
                "temporal_verdict": opportunity.temporal_verdict.value,
                "joint_verdict": opportunity.verdict.value,
                "hull_window": hull_window,
                "hull_would_give_max_contiguous": max_contiguous(hull_window),
                "hull_is_incorrect": hull_window != opportunity.joint_window,
            },
            {**exp["F3"], "hull_window": exp["F3"]["hull_would_give_window"]},
            [
                "joint_window",
                "max_contiguous",
                "temporal_verdict",
                "joint_verdict",
                "hull_window",
                "hull_would_give_max_contiguous",
                "hull_is_incorrect",
            ],
        )
    )

    under, _ = build_opportunity(config, "F3", direction_override="UNDER")
    rec.result(
        check_case(
            "F3_under_variant",
            {
                "temporal_verdict": under.temporal_verdict.value,
                "joint_verdict": under.verdict.value,
            },
            exp["F3"]["under_variant"],
            ["temporal_verdict", "joint_verdict"],
        )
    )

    # --- F4 -------------------------------------------------------------------
    opportunity, _ = build_opportunity(config, "F4")
    spec = case(config, "F4")
    declared, examined = spec["evader_branches"], spec["examined_branches"]
    coverage = len(examined) / len(declared)
    all_branch = verdict_and(
        [opportunity.verdict if b in examined else Verdict.UNKNOWN for b in declared]
    )
    rec.result(
        check_case(
            "F4",
            {
                "b1_joint_window": opportunity.joint_window,
                "b1_max_contiguous": opportunity.max_contiguous,
                "coverage": coverage,
                "all_branch_verdict": all_branch.value,
                "all_branch_claim_permitted": coverage >= 1.0,
            },
            {**exp["F4"], "b1_joint_window": exp["F4"]["b1_joint_window"]},
            [
                "b1_joint_window",
                "b1_max_contiguous",
                "coverage",
                "all_branch_verdict",
                "all_branch_claim_permitted",
            ],
        )
    )

    # --- F5 -------------------------------------------------------------------
    opportunity, _ = build_opportunity(config, "F5")
    spec = case(config, "F5")
    admission = spec["step_admission"]
    sequence = verdict_and([Verdict(admission["step_1"]), Verdict(admission["step_4"])])
    rec.result(
        check_case(
            "F5",
            {
                "temporal_verdict": opportunity.temporal_verdict.value,
                "occupancy_verdict": opportunity.occupancy_verdict.value,
                "movement_verdict": opportunity.movement_verdict.value,
                "joint_verdict": opportunity.verdict.value,
                "step_1_admission": admission["step_1"],
                "sequence_admission": sequence.value,
                "one_step_safety_certifies_sequence": admission["step_1"] == sequence.value,
                "execution_permitted": opportunity.verdict is Verdict.SUPPORTED,
            },
            exp["F5"],
            [
                "temporal_verdict",
                "occupancy_verdict",
                "movement_verdict",
                "joint_verdict",
                "step_1_admission",
                "sequence_admission",
                "one_step_safety_certifies_sequence",
                "execution_permitted",
            ],
        )
    )

    # --- F6 -------------------------------------------------------------------
    spec = case(config, "F6")
    steps = [
        (d["t"], d["candidate_scores"], {k: Verdict(v) for k, v in d["candidate_verdicts"].items()})
        for d in spec["decisions"]
    ]

    def make(arm):
        values = config["commitment_parameters"][arm]
        return CommitmentParameters(
            values["max_commit_duration"], values["switch_margin"], values["unknown_tolerance"]
        )

    j1 = run_decision_sequence(steps, make("J1"))
    j0 = run_decision_sequence(steps, make("J0"))
    degenerate = run_decision_sequence(
        steps, CommitmentParameters(max_commit_duration=1, switch_margin=0.0, unknown_tolerance=0)
    )
    trace = lambda ds: [(d.t, d.selected_opportunity_id, d.decision) for d in ds]  # noqa: E731
    rec.result(
        check_case(
            "F6",
            {
                "J1_t1_selected": j1[0].selected_opportunity_id,
                "J1_t1_decision": j1[0].decision,
                "J1_t2_selected": j1[1].selected_opportunity_id,
                "J1_t2_decision": j1[1].decision,
                "J1_final_selected": j1[-1].selected_opportunity_id,
                "J1_switch_count": j1[-1].memory.switch_count,
                "J0_t1_selected": j0[0].selected_opportunity_id,
                "J0_t2_selected": j0[1].selected_opportunity_id,
                "J0_final_selected": j0[-1].selected_opportunity_id,
                "memory_changes_later_choice": j1[-1].selected_opportunity_id
                != j0[-1].selected_opportunity_id,
                "degeneracy_holds": trace(degenerate) == trace(j0),
            },
            {
                "J1_t1_selected": exp["F6"]["J1"]["t1_selected"],
                "J1_t1_decision": exp["F6"]["J1"]["t1_decision"],
                "J1_t2_selected": exp["F6"]["J1"]["t2_selected"],
                "J1_t2_decision": exp["F6"]["J1"]["t2_decision"],
                "J1_final_selected": exp["F6"]["J1"]["final_selected"],
                "J1_switch_count": exp["F6"]["J1"]["switch_count"],
                "J0_t1_selected": exp["F6"]["J0"]["t1_selected"],
                "J0_t2_selected": exp["F6"]["J0"]["t2_selected"],
                "J0_final_selected": exp["F6"]["J0"]["final_selected"],
                "memory_changes_later_choice": exp["F6"]["memory_changes_later_choice"],
                "degeneracy_holds": exp["F6"]["degeneracy_assertion"]["expected_equal"],
            },
            [
                "J1_t1_selected",
                "J1_t1_decision",
                "J1_t2_selected",
                "J1_t2_decision",
                "J1_final_selected",
                "J1_switch_count",
                "J0_t1_selected",
                "J0_t2_selected",
                "J0_final_selected",
                "memory_changes_later_choice",
                "degeneracy_holds",
            ],
        )
    )


def run_assistance(config, fixture, rec: Recorder) -> None:
    exp = fixture["assistance_expectations"]
    for case_id in ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"):
        spec = assistance_case(config, case_id)
        family = [
            Alternative(i["alternative"], Admission(i["admission"]), i["outcome"])
            for i in spec["declared_family"]
        ]
        result = audit_assistance(spec["helper"], spec["factual_outcome"], family)
        observed = {
            "label": result.label.value,
            "envelope_lower": result.envelope[0],
            "envelope_upper": result.envelope[1],
            "incomplete_family": result.incomplete_family,
            "complete_family_conclusion_permitted": result.complete_family_conclusion_permitted,
            "per_alternative_bounds": {
                k: list(v) for k, v in result.per_alternative_bounds.items()
            },
        }
        expected = {
            "label": exp[case_id]["label"],
            "envelope_lower": exp[case_id]["envelope"][0],
            "envelope_upper": exp[case_id]["envelope"][1],
            "incomplete_family": exp[case_id]["incomplete_family"],
            "complete_family_conclusion_permitted": exp[case_id][
                "complete_family_conclusion_permitted"
            ],
            "per_alternative_bounds": exp[case_id]["per_alternative_bounds"],
        }
        asserted = list(expected)
        if case_id == "A2":
            coalition = float(1 - spec["coalition_note"]["joint_withdrawal_of_h1_and_h2_outcome"])
            observed["coalition_effect"] = coalition
            observed["individual_effects_sum"] = sum(
                v[0] for v in result.per_alternative_bounds.values()
            )
            observed["additivity_holds"] = (
                abs(observed["individual_effects_sum"] - coalition) <= TOLERANCE
            )
            expected["coalition_effect"] = exp[case_id]["coalition_effect"]
            expected["individual_effects_sum"] = exp[case_id]["individual_effects_sum"]
            expected["additivity_holds"] = exp[case_id]["additivity_holds"]
            asserted += ["coalition_effect", "individual_effects_sum", "additivity_holds"]
        if case_id == "A8":
            observed["excluded_members"] = result.excluded_members
            expected["excluded_members"] = exp[case_id]["excluded_members"]
            asserted += ["excluded_members"]
        rec.event("case_evaluated", case_id=case_id)
        rec.result(check_case(case_id, observed, expected, asserted))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True, help="path to the experiment package")
    parser.add_argument(
        "--reseal",
        action="store_true",
        help="permit writing into an already-sealed package; requires a recorded deviation",
    )
    args = parser.parse_args()
    package = args.package if os.path.isabs(args.package) else os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)

    # A sealed package must not be overwritten by accident. This guard exists because it
    # already happened twice: once inside W1 (deviation D-04) and once during the W2
    # dependency check, when a re-run silently rewrote this package's events.jsonl and
    # result.json after it had been sealed.
    if os.path.isfile(os.path.join(package, "checksums.json")) and not args.reseal:
        print(
            f"REFUSED: {os.path.basename(package)} is sealed. Write a new revision "
            f"(…_r02) instead, or pass --reseal and record a deviation.",
            file=sys.stderr,
        )
        return 2

    started_wall = time.time()
    started_cpu = resource.getrusage(resource.RUSAGE_SELF)

    config, fixture = load_config(), load_fixture()
    rec = Recorder(package)
    rec.event("run_started", package=os.path.basename(package))
    rec.event(
        "inputs_loaded",
        config_sha256=sha256_of(os.path.join(ROOT, "configs/finite_examples_v1.json")),
        fixture_sha256=sha256_of(os.path.join(ROOT, "tests/fixtures/finite_cases_v1.json")),
    )

    run_representation(config, fixture, rec)
    run_assistance(config, fixture, rec)

    test_proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "tests"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    test_output = test_proc.stderr.strip().splitlines()
    ran_line = next((line for line in test_output if line.startswith("Ran ")), "")
    rec.event("test_suite_executed", returncode=test_proc.returncode, summary=ran_line)

    ended_cpu = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu_seconds = (
        (ended_cpu.ru_utime - started_cpu.ru_utime)
        + (ended_cpu.ru_stime - started_cpu.ru_stime)
        + children.ru_utime
        + children.ru_stime
    )
    wall_seconds = time.time() - started_wall

    counted = [r for r in rec.results if "_variant" not in r["case_id"]]
    passed = [r for r in counted if r["status"] == "PASS"]
    variants = [r for r in rec.results if "_variant" in r["case_id"]]

    environment = {
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "external_dependencies": [],
        "dependency_policy": "Python standard library only at W0-W1; pinning deferred to W2 (D16).",
        "sumo_invoked": False,
        "optimizer_run": False,
        "checkpoint_loaded": False,
        "test_split_accessed": False,
        "legacy_module_imported": False,
    }
    with open(os.path.join(package, "environment.json"), "w", encoding="utf-8") as handle:
        json.dump(environment, handle, indent=2)
        handle.write("\n")

    with open(os.path.join(package, "events.jsonl"), "w", encoding="utf-8") as handle:
        for row in rec.events:
            handle.write(json.dumps(row, default=str) + "\n")

    with open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as handle:
        for row in rec.results:
            handle.write(json.dumps(row, default=str) + "\n")

    summary = {
        "package": os.path.basename(package),
        "stage": "W0_W1",
        "planned_cases": 14,
        "executed_cases": len(counted),
        "passed": len(passed),
        "failed": len(counted) - len(passed),
        "errors": 0,
        "not_executed": 14 - len(counted),
        "additional_variant_checks": {
            "executed": len(variants),
            "passed": len([r for r in variants if r["status"] == "PASS"]),
        },
        "unit_tests": {"returncode": test_proc.returncode, "summary": ran_line},
        "gate": {
            "name": "W1_analytical_correctness",
            "rule": "SUPPORTED only if 14/14 cases PASS and the cross-checks hold",
            "verdict": "SUPPORTED"
            if len(passed) == 14 and test_proc.returncode == 0
            else "NOT_SUPPORTED",
            "claim_class": "analytical_correctness_only",
        },
        "resources": {
            "cpu_seconds": round(cpu_seconds, 3),
            "wall_seconds": round(wall_seconds, 3),
            "cpu_minutes": round(cpu_seconds / 60.0, 4),
            "cap_cpu_minutes": 30,
        },
        "per_case": {r["case_id"]: r["status"] for r in rec.results},
    }
    with open(os.path.join(package, "result.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")

    print(json.dumps(summary, indent=2))
    return 0 if summary["gate"]["verdict"] == "SUPPORTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
