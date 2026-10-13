"""Commitment memory and the selection rule.

Implements METHOD_SPEC_EN.md section 8. The `J0` and `J1` arms are the SAME code path with
different frozen constants; the degeneracy is asserted by a test so the two arms cannot
diverge for unintended reasons.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

from ..opportunities.reachability import TOLERANCE
from ..opportunities.types import Verdict


@dataclass(frozen=True)
class CommitmentParameters:
    """Frozen selection constants.

    `J0` is `CommitmentParameters(max_commit_duration=1, switch_margin=0.0,
    unknown_tolerance=0)`. `switch_margin` is hysteresis and is the entire mechanical
    difference between the arms.
    """

    max_commit_duration: int
    switch_margin: float
    unknown_tolerance: int


@dataclass(frozen=True)
class CommitmentMemory:
    """Selector memory `m_t`."""

    committed_opportunity_id: str | None = None
    committed_at: int | None = None
    last_verdict: Verdict | None = None
    consecutive_unknown: int = 0
    switch_count: int = 0


@dataclass(frozen=True)
class Decision:
    """One decision: which opportunity, and what happened to the commitment."""

    t: int
    selected_opportunity_id: str | None
    decision: str  # CONTINUE | SWITCH | ABANDON | FALLBACK
    reason: str
    memory: CommitmentMemory


def _best_supported(scores: Mapping[str, float], verdicts: Mapping[str, Verdict]) -> str | None:
    """Argmax over SUPPORTED candidates, with a frozen deterministic tie-break.

    Ties are broken by ascending candidate identifier so the rule is reproducible.
    `UNKNOWN` candidates are never selectable: unresolved admission is not permission.
    """
    supported = [c for c, v in verdicts.items() if v is Verdict.SUPPORTED]
    if not supported:
        return None
    return min(supported, key=lambda c: (-scores[c], c))


def select_action(
    t: int,
    scores: Mapping[str, float],
    verdicts: Mapping[str, Verdict],
    memory: CommitmentMemory,
    params: CommitmentParameters,
) -> Decision:
    """One decision step of the selection rule.

    Order of tests matters and follows the specification exactly: rejection, then expiry,
    then unknown tolerance, then the hysteresis switch test.
    """
    committed = memory.committed_opportunity_id

    if committed is None or committed not in verdicts:
        choice = _best_supported(scores, verdicts)
        if choice is None:
            return Decision(t, None, "FALLBACK", "no_supported_candidate", replace(memory))
        new_memory = CommitmentMemory(
            committed_opportunity_id=choice,
            committed_at=t,
            last_verdict=Verdict.SUPPORTED,
            consecutive_unknown=0,
            switch_count=memory.switch_count,
        )
        reason = "new_commitment" if committed is None else "stale_commitment_replaced"
        return Decision(t, choice, "CONTINUE", reason, new_memory)

    current = verdicts[committed]

    if current is Verdict.REJECTED:
        return Decision(
            t,
            None,
            "ABANDON",
            "committed_opportunity_rejected",
            CommitmentMemory(switch_count=memory.switch_count),
        )

    age = t - (memory.committed_at if memory.committed_at is not None else t)
    if age >= params.max_commit_duration:
        return Decision(
            t,
            None,
            "ABANDON",
            "max_commit_duration_reached",
            CommitmentMemory(switch_count=memory.switch_count),
        )

    if current is Verdict.UNKNOWN:
        consecutive = memory.consecutive_unknown + 1
        if consecutive > params.unknown_tolerance:
            return Decision(
                t,
                None,
                "ABANDON",
                "unknown_tolerance_exceeded",
                CommitmentMemory(switch_count=memory.switch_count),
            )
        return Decision(
            t,
            committed,
            "CONTINUE",
            "unknown_within_tolerance",
            replace(memory, last_verdict=current, consecutive_unknown=consecutive),
        )

    best = _best_supported(scores, verdicts)
    # Strictly exceed the margin, with a tolerance so that a score exactly on the boundary
    # does not switch or hold according to floating-point representation error. Without it,
    # 0.68 > 0.58 + 0.10 evaluates to True in binary floating point and the arm's behaviour
    # at the boundary is not reproducible.
    if (
        best is not None
        and best != committed
        and scores[best] > scores[committed] + params.switch_margin + TOLERANCE
    ):
        return Decision(
            t,
            best,
            "SWITCH",
            "alternative_exceeds_switch_margin",
            CommitmentMemory(
                committed_opportunity_id=best,
                committed_at=t,
                last_verdict=Verdict.SUPPORTED,
                consecutive_unknown=0,
                switch_count=memory.switch_count + 1,
            ),
        )
    return Decision(
        t,
        committed,
        "CONTINUE",
        "held_within_switch_margin",
        replace(memory, last_verdict=Verdict.SUPPORTED, consecutive_unknown=0),
    )


def run_decision_sequence(steps, params: CommitmentParameters) -> list[Decision]:
    """Run the selection rule over a sequence of `(t, scores, verdicts)` steps.

    After an `ABANDON` the memory is empty, so the next step re-selects. This is what makes
    the degenerate `J0` constants reproduce memoryless re-selection.
    """
    memory = CommitmentMemory()
    out: list[Decision] = []
    for t, scores, verdicts in steps:
        decision = select_action(t, scores, verdicts, memory, params)
        if decision.decision == "ABANDON":
            # Re-select immediately within the same decision interval.
            decision = select_action(t, scores, verdicts, decision.memory, params)
        memory = decision.memory
        out.append(decision)
    return out
