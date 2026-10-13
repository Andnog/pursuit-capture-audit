"""Contract loading, schema validation and the semantic invariants schemas cannot express.

Two layers, deliberately separate:

1. **Schema validation** rejects structurally wrong records: missing critical fields,
   wrong types, out-of-range values and unknown extra keys. JSON Schema does this well.
2. **Semantic invariants** reject records that are structurally valid but scientifically
   wrong. JSON Schema cannot express "a capture whose required audit is unresolved must
   record Z = UNKNOWN, never 1", and that is exactly the kind of error that would
   silently inflate the primary endpoint.

A record must pass BOTH layers. `validate_episode_result` runs both.
"""

from __future__ import annotations

import functools
import json
import os
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

CONTRACT_VERSION = "task_contract_v1"

_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
CONTRACTS_DIR = os.path.join(_ROOT, "contracts")
CONFIGS_DIR = os.path.join(_ROOT, "configs")

SCHEMA_NAMES = (
    "public_observation",
    "action",
    "opportunity",
    "episode_result",
)


class ContractViolation(ValueError):
    """Raised when a record violates the schema or a semantic invariant."""

    def __init__(self, layer: str, problems: list[str]):
        self.layer = layer
        self.problems = problems
        super().__init__(f"{layer}: " + "; ".join(problems))


