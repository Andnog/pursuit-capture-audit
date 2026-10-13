"""Minimal road topology for the evader and for offline checks.

A deliberately small graph type: directed edges with lengths and successors. It is what the
scripted evader needs to choose a continuation, and no more. W3's adapter is backend
agnostic for the same reason — the real network arrives at W4, and everything above this
interface should not have to change when it does.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Edge:
    edge_id: str
    from_node: str
    to_node: str
    length_m: float
    speed_limit_mps: float = 13.89


@dataclass
class Topology:
    """A directed road graph. Public information: every agent may read all of it."""

    edges: dict[str, Edge] = field(default_factory=dict)
    _by_from: dict[str, list[str]] = field(default_factory=dict, repr=False)

    @staticmethod
    def build(edges: list[Edge]) -> Topology:
        topology = Topology(edges={e.edge_id: e for e in edges})
        for edge in edges:
            topology._by_from.setdefault(edge.from_node, []).append(edge.edge_id)
        for ids in topology._by_from.values():
            ids.sort()  # frozen ordering, so enumeration is reproducible
        return topology

    def successors(self, edge_id: str) -> list[str]:
        """Admissible continuations from the end of `edge_id`, in frozen order."""
        edge = self.edges[edge_id]
        return list(self._by_from.get(edge.to_node, ()))

    def is_dead_end(self, edge_id: str) -> bool:
        """An edge with no continuation. The evader that enters one becomes stuck."""
        return not self.successors(edge_id)

    def distance_between_nodes(self, source: str, target: str) -> float | None:
        """Shortest travel distance, or `None` when unreachable.

        Used by the AVOIDANT and OPTIMAL_ESCAPE levels. It reads only the public topology
        and the pursuers' CURRENT positions; nothing here consults a future trajectory.
        """
        if source == target:
            return 0.0
        seen: set[str] = set()
        queue: list[tuple[float, str]] = [(0.0, source)]
        while queue:
            cost, node = heapq.heappop(queue)
            if node in seen:
                continue
            seen.add(node)
            if node == target:
                return cost
            for edge_id in self._by_from.get(node, ()):
                edge = self.edges[edge_id]
                if edge.to_node not in seen:
                    heapq.heappush(queue, (cost + edge.length_m, edge.to_node))
        return None

    def distance_from_edge_end(self, edge_id: str, target_node: str) -> float | None:
        return self.distance_between_nodes(self.edges[edge_id].to_node, target_node)
