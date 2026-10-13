"""Predict the path of the evader.

The predictor assumes an evader that flees: at each junction it takes the continuation that
maximizes its time lead over the nearest pursuer at the end of that continuation. It knows the
general behaviour of the evader, not its random draws.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

_MINIMUM_SPEED_MPS = 0.1


@dataclass(frozen=True)
class Edge:
    """A directed street segment."""

    length_m: float
    speed_cap_mps: float
    to_node: str


@dataclass(frozen=True)
class Link:
    """The connection from one edge to the next, through a junction."""

    via_length_m: float
    via_speed_mps: float


@dataclass(frozen=True)
class RoadGraph:
    """The part of a road network that the decisions need.

    Attributes:
        edges: Every edge by its identifier.
        links: The connection between each pair of consecutive edges.
        successors: The edges that can follow each edge.
    """

    edges: Mapping[str, Edge]
    links: Mapping[tuple[str, str], Link]
    successors: Mapping[str, Sequence[str]] = field(default_factory=dict)

    def travel_time_s(self, edge: str, following: str, speed_factor: float = 1.0) -> float:
        """Return the free-flow time to cross a junction and drive the following edge."""
        link, target = self.links[(edge, following)], self.edges[following]
        crossing = link.via_length_m / max(link.via_speed_mps * speed_factor, _MINIMUM_SPEED_MPS)
        return crossing + target.length_m / (target.speed_cap_mps * speed_factor)


@dataclass(frozen=True)
class PathStep:
    """One junction on the predicted path.

    Attributes:
        arrival_edge: The edge by which the evader reaches the junction.
        junction: The junction.
        time_s: The predicted time until the evader reaches it.
    """

    arrival_edge: str
    junction: str
    time_s: float


def _lead_s(node: str, evader_time_s: float, pursuer_node_times: Mapping) -> float:
    """Return how long before the nearest pursuer the evader reaches a node."""
    nearest = min(
        (times.get(node, math.inf) for times in pursuer_node_times.values()), default=math.inf
    )
    return nearest - evader_time_s


def predict_path(
    graph: RoadGraph,
    edge: str,
    offset_m: float,
    pursuer_node_times: Mapping[str, Mapping[str, float]],
    *,
    depth: int,
    speed_factor: float = 1.0,
) -> list[PathStep]:
    """Predict the next junctions of the evader.

    Args:
        graph: The road graph.
        edge: The edge that the evader is on.
        offset_m: Its position along that edge.
        pursuer_node_times: For each pursuer, its travel time to each node.
        depth: The number of junctions to predict.
        speed_factor: The evader's speed relative to the speed caps.

    Returns:
        The predicted junctions, nearest first. The path stops early at a dead end or when the
        best continuation would revisit an edge.
    """
    current = graph.edges[edge]
    time_s = max(0.0, current.length_m - offset_m) / (current.speed_cap_mps * speed_factor)
    path: list[PathStep] = []
    seen = {edge}
    for _ in range(depth):
        path.append(PathStep(edge, graph.edges[edge].to_node, time_s))
        best, best_lead, best_time = None, -math.inf, None
        for following in sorted(graph.successors.get(edge, ())):
            arrival = time_s + graph.travel_time_s(edge, following, speed_factor)
            lead = _lead_s(graph.edges[following].to_node, arrival, pursuer_node_times)
            if lead > best_lead:
                best, best_lead, best_time = following, lead, arrival
        if best is None or best in seen:
            break
        seen.add(best)
        edge, time_s = best, best_time
    return path


def exit_order(
    graph: RoadGraph,
    arrival_edge: str,
    arrival_time_s: float,
    pursuer_node_times: Mapping[str, Mapping[str, float]],
    speed_factor: float = 1.0,
) -> list[str]:
    """Rank the exits of a junction by how attractive they are to a fleeing evader.

    The first exit is the predicted one: the continuation with the largest lead over the nearest
    pursuer. Ties are broken by the identifier of the exit.
    """
    scored = []
    for following in sorted(graph.successors.get(arrival_edge, ())):
        arrival = arrival_time_s + graph.travel_time_s(arrival_edge, following, speed_factor)
        lead = _lead_s(graph.edges[following].to_node, arrival, pursuer_node_times)
        scored.append((-lead, following))
    return [following for _, following in sorted(scored)]
