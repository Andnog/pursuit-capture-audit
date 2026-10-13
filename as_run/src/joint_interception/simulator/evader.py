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
    # A-112: a goal-directed fugitive (not part of the ascending difficulty order).
    GOAL_DIRECTED = 4
    # A-127: a weighted-feature evader whose weights are tuned against a controller.
    TUNED = 5


GOAL_MIN_DISTANCE_M = 800.0  # A-112: a destination at least this far by road
GOAL_AVOID_RADIUS_M = 150.0  # A-112: continuations ending this close to a pursuer are avoided

# A-127: features of the TUNED level, in the order of the weights.
TUNED_FEATURES = ("d1", "d2", "branch", "crowd", "on_edge", "predicted", "noise")
# Weights used by the TUNED level, set by a study before an episode. The default reproduces
# OPTIMAL_ESCAPE, so an unconfigured TUNED evader is the level-3 evader.
TUNED_WEIGHTS: tuple[float, ...] = (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
TUNED_DISTANCE_CAP_M = 1000.0
TUNED_CROWD_RADIUS_M = 300.0
TUNED_BRANCH_CAP = 4


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
    # A-112: candidate destinations for GOAL_DIRECTED (outer band of the network), sorted.
    goal_nodes: tuple[str, ...] = ()
    _positions: dict | None = field(default=None, repr=False)
    _goal: str | None = field(default=None, repr=False)
    # A-127: the pursuers' current edges, whatever the input mode (public information).
    _public_positions: dict | None = field(default=None, repr=False)

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
        self._public_positions = pursuer_positions
        try:
            return self._choose(decision_index, current_edge, pursuer_nodes)
        finally:
            self._positions = None
            self._public_positions = None

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
        elif self.level is EvaderLevel.GOAL_DIRECTED:
            decision = self._goal_directed(decision_index, current_edge, admissible, pursuer_nodes)
        elif self.level is EvaderLevel.TUNED:
            decision = self._tuned(decision_index, current_edge, admissible, pursuer_nodes)
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

    def _pick_goal(self, decision_index: int, from_node: str) -> str | None:
        """A destination keyed by seed and decision, among outer-band nodes far enough by road."""
        far = [
            n
            for n in self.goal_nodes
            if (d := self.topology.distance_between_nodes(from_node, n)) is not None
            and d >= GOAL_MIN_DISTANCE_M
        ]
        if not far:
            return None
        u = _keyed_unit_float(self.seed, decision_index, "goal")
        return far[min(int(u * len(far)), len(far) - 1)]

    def _goal_directed(
        self,
        decision_index: int,
        current_edge: str,
        admissible: tuple[str, ...],
        pursuer_nodes: dict[str, str],
    ) -> EvaderDecision:
        """Level 4 (A-112): drive towards a far destination, avoiding pursuers close ahead.

        Among continuations that do not dead-end, take the one with the shortest road distance
        to the destination, ignoring those whose end is within GOAL_AVOID_RADIUS_M of a pursuer.
        If all are that close, fall back to the level-3 escape score.
        """
        here = self.topology.edges[current_edge].to_node
        if self._goal is None or here == self._goal:
            self._goal = self._pick_goal(decision_index, here)
        onward = [c for c in admissible if self.topology.successors(c)] or list(admissible)
        near = {
            c: min(self._pursuer_distances(c, pursuer_nodes), default=float("inf")) for c in onward
        }
        safe = [c for c in onward if near[c] >= GOAL_AVOID_RADIUS_M]
        to_goal = {}
        for c in onward:
            end = self.topology.edges[c].to_node
            d = (
                None
                if self._goal is None
                else self.topology.distance_between_nodes(end, self._goal)
            )
            to_goal[c] = float("inf") if d is None else d
        if safe and self._goal is not None:
            chosen = min(sorted(safe), key=lambda c: (to_goal[c], c))
            reason = "shortest_road_distance_to_destination_among_safe"
        else:
            scores = {c: self._escape_score(c, pursuer_nodes, len(admissible)) for c in onward}
            chosen = max(
                sorted(onward), key=lambda c: (scores[c], len(self.topology.successors(c)), c)
            )
            reason = "all_continuations_near_a_pursuer_fallback_escape"
        return EvaderDecision(
            decision_index,
            current_edge,
            admissible,
            chosen,
            self.level,
            reason,
            {c: (v if v != float("inf") else -1.0) for c, v in to_goal.items()},
        )

    def _tuned_features(
        self,
        decision_index: int,
        admissible: tuple[str, ...],
        pursuer_nodes: dict[str, str],
    ) -> tuple[dict[str, tuple[float, ...]], dict[str, float]]:
        """Features of every continuation (order of TUNED_FEATURES) and its uncapped distance."""
        occupied = set()
        if self._public_positions is not None:
            occupied = {(a, b) for a, b, _ in self._public_positions.values()}
        nearest, features = {}, {}
        for c in admissible:
            distances = sorted(_finite(d) for d in self._pursuer_distances(c, pursuer_nodes))
            nearest[c] = distances[0] if distances else UNREACHABLE_SCORE
        open_ = [
            c for c in admissible if self.topology.successors(c) or len(admissible) == 1
        ] or list(admissible)
        expected = max(
            sorted(open_), key=lambda c: (nearest[c], len(self.topology.successors(c)), c)
        )
        for c in admissible:
            distances = sorted(_finite(d) for d in self._pursuer_distances(c, pursuer_nodes))
            cap = TUNED_DISTANCE_CAP_M
            d1 = min(distances[0], cap) / cap if distances else 1.0
            d2 = min(distances[1], cap) / cap if len(distances) > 1 else 1.0
            onward = self.topology.successors(c)
            branch = min(len(onward), TUNED_BRANCH_CAP) / TUNED_BRANCH_CAP
            crowd = (
                sum(d <= TUNED_CROWD_RADIUS_M for d in distances) / len(distances)
                if distances
                else 0.0
            )
            if self._public_positions is not None:
                spans = [c, *onward]
                on_edge = any(
                    (self.topology.edges[x].from_node, self.topology.edges[x].to_node) in occupied
                    for x in spans
                )
            else:
                on_edge = self.topology.edges[c].to_node in set(pursuer_nodes.values())
            noise = _keyed_unit_float(self.seed, decision_index, f"tuned|{c}")
            features[c] = (d1, d2, branch, crowd, float(on_edge), float(c == expected), noise)
        return features, nearest

    def _tuned(
        self,
        decision_index: int,
        current_edge: str,
        admissible: tuple[str, ...],
        pursuer_nodes: dict[str, str],
    ) -> EvaderDecision:
        """Level 5 (A-127): the continuation with the best weighted sum of public features.

        The weights (TUNED_WEIGHTS) are tuned by a study against a controller. Only the pursuers'
        current positions are used. A cul-de-sac ranks below every open continuation while an
        alternative exists, as at levels 2 and 3. Ties are broken by the uncapped distance to the
        nearest pursuer, then by onward branching, then by name, so that the reference weights
        (distance only) reproduce OPTIMAL_ESCAPE.
        """
        weights = TUNED_WEIGHTS
        if len(weights) != len(TUNED_FEATURES):
            raise ValueError("TUNED_WEIGHTS must have one weight per feature")
        features, nearest = self._tuned_features(decision_index, admissible, pursuer_nodes)
        scores = {
            c: sum(w * f for w, f in zip(weights, features[c], strict=True)) for c in admissible
        }

        def rank(c: str):
            onward = len(self.topology.successors(c))
            if onward == 0 and len(admissible) > 1:
                return (False, 0.0, 0.0, 0, c)
            return (True, scores[c], nearest[c], onward, c)

        chosen = max(sorted(admissible), key=rank)
        return EvaderDecision(
            decision_index,
            current_edge,
            admissible,
            chosen,
            self.level,
            "max_weighted_public_features",
            {c: round(v, 6) for c, v in scores.items()},
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
