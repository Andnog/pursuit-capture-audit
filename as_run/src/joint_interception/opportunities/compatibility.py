"""Joint and pairwise compatibility predicates.

Implements METHOD_SPEC_EN.md section 5. Both predicates are provided so that the
unsoundness of the pairwise relaxation can be demonstrated rather than asserted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import combinations

from .reachability import (
    TOLERANCE,
    ArrivalSet,
    all_over,
    all_under,
    intersect_all,
    max_contiguous,
)
from .types import Opportunity, Verdict


def lane_capacity_required_m(count: int, body_length_m: float, min_gap_m: float) -> float:
    """Length needed to place `count` bodies in one lane with the minimum gap between them.

    `count * body + (count - 1) * gap`. Mirrors the station-separation arithmetic whose
    violation produced the native collision recorded under obligation O22.
    """
    if count <= 0:
        return 0.0
    return count * body_length_m + (count - 1) * min_gap_m


def assess_temporal(
    arrival_sets: Sequence[ArrivalSet], dwell_required_s: float
) -> tuple[Verdict, tuple, float, str]:
    """Temporal component of the joint compatibility predicate.

    Returns (verdict, joint_window, max_contiguous, reason_code).

    Rule A: `SUPPORTED` requires every participating set to be an under-approximation.
    Rule B: `REJECTED` requires every participating set to be an over-approximation.
    The rules are not symmetric; anything else is `UNKNOWN`.
    """
    window = intersect_all([a.intervals for a in arrival_sets])
    longest = max_contiguous(window)
    directions = [a.direction for a in arrival_sets]

    if not window:
        if all_over(directions):
            return Verdict.REJECTED, window, longest, "empty_intersection_over_approximation"
        return (
            Verdict.UNKNOWN,
            window,
            longest,
            "empty_intersection_but_direction_cannot_certify_non_existence",
        )

    if longest + TOLERANCE < dwell_required_s:
        if all_over(directions):
            return (
                Verdict.REJECTED,
                window,
                longest,
                "max_contiguous_below_dwell_over_approximation",
            )
        return Verdict.UNKNOWN, window, longest, "max_contiguous_below_dwell_direction_insufficient"

    if all_under(directions):
        return Verdict.SUPPORTED, window, longest, "dwell_satisfied_under_approximation"
    return (
        Verdict.UNKNOWN,
        window,
        longest,
        "dwell_satisfied_but_direction_cannot_certify_existence",
    )


def assess_occupancy(
    participants: Sequence[str],
    stations: Mapping[str, str],
    lane_lengths: Mapping[str, float],
    body_length_m: float,
    min_gap_m: float,
) -> tuple[Verdict, str, dict]:
    """Occupancy component: can the participating bodies coexist at their stations?

    Evaluated over the COMPLETE set of participants assigned to each lane. This is the
    component that a pairwise relaxation cannot reproduce.
    """
    per_lane: dict[str, list[str]] = {}
    for participant in participants:
        lane = stations.get(participant)
        if lane is None:
            return Verdict.UNKNOWN, "station_not_declared", {"participant": participant}
        per_lane.setdefault(lane, []).append(participant)

    detail: dict = {"per_lane": {}}
    for lane, occupants in sorted(per_lane.items()):
        available = lane_lengths.get(lane)
        if available is None:
            return Verdict.UNKNOWN, "lane_length_not_declared", {"lane": lane}
        required = lane_capacity_required_m(len(occupants), body_length_m, min_gap_m)
        detail["per_lane"][lane] = {
            "occupants": len(occupants),
            "required_m": required,
            "available_m": available,
        }
        if required > available + TOLERANCE:
            detail.update({"lane": lane, "required_m": required, "available_m": available})
            return Verdict.REJECTED, "lane_capacity_exceeded", detail
    return Verdict.SUPPORTED, "lane_capacity_satisfied", detail


def assess_movement(
    participants: Sequence[str],
    conflicting_pairs: Sequence[Sequence[str]],
    unknown_pairs: Sequence[Sequence[str]],
) -> tuple[Verdict, str]:
    """Movement component, in its finite abstraction.

    Declared conflicting pairs reject; declared unknown pairs yield `UNKNOWN`. The real
    swept-body computation against lane geometry is W2/W3 work and is NOT implemented.
    """
    members = set(participants)

    def involves(pair: Sequence[str]) -> bool:
        return set(pair) <= members

    if any(involves(p) for p in conflicting_pairs):
        return Verdict.REJECTED, "declared_movement_conflict"
    if any(involves(p) for p in unknown_pairs):
        return Verdict.UNKNOWN, "declared_unknown_movement_interaction"
    return Verdict.SUPPORTED, "no_declared_movement_conflict"


def assess_joint_compatibility(
    opportunity_id: str,
    corridor: str,
    participants: Sequence[str],
    arrival_sets: Sequence[ArrivalSet],
    stations: Mapping[str, str],
    lane_lengths: Mapping[str, float],
    dwell_required_s: float,
    body_length_m: float,
    min_gap_m: float,
    conflicting_pairs: Sequence[Sequence[str]] = (),
    unknown_pairs: Sequence[Sequence[str]] = (),
    evader_branch: str | None = None,
    coverage: float = 1.0,
) -> Opportunity:
    """`C(q, o_t, model)` over the COMPLETE candidate combination.

    This is the joint predicate. It is sound as a certificate of team feasibility in a way
    that `assess_pairwise_compatibility` is not.
    """
    temporal, window, longest, temporal_reason = assess_temporal(arrival_sets, dwell_required_s)
    occupancy, occupancy_reason, occupancy_detail = assess_occupancy(
        participants, stations, lane_lengths, body_length_m, min_gap_m
    )
    movement, movement_reason = assess_movement(participants, conflicting_pairs, unknown_pairs)

    opportunity = Opportunity(
        opportunity_id=opportunity_id,
        corridor=corridor,
        participants=tuple(participants),
        temporal_verdict=temporal,
        occupancy_verdict=occupancy,
        movement_verdict=movement,
        joint_window=window,
        max_contiguous=longest,
        margin=(longest - dwell_required_s) if temporal is Verdict.SUPPORTED else None,
        evader_branch=evader_branch,
        coverage=coverage,
    )
    opportunity.add_reason(temporal_reason, "temporal")
    opportunity.add_reason(occupancy_reason, str(occupancy_detail))
    opportunity.add_reason(movement_reason, "movement")
    return opportunity


def assess_pairwise_compatibility(
    participants: Sequence[str],
    arrival_sets: Sequence[ArrivalSet],
    stations: Mapping[str, str],
    lane_lengths: Mapping[str, float],
    dwell_required_s: float,
    body_length_m: float,
    min_gap_m: float,
    conflicting_pairs: Sequence[Sequence[str]] = (),
    unknown_pairs: Sequence[Sequence[str]] = (),
) -> Verdict:
    """The pairwise relaxation `C_pair(q)`: the conjunction over all unordered pairs.

    PROVIDED FOR COMPARISON ONLY. It is NOT a certificate of team feasibility: a set of
    plans can be pairwise compatible and jointly infeasible. See METHOD_SPEC_EN.md
    section 5.2 and finite case F1. It is also asymptotically more expensive than the
    joint predicate, so it is not a performance optimisation.
    """
    by_participant = {a.participant: a for a in arrival_sets}
    verdicts = []
    for left, right in combinations(participants, 2):
        pair = (left, right)
        pair_sets = [by_participant[left], by_participant[right]]
        temporal, _, _, _ = assess_temporal(pair_sets, dwell_required_s)
        occupancy, _, _ = assess_occupancy(pair, stations, lane_lengths, body_length_m, min_gap_m)
        movement, _ = assess_movement(pair, conflicting_pairs, unknown_pairs)
        from .types import verdict_and

        verdicts.append(verdict_and([temporal, occupancy, movement]))
    from .types import verdict_and

    return verdict_and(verdicts)
