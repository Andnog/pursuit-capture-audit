"""Verdicts and the Opportunity record.

Implements the three-valued verdict algebra of METHOD_SPEC_EN.md section 4.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    """A three-valued verdict. `UNKNOWN` is a first-class outcome, never a default."""

    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class Direction(str, Enum):
    """Approximation direction of an arrival set (METHOD_SPEC_EN.md section 2.3)."""

    UNDER = "UNDER"
    OVER = "OVER"
    PREDICTION = "PREDICTION"


def verdict_and(verdicts: Iterable[Verdict]) -> Verdict:
    """Kleene strong conjunction.

    `REJECTED` dominates: a proof of impossibility is not weakened by ignorance elsewhere
    (property AND-1). `UNKNOWN` never becomes `SUPPORTED` by aggregation (property AND-2).

    An empty conjunction is `UNKNOWN`, not `SUPPORTED`: nothing was checked, so nothing is
    supported.
    """
    seen = list(verdicts)
    if not seen:
        return Verdict.UNKNOWN
    if any(v is Verdict.REJECTED for v in seen):
        return Verdict.REJECTED
    if any(v is Verdict.UNKNOWN for v in seen):
        return Verdict.UNKNOWN
    return Verdict.SUPPORTED


def verdict_or(verdicts: Iterable[Verdict]) -> Verdict:
    """Kleene strong disjunction, the dual of `verdict_and`.

    Used only for `some declared branch admits the opportunity`. A claim over ALL branches
    must use `verdict_and` together with a coverage of 1.0.
    """
    seen = list(verdicts)
    if not seen:
        return Verdict.UNKNOWN
    if any(v is Verdict.SUPPORTED for v in seen):
        return Verdict.SUPPORTED
    if any(v is Verdict.UNKNOWN for v in seen):
        return Verdict.UNKNOWN
    return Verdict.REJECTED


@dataclass(frozen=True)
class Reason:
    """A machine-readable justification. A verdict without one is invalid."""

    code: str
    detail: str = ""


@dataclass
class Opportunity:
    """A candidate joint interception opportunity.

    Field names follow METHOD_SPEC_EN.md section 3.
    """

    opportunity_id: str
    corridor: str
    participants: Sequence[str]
    temporal_verdict: Verdict = Verdict.UNKNOWN
    occupancy_verdict: Verdict = Verdict.UNKNOWN
    movement_verdict: Verdict = Verdict.UNKNOWN
    joint_window: tuple = ()
    max_contiguous: float = 0.0
    margin: float | None = None
    evader_branch: str | None = None
    coverage: float = 0.0
    reasons: list[Reason] = field(default_factory=list)
    model_version: str = "finite_v1"
    contract_version: str = "unresolved_D06_D07"

    @property
    def verdict(self) -> Verdict:
        """Overall verdict: the conjunction of the three components."""
        return verdict_and([self.temporal_verdict, self.occupancy_verdict, self.movement_verdict])

    def add_reason(self, code: str, detail: str = "") -> None:
        self.reasons.append(Reason(code, detail))
