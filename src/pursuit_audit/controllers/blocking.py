"""Close a junction: which pursuer stops in which exit lane, and whether the team is in time.

The team can close a junction when it has at least as many pursuers as the junction has exit
lanes and the best one-to-one assignment leaves enough slack in every lane:

    max over assignments  of  min over lanes  [ evader arrival - pursuer arrival ]  >=  margin

The criterion is the smallest slack, not the sum of the times: a junction is closed only if its
worst-served lane is closed.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

Lane = tuple[str, int]  # exit edge, lane index
_CLEARANCE_AHEAD_M = 6.0
_END_OF_EDGE_M = 1.0


@dataclass(frozen=True)
class Assignment:
    """An assignment of pursuers to the exit lanes of a junction.

    Attributes:
        blockers: The lane of each assigned pursuer.
        slack_s: The smallest slack over the lanes.
    """

    blockers: dict[str, Lane]
    slack_s: float


def stop_point_cost(
    position: tuple[str, float],
    edge: str,
    *,
    edge_length_m: float,
    speed_cap_mps: float,
    hold_m: float,
    time_to_edge_end_s: float | None,
    slow: float,
    startup_s: float,
) -> tuple[float, float]:
    """Estimate the time for a pursuer to reach its stopping point in an exit, and that point.

    Args:
        position: The edge and offset of the pursuer.
        edge: The exit edge.
        edge_length_m: Its length.
        speed_cap_mps: Its speed cap.
        hold_m: The distance into the exit at which the pursuer should stop.
        time_to_edge_end_s: The pursuer's free-flow time to the end of the exit; ``None`` if the
            exit cannot be reached.
        slow: A factor that inflates free-flow time (start-up, yielding, signals).
        startup_s: A fixed delay added to every trip.

    Returns:
        The estimated time, infinite if the stopping point cannot be reached, and the stopping
        distance, moved ahead of a pursuer that is already on the exit.
    """
    if position[0] == edge:
        if position[1] + _CLEARANCE_AHEAD_M >= edge_length_m - _END_OF_EDGE_M:
            return math.inf, hold_m
        return 0.0, max(hold_m, position[1] + _CLEARANCE_AHEAD_M)
    if time_to_edge_end_s is None:
        return math.inf, hold_m
    free = time_to_edge_end_s - (edge_length_m - hold_m) / speed_cap_mps
    return slow * free + startup_s, hold_m


def _smallest_slack(
    chosen: Sequence[str],
    lanes: Sequence[Lane],
    cost_s: Mapping[tuple[str, Lane], float],
    evader_arrival_s: float,
) -> float:
    pairs = zip(chosen, lanes, strict=True)
    return min(evader_arrival_s - cost_s[(pursuer, lane)] for pursuer, lane in pairs)


def _exhaustive(pursuers, lanes, cost_s, evader_arrival_s) -> tuple[tuple[str, ...] | None, float]:
    best, best_slack = None, -math.inf
    for chosen in itertools.permutations(pursuers, len(lanes)):
        slack = _smallest_slack(chosen, lanes, cost_s, evader_arrival_s)
        if slack > best_slack:
            best, best_slack = chosen, slack
    return best, best_slack


def _hardest_lane_first(pursuers, lanes, cost_s, evader_arrival_s) -> tuple[tuple[str, ...], float]:
    free = set(pursuers)
    order = sorted(lanes, key=lambda lane: -min(cost_s[(p, lane)] for p in pursuers))
    pick = {}
    for lane in order:
        pursuer = min(free, key=lambda p: (cost_s[(p, lane)], p))
        pick[lane] = pursuer
        free.discard(pursuer)
    chosen = tuple(pick[lane] for lane in lanes)
    return chosen, _smallest_slack(chosen, lanes, cost_s, evader_arrival_s)


def assign_blockers(
    pursuers: Sequence[str],
    lanes: Sequence[Lane],
    cost_s: Mapping[tuple[str, Lane], float],
    *,
    evader_arrival_s: float,
    margin_s: float,
    exhaustive_up_to: int | None = None,
) -> Assignment | None:
    """Assign one pursuer to every exit lane, maximizing the smallest slack.

    Args:
        pursuers: The pursuers, in a fixed order that breaks ties.
        lanes: The exit lanes to close.
        cost_s: The estimated time of each pursuer to each lane.
        evader_arrival_s: The predicted arrival of the evader at the junction.
        margin_s: The slack that every lane must keep.
        exhaustive_up_to: Enumerate every assignment up to this number of pursuers, and above it
            serve the hardest lane first. ``None`` always enumerates.

    Returns:
        The assignment, or ``None`` if the junction has more lanes than the team has pursuers or
        the best assignment leaves less than the margin.
    """
    if not lanes or len(lanes) > len(pursuers):
        return None
    if exhaustive_up_to is not None and len(pursuers) > exhaustive_up_to:
        chosen, slack = _hardest_lane_first(pursuers, lanes, cost_s, evader_arrival_s)
    else:
        chosen, slack = _exhaustive(pursuers, lanes, cost_s, evader_arrival_s)
    if chosen is None or slack < margin_s:
        return None
    return Assignment(dict(zip(chosen, lanes, strict=True)), slack)