@functools.cache
def load_schema(name: str) -> dict:
    if name not in SCHEMA_NAMES:
        raise KeyError(f"unknown schema {name!r}; known: {SCHEMA_NAMES}")
    path = os.path.join(CONTRACTS_DIR, f"{name}.schema.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


@functools.cache
def _validator(name: str) -> Draft202012Validator:
    schema = load_schema(name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@functools.cache
def load_domain(config_id: str = "domain_v1") -> dict:
    path = os.path.join(CONFIGS_DIR, f"{config_id}.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def schema_problems(name: str, record: Any) -> list[str]:
    """Return every schema problem, not only the first, so a record can be fixed in one pass."""
    errors = sorted(_validator(name).iter_errors(record), key=lambda e: list(e.path))
    return [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors]


def validate(name: str, record: Any) -> None:
    problems = schema_problems(name, record)
    if problems:
        raise ContractViolation(f"schema:{name}", problems)


# --------------------------------------------------------------------------------------
# Semantic invariants
# --------------------------------------------------------------------------------------


def episode_result_invariants(record: dict) -> list[str]:
    """Invariants over one episode result that JSON Schema cannot express.

    Each one corresponds to a way the primary endpoint could be silently inflated or a
    failure silently erased.
    """
    problems: list[str] = []
    y, z = record.get("Y"), record.get("Z")
    cause = record.get("endpoint_cause")
    status = record.get("status")
    coverage = record.get("audit_coverage")
    captures = {"CAPTURE_MOVING_CIRCULATION", "CAPTURE_AFTER_ROUTE_ENDPOINT"}

    # Z is capture AND supported assistance, so Z = 1 requires Y = 1.
    if z == 1 and y != 1:
        problems.append("Z=1 requires Y=1: assisted capture cannot occur without capture")

    # A known non-capture is a known non-assisted-capture.
    if y == 0 and z != 0:
        problems.append("Y=0 requires Z=0: known non-capture gives Z=0, not UNKNOWN")

    # The rule that keeps the primary endpoint honest.
    if y == 1 and z == 1 and (coverage is None or coverage < 1.0):
        problems.append(
            "Z=1 requires audit_coverage=1.0: a capture whose required audit is unresolved "
            "gives Z=UNKNOWN, never 1"
        )

    # Endpoint cause and Y must agree.
    if cause in captures and y != 1:
        problems.append(f"endpoint_cause={cause} requires Y=1")
    if y == 1 and cause not in captures:
        problems.append(f"Y=1 requires a capture endpoint_cause, got {cause!r}")

    # A safety failure invalidates the physical result; it is never a capture.
    if cause == "SAFETY_FAILURE" and y == 1:
        problems.append("SAFETY_FAILURE cannot coincide with Y=1")
    if record.get("physical_validity") == "FAIL" and y == 1:
        problems.append("physical_validity=FAIL cannot coincide with Y=1")

    # An incomplete trace cannot yield a resolved outcome.
    if cause == "INTEGRITY_FAILURE_INCOMPLETE_TRACE" and y != "UNKNOWN":
        problems.append("INTEGRITY_FAILURE_INCOMPLETE_TRACE requires Y=UNKNOWN")

    # Not-executed cases stay in the denominator but carry no outcome.
    if status in {"NOT_EXECUTED", "CANCELLED"} and (y != "UNKNOWN" or z != "UNKNOWN"):
        problems.append(f"status={status} requires Y=UNKNOWN and Z=UNKNOWN")

    # Endpoint time must exist for a resolved capture and respect the horizon.
    horizon = load_domain()["timing"]["horizon_s"]
    endpoint_time = record.get("endpoint_time_s")
    if y == 1 and endpoint_time is None:
        problems.append("Y=1 requires endpoint_time_s")
    if endpoint_time is not None and endpoint_time > horizon:
        problems.append(f"endpoint_time_s={endpoint_time} exceeds horizon {horizon}")

    # An assistance label that asserts a positive effect requires full coverage.
    if record.get("assistance_label") == "POSITIVE_ACROSS_FAMILY" and (
        coverage is None or coverage < 1.0
    ):
        problems.append(
            "POSITIVE_ACROSS_FAMILY requires audit_coverage=1.0; an incomplete family "
            "cannot support a complete-family conclusion"
        )
    return problems


def validate_episode_result(record: dict) -> None:
    """Validate both layers. Schema first, because invariants assume well-formed fields."""
    validate("episode_result", record)
    problems = episode_result_invariants(record)
    if problems:
        raise ContractViolation("invariants:episode_result", problems)


def observation_invariants(record: dict) -> list[str]:
    """Invariants over one public observation."""
    problems: list[str] = []
    domain = load_domain()
    prohibited = set(domain["observation"]["prohibited_observation_keys"])
    vehicles = record.get("vehicles", [])

    ids = [v.get("vehicle_id") for v in vehicles]
    if len(ids) != len(set(ids)):
        problems.append("duplicate vehicle_id in a single observation")

    classes = [v.get("vehicle_class") for v in vehicles]
    if classes.count("evader") > domain["team"]["evaders"]:
        problems.append("more evaders than the contract declares")
    if classes.count("pursuer") > domain["team"]["pursuers"]:
        problems.append("more pursuers than the contract declares")

    # The decision index and the simulation clock must agree with the decision interval.
    interval = domain["timing"]["decision_interval_s"]
    index, clock = record.get("decision_index"), record.get("simulation_time_s")
    if index is not None and clock is not None and abs(clock - index * interval) > 1e-6:
        problems.append(
            f"simulation_time_s={clock} disagrees with decision_index={index} "
            f"at interval {interval}"
        )

    # Defence in depth. The schema is closed, so an extra key is already rejected; this
    # names WHICH prohibited key appeared, at any depth, instead of reporting a generic
    # "additional property". The check uses the machine-readable key list, never the prose
    # list: the prose contains the word "evader", which is a legitimate vehicle_class, and
    # pattern-matching prose against data is precisely the defect recorded as W1
    # deviation D-02.
    found = sorted(_prohibited_keys_present(record, prohibited))
    problems.extend(f"prohibited key {key!r} present in the observation" for key in found)
    return problems


def _prohibited_keys_present(node: Any, prohibited: set[str]) -> set[str]:
    """Every prohibited key appearing anywhere in a nested structure."""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key in prohibited:
                found.add(key)
            found |= _prohibited_keys_present(value, prohibited)
    elif isinstance(node, list):
        for item in node:
            found |= _prohibited_keys_present(item, prohibited)
    return found


def validate_observation(record: dict) -> None:
    validate("public_observation", record)
    problems = observation_invariants(record)
    if problems:
        raise ContractViolation("invariants:public_observation", problems)


@dataclass(frozen=True)
class CaptureParameters:
    """The seven D06 parameters, read from the domain configuration, never hard-coded."""

    contact_gap_min_m: float
    contact_gap_max_m: float
    capture_speed_max_mps: float
    relative_speed_max_mps: float
    orientation_tolerance_rad: float
    dwell_time_s: float
    geometry_tolerance_m: float
    frozen: bool

    @staticmethod
    def from_domain(domain: dict | None = None) -> CaptureParameters:
        domain = domain or load_domain()
        predicate = domain["capture_predicate"]
        values = {k: v["value"] for k, v in predicate["parameters"].items()}
        return CaptureParameters(frozen=predicate["status"] == "FROZEN", **values)

    def consistency_problems(self, domain: dict | None = None) -> list[str]:
        """The parameter set must satisfy its own derived properties.

        These are not style checks. Each one corresponds to a way the predicate could be
        made to accept something it must never accept.
        """
        domain = domain or load_domain()
        problems: list[str] = []
        min_gap = domain["vehicle"]["min_gap_m"]
        step = domain["timing"]["physical_step_s"]
        decision = domain["timing"]["decision_interval_s"]

        if not 0 < self.geometry_tolerance_m < self.contact_gap_min_m:
            problems.append("require 0 < geometry_tolerance_m < contact_gap_min_m")
        if not self.contact_gap_min_m < self.contact_gap_max_m:
            problems.append("require contact_gap_min_m < contact_gap_max_m")
        if not self.contact_gap_max_m < min_gap:
            problems.append(
                f"require contact_gap_max_m < min_gap_m ({min_gap}), otherwise ordinary "
                "car-following satisfies the separation condition"
            )

        # A-45 found the three checks below missing, and their absence made D06
        # unsatisfiable while every check above passed: the band was excluded from
        # ordinary following by making it unreachable by ANY safe manoeuvre.
        by_class = domain["vehicle"].get("min_gap_m_by_class", {})
        pursuer_gap = by_class.get("pursuer", min_gap)
        evader_gap = by_class.get("evader")
        if not self.contact_gap_max_m < pursuer_gap:
            problems.append(
                f"require contact_gap_max_m < pursuer min_gap ({pursuer_gap}), otherwise a "
                "pursuer merely trailing the evader sits inside the capture band"
            )
        if evader_gap is None:
            problems.append(
                "require an evader min_gap: without one the capture band is unreachable under "
                "safe following, because every vehicle stops at the pursuer min_gap"
            )
        elif not self.contact_gap_min_m <= evader_gap <= self.contact_gap_max_m:
            problems.append(
                f"require contact_gap_min_m <= evader min_gap ({evader_gap}) <= "
                "contact_gap_max_m, otherwise an evader brought to a stop behind a pursuer "
                "cannot come to rest inside the capture band with safety checks on"
            )
        factor = domain.get("simulator", {}).get("collision_mingap_factor")
        if factor != 0:
            problems.append(
                f"require simulator collision_mingap_factor == 0 (found {factor!r}): under "
                "SUMO's default every bumper gap below min_gap is a collision, which puts "
                "the whole capture band inside the collision zone"
            )
        if self.contact_gap_min_m < 10 * self.geometry_tolerance_m:
            problems.append(
                "require contact_gap_min_m >= 10 * geometry_tolerance_m so that a "
                "separation at the bound cannot be an overlap within tolerance"
            )
        if self.dwell_time_s < 2 * decision:
            problems.append("require dwell_time_s >= 2 * decision_interval_s")
        if abs(self.dwell_time_s / step - round(self.dwell_time_s / step)) > 1e-9:
            problems.append("require dwell_time_s to be an integer number of physical steps")
        band = self.contact_gap_max_m - self.contact_gap_min_m
        if self.relative_speed_max_mps <= 0:
            problems.append("require relative_speed_max_mps > 0")
        elif band / self.relative_speed_max_mps >= self.dwell_time_s:
            problems.append(
                "require band_width / relative_speed_max_mps < dwell_time_s, otherwise a "
                "monotone fly-through of the separation band can satisfy the dwell"
            )
        if not 0 < self.orientation_tolerance_rad < 1.5707963267948966:
            problems.append("require 0 < orientation_tolerance_rad < pi/2")
        if self.capture_speed_max_mps <= 0:
            problems.append("require capture_speed_max_mps > 0")
        return problems


def simulator_arguments(domain: dict | None = None) -> list[str]:
    """SUMO arguments the domain contract freezes. Every native run must pass these.

    Taken from the contract rather than written into a runner, so the collision semantics
    a run used are the ones the contract declares - and a runner that omits them is
    detectable by comparing its start command against this list.
    """
    domain = domain or load_domain()
    return list(domain["simulator"]["sumo_argument"])


def min_gap_for(vehicle_class: str, domain: dict | None = None) -> float:
    """Car-following distance for a vehicle class (A-46). Falls back to `min_gap_m`."""
    domain = domain or load_domain()
    vehicle = domain["vehicle"]
    return float(vehicle.get("min_gap_m_by_class", {}).get(vehicle_class, vehicle["min_gap_m"]))
