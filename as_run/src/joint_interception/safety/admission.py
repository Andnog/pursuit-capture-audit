"""Safety admission: the common interface every arm passes through.

Trivalent by design (METHOD_SPEC_EN.md section 5 and the historical assistance
specification): an action is `SUPPORTED` admissible, `REJECTED` inadmissible, or
`UNKNOWN`. **Unresolved admission is never permission to execute.**

What this module is NOT: a formally synthesised shield. It is an empirical local guard.
The master plan states that a local guard does not establish a verified shield, and the
historical obligation O22 remains open precisely because the guard's directional and
timing proofs were never completed.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.geometry import Rectangle, body_separation_m, rectangles_overlap
from ..opportunities.types import Verdict


@dataclass(frozen=True)
class AdmissionResult:
    verdict: Verdict
    reason: str
    detail: dict

    @property
    def permits_execution(self) -> bool:
        """Only a SUPPORTED verdict permits execution. UNKNOWN does not."""
        return self.verdict is Verdict.SUPPORTED


def stopping_distance_m(speed_mps: float, deceleration_mps2: float) -> float:
    """Ordinary-braking stopping distance.

    Emergency braking is deliberately not modelled here: the contract treats it as a
    safety-failure indicator rather than an available manoeuvre, so admitting an action
    that would need it must not be possible.
    """
    if deceleration_mps2 <= 0:
        raise ValueError("deceleration must be positive")
    if speed_mps < 0:
        raise ValueError("speed must be non-negative")
    return (speed_mps * speed_mps) / (2.0 * deceleration_mps2)


def admit_immediate_step(
    actor: Rectangle,
    actor_speed_mps: float,
    others: dict[str, Rectangle],
    step_s: float,
    geometry_tolerance_m: float,
    unresolved: frozenset[str] = frozenset(),
) -> AdmissionResult:
    """Admit or refuse the actor's next physical step against the current bodies.

    This is a ONE-STEP check. It says nothing about the remainder of a manoeuvre; the
    caller must not promote its verdict to a statement about a trajectory. Finite case F5
    exists to keep that distinction enforced.
    """
    if any(rectangles_overlap(actor, body) for body in others.values()):
        return AdmissionResult(
            Verdict.REJECTED, "body_overlap_at_current_state", {"step_s": step_s}
        )

    closest_id, closest_gap = None, float("inf")
    for other_id, body in others.items():
        gap = body_separation_m(actor, body)
        if gap < closest_gap:
            closest_id, closest_gap = other_id, gap

    if closest_id is not None and closest_id in unresolved:
        return AdmissionResult(
            Verdict.UNKNOWN,
            "closest_neighbour_state_unresolved",
            {"neighbour": closest_id, "gap_m": closest_gap},
        )

    reachable = actor_speed_mps * step_s
    if closest_gap - reachable <= geometry_tolerance_m:
        return AdmissionResult(
            Verdict.REJECTED,
            "step_could_close_gap_within_tolerance",
            {"neighbour": closest_id, "gap_m": closest_gap, "reachable_m": reachable},
        )

    if unresolved:
        return AdmissionResult(
            Verdict.UNKNOWN,
            "unresolved_neighbours_present",
            {"unresolved": sorted(unresolved), "closest_gap_m": closest_gap},
        )

    return AdmissionResult(
        Verdict.SUPPORTED,
        "step_clear_of_all_bodies",
        {"neighbour": closest_id, "gap_m": closest_gap, "reachable_m": reachable},
    )


def admit_sequence(step_verdicts: list[Verdict]) -> AdmissionResult:
    """Admission over a sequence of steps.

    The conjunction is Kleene's: one REJECTED step refuses the sequence, and an UNKNOWN
    step anywhere prevents the sequence from being SUPPORTED. An empty sequence is
    UNKNOWN, because nothing was checked.
    """
    from ..opportunities.types import verdict_and

    verdict = verdict_and(step_verdicts)
    if verdict is Verdict.SUPPORTED:
        reason = "all_steps_supported"
    elif verdict is Verdict.REJECTED:
        reason = "at_least_one_step_rejected"
    elif not step_verdicts:
        reason = "empty_sequence_nothing_checked"
    else:
        reason = "at_least_one_step_unresolved"
    return AdmissionResult(verdict, reason, {"steps": len(step_verdicts)})
