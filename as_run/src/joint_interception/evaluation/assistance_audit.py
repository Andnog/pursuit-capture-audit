"""Assistance accounting over finite outcome tables.

Implements METHOD_SPEC_EN.md section 9. The construction is adopted, with attribution,
from the historical assistance specification
`urban_capture_cooperation_v3/research/20260919_novelty_audit_01/METHOD_SPEC_EN.md`
sections 4 to 6. It is a MEASUREMENT component of this project, not a contribution.

The bounds computed here are LOGICAL bounds arising from missing outcomes. They are not
confidence intervals and must never be reported as such.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum

UNKNOWN = "UNKNOWN"

Bounds = tuple[float, float]


class Admission(str, Enum):
    """Trivalent admission of an intervention alternative."""

    SUPPORTED_ADMISSIBLE = "SUPPORTED_ADMISSIBLE"
    SUPPORTED_INADMISSIBLE = "SUPPORTED_INADMISSIBLE"
    UNRESOLVED = "UNRESOLVED"


class AssistanceLabel(str, Enum):
    POSITIVE_ACROSS_FAMILY = "POSITIVE_ACROSS_FAMILY"
    BASELINE_DEPENDENT = "BASELINE_DEPENDENT"
    NO_POSITIVE_EFFECT_DEMONSTRATED = "NO_POSITIVE_EFFECT_DEMONSTRATED"
    HARMFUL_ACROSS_FAMILY = "HARMFUL_ACROSS_FAMILY"
    INSUFFICIENT_SUPPORT = "INSUFFICIENT_SUPPORT"


def outcome_bounds(outcome) -> Bounds:
    """Bounds for a binary outcome. An unknown outcome is `[0, 1]`, never an assumed 0."""
    if outcome == UNKNOWN or outcome is None:
        return (0.0, 1.0)
    value = float(outcome)
    if value not in (0.0, 1.0):
        raise ValueError(f"binary outcome expected, got {outcome!r}")
    return (value, value)


def contrast_bounds(factual, intervened) -> Bounds:
    """`d = Y_factual - Y_intervened` with bounds `[l_f - u_b, u_f - l_b]`."""
    low_f, high_f = outcome_bounds(factual)
    low_b, high_b = outcome_bounds(intervened)
    return (low_f - high_b, high_f - low_b)


@dataclass(frozen=True)
class Alternative:
    """One declared member of the intervention family."""

    alternative: str
    admission: Admission
    outcome: object  # 0, 1 or UNKNOWN


@dataclass
class AssistanceResult:
    helper: str
    per_alternative_bounds: dict[str, Bounds]
    envelope: Bounds
    label: AssistanceLabel
    incomplete_family: bool
    complete_family_conclusion_permitted: bool
    resolved_members: list[str] = field(default_factory=list)
    excluded_members: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def audit_assistance(
    helper: str, factual_outcome, family: Sequence[Alternative]
) -> AssistanceResult:
    """Account for the assistance of one helper over a declared intervention family.

    Only members whose admission is `SUPPORTED_ADMISSIBLE` enter the label. Members with
    unresolved admission are EXCLUDED but remain visible and set `incomplete_family`; they
    are never silently replaced by a different baseline.
    """
    per_alternative: dict[str, Bounds] = {}
    resolved: list[Alternative] = []
    excluded: list[str] = []
    reasons: list[str] = []

    for member in family:
        if member.admission is Admission.SUPPORTED_ADMISSIBLE:
            resolved.append(member)
            per_alternative[member.alternative] = contrast_bounds(factual_outcome, member.outcome)
        else:
            excluded.append(member.alternative)
            reasons.append(f"excluded:{member.alternative}:{member.admission.value}")

    incomplete_family = any(m.admission is Admission.UNRESOLVED for m in family)

    if not resolved:
        return AssistanceResult(
            helper,
            per_alternative,
            (0.0, 0.0),
            AssistanceLabel.INSUFFICIENT_SUPPORT,
            incomplete_family,
            False,
            [],
            excluded,
            reasons + ["no_resolved_admissible_member"],
        )

    lows = [per_alternative[m.alternative][0] for m in resolved]
    highs = [per_alternative[m.alternative][1] for m in resolved]
    envelope = (min(lows), max(highs))

    if any(m.outcome == UNKNOWN or m.outcome is None for m in resolved):
        label = AssistanceLabel.INSUFFICIENT_SUPPORT
        reasons.append("resolved_member_with_unknown_outcome")
    else:
        # Every resolved outcome is known, so each contrast is a point.
        points = [per_alternative[m.alternative][0] for m in resolved]
        if all(p > 0 for p in points):
            label = AssistanceLabel.POSITIVE_ACROSS_FAMILY
        elif all(p < 0 for p in points):
            label = AssistanceLabel.HARMFUL_ACROSS_FAMILY
        elif all(p == 0 for p in points):
            label = AssistanceLabel.NO_POSITIVE_EFFECT_DEMONSTRATED
            reasons.append("envelope_includes_zero_not_proof_of_no_coordination")
        else:
            label = AssistanceLabel.BASELINE_DEPENDENT

    permitted = (not incomplete_family) and label is not AssistanceLabel.INSUFFICIENT_SUPPORT
    if incomplete_family:
        reasons.append("incomplete_family_no_complete_family_conclusion")

    return AssistanceResult(
        helper,
        per_alternative,
        envelope,
        label,
        incomplete_family,
        permitted,
        [m.alternative for m in resolved],
        excluded,
        reasons,
    )


def effects_are_additive(individual_effects: Sequence[float], coalition_effect: float) -> bool:
    """Whether individual leave-one-out effects sum to the coalition effect.

    Provided so that non-additivity under redundancy is MEASURED rather than assumed.
    Two interchangeable helpers can each have a null individual effect while the pair
    matters; that is not evidence of absent coordination.
    """
    return abs(sum(individual_effects) - coalition_effect) <= 1e-9


def endpoint_bounds(supported: int, unresolved: int, executed: int) -> Bounds:
    """Logical bounds `[S/N, (S+U)/N]` for the binary endpoint over executed cases.

    These are missing-outcome bounds, not confidence intervals.
    """
    if executed <= 0:
        raise ValueError("executed sample size must be positive")
    return (supported / executed, (supported + unresolved) / executed)
