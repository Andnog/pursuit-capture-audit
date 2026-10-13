"""Pre-position the pursuers that are not needed for an ambush.

When the team cannot close a junction, predictive lane blocking sends its free pursuers ahead, to
wait in the lanes of the exits that the evader is predicted to take at the next junctions. The
pursuers decide in a fixed order. Each takes the best lane that it can reach in time: the
predicted exit first, then the nearer junction, then the larger slack. A lane taken by a teammate
is excluded, which is what joint assignment means here; the coordination ablation of the study
removes that exclusion.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from .prediction import PathStep


@dataclass(frozen=True)
class Target:
    """A waiting position: a lane of an exit, a stopping distance, and the junction it serves."""

    edge: str
    lane: int
    hold_m: float
    junction: str


@dataclass(frozen=True)
class PrepositioningRule:
    """The parameters of pre-positioning.

    Attributes:
        first_junction: The nearest junction on the predicted path to consider (1 is the next).
        last_junction: The farthest junction to consider.
        margin_s: The slack that a pursuer must keep over the evader at its lane.
        hold_m: The distance into the exit at which a pursuer stops.
        independent: Let every pursuer choose as if alone, without excluding teammates' lanes.
    """

    first_junction: int = 2
    last_junction: int = 5
    margin_s: float = 1.0
    hold_m: float = 12.0
    independent: bool = False


def preposition(
    path: Sequence[PathStep],
    free_pursuers: Sequence[str],
    rule: PrepositioningRule,
    *,
    exits_of: Callable[[PathStep], Sequence[str]],
    lanes_of: Callable[[str], Sequence[int]],
    edge_length_m: Callable[[str], float],
    cost_of: Callable[[str, str, float], tuple[float, float]],
    previous: Mapping[str, Target] | None = None,
) -> dict[str, Target]:
    """Choose a waiting lane for each free pursuer.

    Args:
        path: The predicted junctions of the evader, nearest first.
        free_pursuers: The pursuers to place.
        rule: The parameters.
        exits_of: The exits of a junction, the predicted one first.
        lanes_of: The lanes of an exit.
        edge_length_m: The length of an edge.
        cost_of: The estimated time of a pursuer to its stopping point in an exit, and that point,
            given the pursuer, the exit and the nominal stopping distance.
        previous: The targets chosen at the previous step. A target whose junction is still ahead
            is kept, so that pursuers are not re-routed at every step.

    Returns:
        The target of each pursuer that has one. A pursuer without a target chases.
    """
    ahead = {step.junction for step in path}
    chosen = {
        pursuer: target
        for pursuer, target in (previous or {}).items()
        if pursuer in free_pursuers and target.junction in ahead
    }
    taken = {(target.edge, target.lane) for target in chosen.values()}
    candidates = []
    for number, step in enumerate(path, 1):
        if not rule.first_junction <= number <= rule.last_junction:
            continue
        for rank, exit_edge in enumerate(exits_of(step)):
            for lane in lanes_of(exit_edge):
                candidates.append((number, rank, exit_edge, lane, step))
    for pursuer in sorted(free_pursuers):
        if pursuer in chosen:
            continue
        best, best_key = None, None
        for number, rank, exit_edge, lane, step in candidates:
            if (exit_edge, lane) in taken and not rule.independent:
                continue
            nominal = min(rule.hold_m, 0.5 * edge_length_m(exit_edge))
            cost, hold = cost_of(pursuer, exit_edge, nominal)
            slack = step.time_s - cost
            if slack < rule.margin_s:
                continue
            key = (rank, number, -slack)
            if best_key is None or key < best_key:
                best, best_key = Target(exit_edge, lane, hold, step.junction), key
        if best is not None:
            chosen[pursuer] = best
            taken.add((best.edge, best.lane))
    return chosen
