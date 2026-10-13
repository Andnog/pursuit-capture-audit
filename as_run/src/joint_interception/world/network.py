"""The network as the declared model sees it: edges, real connections, internal lanes, signals.

Built from a SUMO network file with `sumolib`, read-only. Transitions follow the network's
actual CONNECTIONS, not every edge leaving a node: `Topology.successors` enumerates by node
and would let a vehicle make turns the network forbids.
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

from ..opportunities.approach import SignalProgram
from ..simulator.topology import Edge, Topology

Point = tuple[float, float]


@dataclass(frozen=True)
class EdgeInfo:
    edge_id: str
    from_node: str
    to_node: str
    length_m: float
    lanes: int
    speed_cap_mps: float
    shape: tuple[Point, ...]

    @property
    def single_lane(self) -> bool:
        return self.lanes == 1


@dataclass(frozen=True)
class Link:
    """A permitted transition from one edge to the next, through a junction."""

    from_edge: str
    to_edge: str
    via_length_m: float
    via_speed_mps: float
    via_shape: tuple[Point, ...]
    signal: tuple[str, int] | None
    # SUMO right of way (A-47 harness development): the connection's link state ("M" major,
    # "m" minor, "=" equal, "O"/"o" signal-controlled), and the links of the same junction that
    # have priority over this one.
    state: str = "M"
    prohibitors: tuple[tuple[str, str], ...] = ()


@dataclass
class GraphNetwork:
    edges: dict[str, EdgeInfo]
    links: dict[tuple[str, str], Link]
    programs: dict[str, SignalProgram]
    _successors: dict[str, list[str]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        by_from: dict[str, list[str]] = {}
        for from_edge, to_edge in self.links:
            by_from.setdefault(from_edge, []).append(to_edge)
        self._successors = {k: sorted(v) for k, v in by_from.items()}

    def successors(self, edge_id: str) -> list[str]:
        return list(self._successors.get(edge_id, ()))

    def link(self, from_edge: str, to_edge: str) -> Link | None:
        return self.links.get((from_edge, to_edge))

    def traversal_time_s(self, edge_id: str) -> float:
        edge = self.edges[edge_id]
        return edge.length_m / max(edge.speed_cap_mps, 1e-6)

    def route(self, start_edge: str, goal_edge: str) -> list[str] | None:
        """Fastest route by free-flow time at each edge's cap, internal lanes included.

        Returns the edge list from `start_edge` to `goal_edge` inclusive, or `None`.
        """
        if start_edge == goal_edge:
            return [start_edge]
        best: dict[str, float] = {start_edge: 0.0}
        parent: dict[str, str] = {}
        queue: list[tuple[float, str]] = [(0.0, start_edge)]
        while queue:
            cost, edge_id = heapq.heappop(queue)
            if edge_id == goal_edge:
                path = [edge_id]
                while path[-1] in parent:
                    path.append(parent[path[-1]])
                return path[::-1]
            if cost > best.get(edge_id, math.inf):
                continue
            for nxt in self.successors(edge_id):
                link = self.links[(edge_id, nxt)]
                step = self.traversal_time_s(edge_id) + link.via_length_m / max(
                    link.via_speed_mps, 1e-6
                )
                candidate = cost + step
                if candidate < best.get(nxt, math.inf):
                    best[nxt] = candidate
                    parent[nxt] = edge_id
                    heapq.heappush(queue, (candidate, nxt))
        return None

    def topology(self) -> Topology:
        """The evader's view: public topology whose successors follow real connections."""
        return ConnectedTopology.build_from(self)

    @staticmethod
    def from_sumo(path: str) -> GraphNetwork:
        import sumolib

        from ..opportunities.approach import SignalProgram as Program

        net = sumolib.net.readNet(path, withInternal=True, withPrograms=True)
        edges: dict[str, EdgeInfo] = {}
        for edge in net.getEdges():
            if edge.isSpecial() or not edge.allows("passenger"):
                continue
            lanes = [lane for lane in edge.getLanes() if lane.allows("passenger")]
            if not lanes:
                continue
            reference = lanes[0]
            edges[edge.getID()] = EdgeInfo(
                edge_id=edge.getID(),
                from_node=edge.getFromNode().getID(),
                to_node=edge.getToNode().getID(),
                length_m=reference.getLength(),
                lanes=len(lanes),
                speed_cap_mps=min(lane.getSpeed() for lane in lanes),
                shape=tuple(tuple(p) for p in reference.getShape()),
            )
        links: dict[tuple[str, str], Link] = {}
        index_to_pair: dict[tuple[str, int], tuple[str, str]] = {}
        chosen: dict[tuple[str, str], object] = {}
        for edge_id in edges:
            for target, connections in net.getEdge(edge_id).getOutgoing().items():
                if target.getID() not in edges:
                    continue
                for connection in connections:
                    node = net.getEdge(edge_id).getToNode().getID()
                    index_to_pair[(node, connection.getJunctionIndex())] = (edge_id, target.getID())
        for edge_id in edges:
            outgoing = net.getEdge(edge_id).getOutgoing()
            for target, connections in outgoing.items():
                to_id = target.getID()
                if to_id not in edges or not connections:
                    continue
                connection = connections[0]
                via_length, via_speed, via_shape = _via_chain(net, connection, to_id)
                if via_length <= 0.0:
                    via_speed = edges[to_id].speed_cap_mps
                tls = connection.getTLSID()
                index = connection.getTLLinkIndex()
                signal = (tls, index) if tls and index is not None and index >= 0 else None
                chosen[(edge_id, to_id)] = connection
                links[(edge_id, to_id)] = Link(
                    edge_id,
                    to_id,
                    via_length,
                    via_speed,
                    via_shape,
                    signal,
                    connection.getState(),
                    _prohibitors(net, edge_id, connection, index_to_pair),
                )
        programs: dict[str, SignalProgram] = {}
        for tls in net.getTrafficLights():
            programs_of = tls.getPrograms()
            if not programs_of:
                continue
            program = next(iter(programs_of.values()))
            phases = program.getPhases()
            if phases:
                programs[tls.getID()] = Program(
                    tls.getID(),
                    tuple(float(p.duration) for p in phases),
                    tuple(p.state for p in phases),
                    float(getattr(program, "offset", 0.0) or 0.0),
                )
        return GraphNetwork(edges, links, programs)


