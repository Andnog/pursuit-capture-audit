"""Shared test support: path setup and fixture/config loading.

The tests load the FROZEN fixture and compare the implementation against it. They do not
recompute the expected values from the implementation.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

TOLERANCE = 1e-9


def load_config() -> dict:
    with open(os.path.join(ROOT, "configs", "finite_examples_v1.json"), encoding="utf-8") as handle:
        return json.load(handle)


def load_fixture() -> dict:
    with open(
        os.path.join(ROOT, "tests", "fixtures", "finite_cases_v1.json"), encoding="utf-8"
    ) as handle:
        return json.load(handle)


def case(config: dict, case_id: str) -> dict:
    for item in config["representation_cases"]:
        if item["case_id"] == case_id:
            return item
    raise KeyError(case_id)


def assistance_case(config: dict, case_id: str) -> dict:
    for item in config["assistance_cases"]:
        if item["case_id"] == case_id:
            return item
    raise KeyError(case_id)


def as_intervals(pairs) -> tuple:
    return tuple((float(a), float(b)) for a, b in pairs)


def intervals_equal(left, right) -> bool:
    left, right = tuple(left), tuple(right)
    if len(left) != len(right):
        return False
    return all(
        abs(a[0] - b[0]) <= TOLERANCE and abs(a[1] - b[1]) <= TOLERANCE
        for a, b in zip(left, right, strict=True)
    )


def build_opportunity(config: dict, case_id: str, direction_override: str | None = None):
    """Build the joint-compatibility result for one representation case from the CONFIG."""
    from joint_interception.opportunities.compatibility import (
        assess_joint_compatibility,
        assess_pairwise_compatibility,
    )
    from joint_interception.opportunities.reachability import ArrivalSet
    from joint_interception.opportunities.types import Direction

    spec = case(config, case_id)
    geometry = config["lane_geometry"]
    lane_lengths = {name: data["usable_length_m"] for name, data in spec["lanes"].items()}
    arrival_sets = [
        ArrivalSet.build(
            participant,
            data["intervals"],
            Direction(direction_override or data["direction"]),
        )
        for participant, data in spec["arrival_sets"].items()
    ]
    common = dict(
        participants=spec["participants"],
        arrival_sets=arrival_sets,
        stations=spec["stations"],
        lane_lengths=lane_lengths,
        dwell_required_s=spec["dwell_required_s"],
        body_length_m=geometry["body_length_m"],
        min_gap_m=geometry["min_gap_m"],
        conflicting_pairs=spec.get("declared_movement_conflicts", []),
        unknown_pairs=spec.get("declared_movement_unknown_pairs", []),
    )
    opportunity = assess_joint_compatibility(
        opportunity_id=case_id, corridor=list(spec["lanes"])[0], **common
    )
    pairwise = assess_pairwise_compatibility(**common)
    return opportunity, pairwise
