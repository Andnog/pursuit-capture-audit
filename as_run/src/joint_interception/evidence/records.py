"""Construction of evidence rows that satisfy both validation layers.

Rows are built here and nowhere else, so every row in every package passes the schema and
the semantic invariants. A row that cannot be constructed is a row that must not be
written.
"""

from __future__ import annotations

from ..domain.contracts import CONTRACT_VERSION, validate_episode_result

UNKNOWN = "UNKNOWN"


def build_episode_result(
    case_id: str,
    arm: str,
    split: str,
    city: str,
    scenario_id: str,
    environment_seed: int,
    input_hashes: dict[str, str],
    status: str,
    endpoint_cause: str,
    y_outcome,
    z_outcome,
    physical_validity: str,
    audit_coverage: float,
    wall_seconds: float,
    cpu_seconds: float,
    evidence_paths: list[str],
    endpoint_time_s: float | None = None,
    training_seed: int | None = None,
    audit_seed: int | None = None,
    safety_failures: int = 0,
    guard_interventions: int = 0,
    commitment_switches: int = 0,
    assistance_label: str | None = None,
    reasons: list[str] | None = None,
    **cost_detail,
) -> dict:
    """Build one validated row. Raises `ContractViolation` rather than writing a bad row."""
    record = {
        "contract_version": CONTRACT_VERSION,
        "case_id": case_id,
        "arm": arm,
        "split": split,
        "city": city,
        "scenario_id": scenario_id,
        "seeds": {
            "environment": environment_seed,
            "training": training_seed,
            "audit": audit_seed,
        },
        "input_hashes": input_hashes,
        "status": status,
        "endpoint_cause": endpoint_cause,
        "Y": y_outcome,
        "Z": z_outcome,
        "endpoint_time_s": endpoint_time_s,
        "physical_validity": physical_validity,
        "safety_failures": safety_failures,
        "guard_interventions": guard_interventions,
        "commitment_switches": commitment_switches,
        "audit_coverage": audit_coverage,
        "assistance_label": assistance_label,
        "reasons": list(reasons or []),
        "cost": {
            "wall_seconds": wall_seconds,
            "cpu_seconds": cpu_seconds,
            "candidate_generation_s": cost_detail.get("candidate_generation_s"),
            "compatibility_s": cost_detail.get("compatibility_s"),
            "inference_s": cost_detail.get("inference_s"),
            "deadline_misses": cost_detail.get("deadline_misses"),
        },
        "evidence_paths": evidence_paths,
    }
    validate_episode_result(record)
    return record


def build_not_executed_row(
    case_id: str,
    arm: str,
    split: str,
    city: str,
    scenario_id: str,
    environment_seed: int,
    input_hashes: dict[str, str],
    reason: str,
    evidence_paths: list[str],
) -> dict:
    """A planned case that did not run.

    It stays in the denominator with no outcome. Master plan section 9: not-executed cases
    are reported separately with planned and executed denominators, and must never be
    described as observed physical failures.
    """
    return build_episode_result(
        case_id=case_id,
        arm=arm,
        split=split,
        city=city,
        scenario_id=scenario_id,
        environment_seed=environment_seed,
        input_hashes=input_hashes,
        status="NOT_EXECUTED",
        endpoint_cause=UNKNOWN,
        y_outcome=UNKNOWN,
        z_outcome=UNKNOWN,
        physical_validity=UNKNOWN,
        audit_coverage=0.0,
        wall_seconds=0.0,
        cpu_seconds=0.0,
        evidence_paths=evidence_paths,
        reasons=[reason],
    )


def endpoint_bounds_over_rows(rows: list[dict]) -> tuple[float, float]:
    """Logical bounds `[S/N, (S+U)/N]` for the assisted-capture endpoint over rows.

    These are missing-outcome bounds, not confidence intervals.
    """
    executed = [r for r in rows if r["status"] != "NOT_EXECUTED"]
    if not executed:
        raise ValueError("no executed rows; bounds are undefined")
    supported = sum(1 for r in executed if r["Z"] == 1)
    unresolved = sum(1 for r in executed if r["Z"] == UNKNOWN)
    total = len(executed)
    return supported / total, (supported + unresolved) / total
