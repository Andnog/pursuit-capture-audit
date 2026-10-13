"""Candidate generation with accounted pruning.

Master plan section 6: every stage must log how many candidates it removed and why. The
reason is specific, not bureaucratic. The historical O26 diagnostic recorded 6548
stop/stationary-lateral candidate occurrences of which NONE passed the selector's screen,
and could not distinguish "no physically reachable complementary candidate existed" from
"the controller never positioned agents to make one available". Pruning that is not counted
makes those two indistinguishable.

The generator is itself a source of coordination. Enumerating combinations and filtering
for joint compatibility supplies team structure that a learner above it does not have to
discover. That is why `BASELINE_SPEC_EN.md` requires a common candidate set and a
deterministic joint reference, and why this module reports the counts needed to show what
the filter removed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from .compatibility import assess_joint_compatibility, assess_pairwise_compatibility
from .reachability import ArrivalSet
from .types import Opportunity, Verdict


@dataclass
class GenerationAccount:
    """What the generator enumerated, removed and kept. Must reconcile."""

    enumerated: int = 0
    pruned: dict[str, int] = field(default_factory=dict)
    truncated: int = 0
    deduplicated: int = 0
    kept: int = 0
    pruned_keys: list[str] = field(default_factory=list)

    def prune(self, reason: str, key: str) -> None:
        self.pruned[reason] = self.pruned.get(reason, 0) + 1
        self.pruned_keys.append(f"{reason}:{key}")

    @property
    def total_pruned(self) -> int:
        return sum(self.pruned.values())

    def reconciles(self) -> bool:
        """Enumerated must equal kept plus everything removed, with nothing unaccounted."""
        return self.enumerated == self.kept + self.total_pruned + self.truncated + self.deduplicated

    def as_record(self) -> dict:
        return {
            "enumerated": self.enumerated,
            "pruned": dict(sorted(self.pruned.items())),
            "total_pruned": self.total_pruned,
            "truncated": self.truncated,
            "deduplicated": self.deduplicated,
            "kept": self.kept,
            "reconciles": self.reconciles(),
        }


@dataclass(frozen=True)
class GeneratorLimits:
    """Caps are part of the method, not implementation details.

    Combination enumeration is `O(C(n, m) * p^m)`. With five pursuers and an unbounded plan
    count it does not terminate usefully, so the caps and their effect on coverage are
    declared and logged.
    """

    max_participants: int = 3
    min_participants: int = 2
    max_candidates: int = 64


def candidate_key(corridor: str, participants: tuple[str, ...]) -> str:
    return f"{corridor}|{','.join(sorted(participants))}"


def build_candidates(
    corridors: dict[str, dict],
    arrival_sets: dict[str, dict[str, ArrivalSet]],
    stations: dict[str, dict[str, str]],
    lane_lengths: dict[str, float],
    dwell_required_s: float,
    body_length_m: float,
    min_gap_m: float,
    limits: GeneratorLimits | None = None,
    conflicting_pairs: tuple[tuple[str, str], ...] = (),
    unknown_pairs: tuple[tuple[str, str], ...] = (),
    evader_branch: str | None = None,
    coverage: float = 1.0,
    use_pairwise: bool = False,
) -> tuple[list[Opportunity], GenerationAccount]:
    """Enumerate, prune and score candidate joint opportunities.

    `use_pairwise=True` selects the pairwise RELAXATION, which is unsound as a certificate
    of team feasibility (METHOD_SPEC_EN.md section 5.2, finite case F1). It is available so
    the two can be compared, and every opportunity it produces is labelled as an
    approximation.
    """
    limits = limits or GeneratorLimits()
    account = GenerationAccount()
    seen: set[str] = set()
    scored: list[tuple[float, str, Opportunity]] = []

    for corridor, corridor_spec in sorted(corridors.items()):
        members = sorted(corridor_spec["participants"])
        for size in range(limits.min_participants, limits.max_participants + 1):
            for participants in combinations(members, size):
                account.enumerated += 1
                key = candidate_key(corridor, participants)

                if key in seen:
                    account.deduplicated += 1
                    continue
                seen.add(key)

                missing = [p for p in participants if p not in arrival_sets.get(corridor, {})]
                if missing:
                    account.prune("no_arrival_set_for_participant", key)
                    continue

                sets = [arrival_sets[corridor][p] for p in participants]
                opportunity = assess_joint_compatibility(
                    opportunity_id=key,
                    corridor=corridor,
                    participants=participants,
                    arrival_sets=sets,
                    stations=stations[corridor],
                    lane_lengths=lane_lengths,
                    dwell_required_s=dwell_required_s,
                    body_length_m=body_length_m,
                    min_gap_m=min_gap_m,
                    conflicting_pairs=conflicting_pairs,
                    unknown_pairs=unknown_pairs,
                    evader_branch=evader_branch,
                    coverage=coverage,
                )

                if use_pairwise:
                    pairwise = assess_pairwise_compatibility(
                        participants=participants,
                        arrival_sets=sets,
                        stations=stations[corridor],
                        lane_lengths=lane_lengths,
                        dwell_required_s=dwell_required_s,
                        body_length_m=body_length_m,
                        min_gap_m=min_gap_m,
                        conflicting_pairs=conflicting_pairs,
                        unknown_pairs=unknown_pairs,
                    )
                    opportunity.add_reason(
                        "pairwise_approximation_used",
                        f"pairwise={pairwise.value}; NOT a team-feasibility certificate",
                    )

                if opportunity.verdict is Verdict.REJECTED:
                    # A rejected candidate is COUNTED, not forgotten. Distinguishing an
                    # absent opportunity from a rejected one is the whole point.
                    account.prune("rejected_by_compatibility", key)
                    continue

                score = opportunity.max_contiguous - dwell_required_s
                scored.append((score, key, opportunity))

    # Frozen ordering: score descending, then identifier ascending. Deterministic.
    scored.sort(key=lambda item: (-item[0], item[1]))
    if len(scored) > limits.max_candidates:
        account.truncated = len(scored) - limits.max_candidates
        for _, key, _ in scored[limits.max_candidates :]:
            account.pruned_keys.append(f"truncated:{key}")
        scored = scored[: limits.max_candidates]

    kept = [opportunity for _, _, opportunity in scored]
    account.kept = len(kept)
    return kept, account