def _prohibitors(net, from_edge: str, connection, index_to_pair) -> tuple[tuple[str, str], ...]:
    """Links of the same junction whose vehicles `connection`'s must yield to (SUMO's request
    matrix: `prohibits[mine]`, read right to left)."""
    node = net.getEdge(from_edge).getToNode()
    mine = connection.getJunctionIndex()
    table = getattr(node, "_prohibits", None)
    if not table or mine is None or mine < 0 or mine not in table:
        return ()
    row = table[mine]
    out = set()
    for other in range(len(row)):
        if row[-(other + 1)] == "1":
            pair = index_to_pair.get((node.getID(), other))
            if pair is not None and pair != (from_edge, connection.getTo().getID()):
                out.add(pair)
    return tuple(sorted(out))


def _via_chain(net, connection, to_edge: str) -> tuple[float, float, tuple]:
    """Length, slowest speed and shape of the WHOLE internal path of a connection.

    At junctions with an internal junction SUMO splits the internal path into a chain of
    lanes, and `getViaLaneID()` returns only the first. Reading one lane was the whole of
    A-43's 42 m distance discrepancy: on adelaide_cbd route 0 it accrued at a single
    junction whose chain was 9.53 m then 41.95 m.
    """
    via_id = connection.getViaLaneID()
    length, speed, shape = 0.0, math.inf, []
    seen: set[str] = set()
    while via_id and via_id not in seen:
        seen.add(via_id)
        try:
            lane = net.getLane(via_id)
        except KeyError:
            break
        length += lane.getLength()
        speed = min(speed, lane.getSpeed())
        shape.extend(tuple(p) for p in lane.getShape())
        following = None
        for nxt in lane.getOutgoing():
            target = nxt.getToLane().getEdge()
            if target.getID() == to_edge or target.isSpecial():
                following = nxt.getViaLaneID() or None
                if following:
                    break
        via_id = following
    return length, (speed if speed != math.inf else 0.0), tuple(shape)


class ConnectedTopology(Topology):
    """`Topology` whose successors are the network's real connections, not every edge at a node."""

    _network_successors: dict[str, list[str]]

    @staticmethod
    def build_from(network: GraphNetwork) -> ConnectedTopology:
        base = Topology.build(
            [
                Edge(e.edge_id, e.from_node, e.to_node, e.length_m, e.speed_cap_mps)
                for e in network.edges.values()
            ]
        )
        topology = ConnectedTopology(edges=base.edges, _by_from=base._by_from)
        topology._network_successors = {e: network.successors(e) for e in network.edges}
        return topology

    def successors(self, edge_id: str) -> list[str]:
        return list(self._network_successors.get(edge_id, ()))


def point_on_shape(shape: tuple[Point, ...], distance: float) -> tuple[float, float, float]:
    """Point and heading at `distance` along a polyline, clamped to its ends."""
    if len(shape) < 2:
        x, y = shape[0] if shape else (0.0, 0.0)
        return x, y, 0.0
    remaining = max(0.0, distance)
    for (x0, y0), (x1, y1) in zip(shape, shape[1:], strict=False):
        segment = math.hypot(x1 - x0, y1 - y0)
        heading = math.atan2(y1 - y0, x1 - x0)
        if remaining <= segment or (x1, y1) == shape[-1]:
            t = 0.0 if segment <= 1e-12 else min(1.0, remaining / segment)
            return x0 + t * (x1 - x0), y0 + t * (y1 - y0), heading
        remaining -= segment
    (x0, y0), (x1, y1) = shape[-2], shape[-1]
    return x1, y1, math.atan2(y1 - y0, x1 - x0)
