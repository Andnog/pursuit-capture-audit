"""The scripted evader: a difficulty level, not a policy.

Decision D08, frozen 21 September 2026. The evader is **not** an agent whose behaviour this
project must justify. It is a scripted routine with three declared levels, so the only
thing configured per scenario is how hard the pursuers' task is.

That shape is deliberate: it keeps the evader out of the contribution. No claim depends on
it being optimal or realistic — only on its level being declared and held fixed. A learned
or hand-tuned evader would have made every result contingent on an evader design that
itself needed defending.

**Why every decision is logged with its alternatives.** The capture contract (D06) admits a
capture in a cul-de-sac as *coordinated* only if the evader was FORCED there, with positive
evidence that no better exit was available where it entered. That evidence has to come from
somewhere, and the only place it can come from is the evader's own decision record. So this
module logs the full admissible set at every decision, not just the choice. It is the link
between D06 and D08, and without it the dead-end rule would be unfalsifiable.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import IntEnum

from .topology import Topology

# Two sentinels with OPPOSITE meanings, kept distinct on purpose. An earlier version mapped
# both to -1.0, which silently made "the pursuers cannot reach this at all" — the best
# possible outcome for the evader — indistinguishable from "this is a cul-de-sac", the
# worst. Scores are reported, so a collision there would corrupt the audit record too.
UNREACHABLE_SCORE = 1.0e9  # no pursuer can reach it: maximally safe
DEAD_END_PENALTY = -1.0  # a cul-de-sac while alternatives exist: never a good escape


class EvaderLevel(IntEnum):
    """Difficulty for the pursuers, ascending."""

    RANDOM = 1
    AVOIDANT = 2
    OPTIMAL_ESCAPE = 3


@dataclass(frozen=True)
class EvaderDecision:
    """One decision, with everything needed to audit it afterwards."""

    decision_index: int
    current_edge: str
    admissible: tuple[str, ...]
    chosen: str | None
    level: EvaderLevel
    reason: str
    scores: dict[str, float] = field(default_factory=dict)

    @property
    def had_alternatives(self) -> bool:
        return len(self.admissible) > 1

    @property
    def entered_dead_end(self) -> bool:
        return self.chosen is None


def _finite(value: float) -> float:
    """Map an unreachable distance to a large finite score.

    Unreachable means no pursuer can get there, which is the SAFEST outcome for the evader,
    so it must score high. Serialising it as a negative sentinel would invert its meaning.
    """
    return UNREACHABLE_SCORE if value == float("inf") else value


def _keyed_unit_float(seed: int, decision_index: int, salt: str) -> float:
    """A reproducible value in [0, 1) keyed by seed, decision and salt.

    Keyed rather than sequential on purpose. A sequential stream makes the evader's choice
    depend on how many numbers everything else happened to draw, so restoring a prefix and
    replaying would diverge — exactly the failure W3 demonstrated for shared seeds. Keying
    on the decision index means a restored prefix reproduces the same choice regardless of
    what else consumed randomness.
    """
    digest = hashlib.sha256(f"{seed}|{decision_index}|{salt}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


@dataclass
class ScriptedEvader:
    """The evader. Deterministic given `(level, seed)` and the public state."""

    level: EvaderLevel
    seed: int
    topology: Topology
    decisions: list[EvaderDecision] = field(default_factory=list)
    # A-62. "node": distance to the node each pursuer is heading to (D08 as frozen).
    # "interpolated": distance interpolated along the pursuer's edge by the fraction it has
    # covered - the same public information, but continuous in time. The node input jumps
    # a whole edge when a pursuer enters the next one, so a tenth of a second changed the
    # evader's choice in SUMO's closed loop (X03).
    input_mode: str = "node"
    _positions: dict | None = field(default=None, repr=False)

    def choose(
        self,
        decision_index: int,
        current_edge: str,
        pursuer_nodes: dict[str, str],
        pursuer_positions: dict[str, tuple[str, str, float]] | None = None,
    ) -> EvaderDecision:
        """Pick a continuation from the end of `current_edge`.

        `pursuer_nodes` maps each pursuer to the node it is currently at;
        `pursuer_positions` maps it to `(from_node, to_node, fraction covered)` of the edge it
        is on and is used in "interpolated" mode. Both are public information. **No future
        trajectory, intent or plan of any pursuer is consulted at any level**, and there is
        no route oracle.
        """
        if self.input_mode == "interpolated" and pursuer_positions is None:
            raise ValueError("interpolated evader input needs pursuer_positions")
        self._positions = pursuer_positions if self.input_mode == "interpolated" else None
        try:
            return self._choose(decision_index, current_edge, pursuer_nodes)
        finally:
            self._positions = None

    def _choose(
        self,
        decision_index: int,
        current_edge: str,
        pursuer_nodes: dict[str, str],
    ) -> EvaderDecision:
        admissible = tuple(self.topology.successors(current_edge))

        if not admissible:
            decision = EvaderDecision(
                decision_index,
                current_edge,
                admissible,
                None,
                self.level,
                "dead_end_no_admissible_continuation",
            )
            self.decisions.append(decision)
            return decision

        if self.level is EvaderLevel.RANDOM:
            index = int(_keyed_unit_float(self.seed, decision_index, "random") * len(admissible))
            index = min(index, len(admissible) - 1)
            decision = EvaderDecision(
                decision_index,
                current_edge,
                admissible,
                admissible[index],
                self.level,
                "uniform_among_admissible",
            )
        elif self.level is EvaderLevel.AVOIDANT:
            decision = self._avoidant(decision_index, current_edge, admissible, pursuer_nodes)
        else:
            decision = self._optimal_escape(decision_index, current_edge, admissible, pursuer_nodes)

        self.decisions.append(decision)
        return decision

    def _pursuer_distances(self, candidate: str, pursuer_nodes: dict[str, str]) -> list[float]:
        """Distance from the candidate's far end to each pursuer. Unreachable counts as far."""
        end = self.topology.edges[candidate].to_node
        out = []
        if self._positions is not None:
            # Distance FOR THE PURSUER to reach the candidate's end, interpolated between the
            # ends of its edge by the fraction covered: equal on both sides of a node, so
            # continuous in time. A first version measured end -> pursuer instead and let a
            # helper standing on the candidate edge itself count as far away (control test).
            for from_node, to_node, fraction in self._positions.values():
                near = self.topology.distance_between_nodes(from_node, end)
                far = self.topology.distance_between_nodes(to_node, end)
                near = float("inf") if near is None else near
                far = float("inf") if far is None else far
                if fraction <= 0.0:
                    out.append(near)
                elif fraction >= 1.0:
                    out.append(far)
                elif near == float("inf") or far == float("inf"):
                    out.append(float("inf"))
                else:
                    out.append((1.0 - fraction) * near + fraction * far)
            return out
        for node in pursuer_nodes.values():
            distance = self.topology.distance_between_nodes(end, node)
            out.append(float("inf") if distance is None else distance)
        return out

    def _escape_score(
        self, candidate: str, pursuer_nodes: dict[str, str], admissible_count: int
    ) -> float:
        """How good `candidate` is as an escape. Shared by levels 2 and 3.

        Distance to the nearest pursuer, except that a cul-de-sac scores below every real
        distance while any alternative exists.

        The penalty is essential rather than cosmetic, and measurement is what showed it.
        Graph distance rates a dead end as MAXIMALLY safe, because no pursuer can reach it -
        true, and strategically suicidal. Without the penalty level 2 walked into dead ends
        75.5% of the time against 47% for level 1, INVERTING the difficulty ordering and
        making the supposedly harder level easier for the pursuers.
        """
        onward = len(self.topology.successors(candidate))
        if onward == 0 and admissible_count > 1:
            return DEAD_END_PENALTY
        return _finite(min(self._pursuer_distances(candidate, pursuer_nodes), default=float("inf")))

    def _avoidant(
        self,
        decision_index: int,
        current_edge: str,
        admissible: tuple[str, ...],
        pursuer_nodes: dict[str, str],
    ) -> EvaderDecision:
        """Level 2: go away from the pursuers, but not necessarily optimally.

        Scores each continuation by the distance to the NEAREST pursuer, then takes the best
        of a randomly chosen pair rather than the global best. That is what makes it level 2
        and not level 3: it reliably moves away without reliably choosing the best escape.
        """
        # Level 2 shares the escape score, including the dead-end penalty. Its
        # suboptimality comes from WHICH open direction it picks, not from trapping
        # itself.
        scores = {c: self._escape_score(c, pursuer_nodes, len(admissible)) for c in admissible}
        if len(admissible) == 1:
            chosen = admissible[0]
            reason = "single_admissible_continuation"
        else:
            first = int(_keyed_unit_float(self.seed, decision_index, "avoid_a") * len(admissible))
            second = int(_keyed_unit_float(self.seed, decision_index, "avoid_b") * len(admissible))
            first, second = min(first, len(admissible) - 1), min(second, len(admissible) - 1)
            pair = {admissible[first], admissible[second]}
            chosen = max(sorted(pair), key=lambda c: (scores[c], c))
            reason = "best_of_a_sampled_pair_by_distance_to_nearest_pursuer"
        return EvaderDecision(
            decision_index,
            current_edge,
            admissible,
            chosen,
            self.level,
            reason,
            scores,
        )

    def _optimal_escape(
        self,
        decision_index: int,
        current_edge: str,
        admissible: tuple[str, ...],
        pursuer_nodes: dict[str, str],
    ) -> EvaderDecision:
        """Level 3: the best available escape given the pursuers' observed positions.

        Maximises the shared escape score, breaking ties by onward branching: a continuation
        that keeps more options open is a better escape than one that does not. Levels 2 and
        3 now use the SAME score; what separates them is that level 2 picks the better of a
        sampled pair while level 3 takes the global best.
        """
        scores = {c: self._escape_score(c, pursuer_nodes, len(admissible)) for c in admissible}
        best = max(
            sorted(admissible),
            key=lambda c: (scores[c], len(self.topology.successors(c)), c),
        )
        return EvaderDecision(
            decision_index,
            current_edge,
            admissible,
            best,
            self.level,
            "max_distance_to_nearest_pursuer_tiebreak_onward_branching",
            {k: (v if v != float("inf") else -1.0) for k, v in scores.items()},
        )

    # -- audit ----------------------------------------------------------------------

    def dead_end_entry(self) -> EvaderDecision | None:
        """The decision at which the evader committed to the edge that dead-ended, if any.

        Returns the decision BEFORE the dead end, because that is where the alternatives
        existed. The dead-end decision itself has no alternatives by definition, so auditing
        it would always conclude "no choice available" and the rule would be vacuous.
        """
        for index, decision in enumerate(self.decisions):
            if decision.entered_dead_end and index > 0:
                return self.decisions[index - 1]
        return None

    def was_forced_into_dead_end(self) -> tuple[bool, str, dict]:
        """Whether a dead-end capture may be recorded as COORDINATED, per D06.

        Forced means every alternative at the entry decision was itself a dead end. If any
        alternative led onward, the evader chose the cul-de-sac and the pursuers did not
        force it there — the capture is then `CAPTURE_UNCOORDINATED_DEAD_END`.

        This is a conservative reading. A pursuer team might block an onward alternative
        without that alternative being a dead end, and this test would not credit them.
        Crediting that case needs occupancy evidence at the entry decision, which this
        module does not have; the strict reading is the one that cannot over-credit.
        """
        entry = self.dead_end_entry()
        if entry is None:
            return False, "no_dead_end_entry_recorded", {}
        alternatives = [c for c in entry.admissible if c != entry.chosen]
        onward = {c: len(self.topology.successors(c)) for c in alternatives}
        escapable = [c for c, count in onward.items() if count > 0]
        detail = {
            "entry_decision_index": entry.decision_index,
            "admissible": list(entry.admissible),
            "chosen": entry.chosen,
            "alternatives_with_onward_continuations": escapable,
        }
        if not alternatives:
            return True, "no_alternative_existed_at_entry", detail
        if not escapable:
            return True, "every_alternative_was_also_a_dead_end", detail
        return False, "an_escapable_alternative_existed_at_entry", detail
