"""F1 feasibility probe: a caging certificate on the road graph and three pursuit strategies.

Certificate (evaluated every decision on SUMO's positions): with free-flow times over legal
connections (internal lanes included), the evader's SAFE REGION is the set of junctions it reaches
strictly before every pursuer (by `margin_s`). Its GATES are the junctions outside it that the
evader could step to from inside. The evader is CAGED when its safe region has at most `k_nodes`
junctions; the cage counts once it has held for `persist_s` seconds.

Strategies (no learning):
- "cut": pursuers are assigned to distinct gates, most urgent gate first, each to the pursuer
  that reaches it soonest; spare pursuers chase the evader;
- "individual": every pursuer independently goes to the gate it can take with the largest
  margin, duplicates allowed;
- "pursuit": every pursuer drives to the evader's current edge.
"""

from __future__ import annotations

import heapq

from ..world.network import GraphNetwork


class Reach:
    """Free-flow arrival times over legal connections."""

    def __init__(self, net: GraphNetwork):
        self.net = net
        self.succ = {e: net.successors(e) for e in net.edges}

    def from_edge(self, edge: str, offset: float, speed_factor: float = 1.0):
        """Time to the END of every edge, starting at `offset` on `edge`. Returns (dist, prev)."""
        net = self.net
        info = net.edges[edge]
        dist = {edge: max(0.0, info.length_m - offset) / (info.speed_cap_mps * speed_factor)}
        prev: dict[str, str | None] = {edge: None}
        heap = [(dist[edge], edge)]
        while heap:
            d, e = heapq.heappop(heap)
            if d > dist.get(e, float("inf")) + 1e-9:
                continue
            for s in self.succ.get(e, ()):
                link = net.links[(e, s)]
                cost = link.via_length_m / max(link.via_speed_mps * speed_factor, 0.1)
                cost += net.edges[s].length_m / (net.edges[s].speed_cap_mps * speed_factor)
                if d + cost < dist.get(s, float("inf")) - 1e-9:
                    dist[s] = d + cost
                    prev[s] = e
                    heapq.heappush(heap, (d + cost, s))
        return dist, prev

    def node_times(self, dist) -> dict[str, float]:
        out: dict[str, float] = {}
        for e, d in dist.items():
            n = self.net.edges[e].to_node
            if d < out.get(n, float("inf")):
                out[n] = d
        return out


def vehicle_edge(state, conn, vid, net):
    """(edge, offset) of a vehicle from SUMO's state; inside a junction: the next edge's start."""
    road, lane_id, pos = state[0], state[1], state[2]
    if road.startswith(":"):
        route = conn.vehicle.getRoute(vid)
        idx = conn.vehicle.getRouteIndex(vid)
        nxt = route[min(idx + 1, len(route) - 1)]
        return nxt, 0.0
    if road not in net.edges:
        return None
    lane_len = conn.lane.getLength(lane_id) if lane_id else net.edges[road].length_m
    return road, pos * net.edges[road].length_m / max(lane_len, 1e-6)


def certificate(
    reach: Reach,
    evader_pos,
    pursuer_pos: dict,
    speed_factor: float,
    margin_s: float,
    with_approaches: bool = False,
    pursuer_speed_factor: float = 1.0,
):
    """Safe region, gates, and per-pursuer node times.

    The safe region is CONNECTED from the evader: the evader's search does not continue through a
    junction a pursuer reaches first (r02). The first version kept every junction the evader
    reached first by any path, including paths through pursuer-held junctions, and drew safe
    regions far from a boxed-in evader (F1 r01 GIF)."""
    per = {}
    t_p: dict[str, float] = {}
    for vid, pos in pursuer_pos.items():
        dist, prev = reach.from_edge(*pos, speed_factor=pursuer_speed_factor)
        per[vid] = (reach.node_times(dist), dist, prev)
        for n, t in per[vid][0].items():
            if t < t_p.get(n, float("inf")):
                t_p[n] = t
    net = reach.net
    edge, offset = evader_pos
    info = net.edges[edge]
    start = max(0.0, info.length_m - offset) / (info.speed_cap_mps * speed_factor)
    t_e: dict[str, float] = {}
    safe: set[str] = set()
    gates: set[str] = set()
    approaches: dict[str, set[str]] = {}
    heap = [(start, edge)]
    seen: dict[str, float] = {edge: start}
    while heap:
        d, e = heapq.heappop(heap)
        if d > seen.get(e, float("inf")) + 1e-9:
            continue
        n = net.edges[e].to_node
        t_e[n] = min(t_e.get(n, float("inf")), d)
        if d + margin_s >= t_p.get(n, float("inf")):
            gates.add(n)  # a pursuer holds it first: the evader's search stops here
            approaches.setdefault(n, set()).add(e)  # A-88: the edge the evader would enter it by
            continue
        safe.add(n)
        for s in reach.succ.get(e, ()):
            link = net.links[(e, s)]
            cost = link.via_length_m / max(link.via_speed_mps * speed_factor, 0.1)
            cost += net.edges[s].length_m / (net.edges[s].speed_cap_mps * speed_factor)
            if d + cost < seen.get(s, float("inf")) - 1e-9:
                seen[s] = d + cost
                heapq.heappush(heap, (d + cost, s))
    gates -= safe
    if with_approaches:
        return safe, gates, t_e, per, {g: approaches.get(g, set()) for g in gates}
    return safe, gates, t_e, per


def lane_held(gates, approaches, lane_states, evader_state, hold_speed_mps, lanes_of):
    """A-88 lane-level holding: a gate is held only if, on every edge by which the evader would
    enter it, EVERY lane carries a pursuer at <= hold_speed_mps that is ahead of the evader when
    the evader is on that edge. `lane_states`: {pursuer: (edge, lane_id, lane_pos, speed)};
    `evader_state` likewise; `lanes_of(edge)` -> lane ids."""
    held = set()
    for g in gates:
        ok = bool(approaches.get(g))
        for a in approaches.get(g, ()):
            for lane in lanes_of(a):
                blocked = any(
                    st[1] == lane
                    and st[3] <= hold_speed_mps
                    and (evader_state[0] != a or st[2] > evader_state[2])
                    for st in lane_states.values()
                )
                if not blocked:
                    ok = False
                    break
            if not ok:
                break
        if ok:
            held.add(g)
    return held


def _edge_into(node, dist, prev_unused, net):
    """The edge ending at `node` with the earliest arrival (the pursuer's approach)."""
    best = None
    for e, d in dist.items():
        if net.edges[e].to_node == node and (best is None or d < best[0]):
            best = (d, e)
    return None if best is None else best[1]


def plan_commands(strategy, reach: Reach, safe, gates, t_e, per, evader_edge, net, previous=None):
    """Commands ("seg", target_edge, None) per pursuer: drive to the edge into the chosen node,
    stop at its end.

    `previous` (F3, A-73): the last assignment. A pursuer KEEPS its previous gate while that
    junction is still a gate and it can still reach it before the evader; only the others are
    re-assigned. Without it targets were re-chosen every second and 45 % of F2's runs had hard
    braking. `previous=None` reproduces F1/F2 exactly."""
    commands = {}
    pursuers = sorted(per)
    if strategy == "pursuit" or not gates:
        for vid in pursuers:
            commands[vid] = ("seg", evader_edge, None)
        return commands, {}
    urgent = sorted(gates, key=lambda g: (t_e.get(g, float("inf")), g))
    assignment: dict[str, str] = {}
    if previous:
        for vid, g in sorted(previous.items()):
            if (
                vid in per
                and g in gates
                and per[vid][0].get(g, float("inf")) <= t_e.get(g, float("inf"))
                and (strategy != "cut" or g not in assignment.values())
            ):
                assignment[vid] = g
    if strategy == "cut":
        free = [v for v in pursuers if v not in assignment]
        taken = set(assignment.values())
        for g in urgent:
            if g in taken:
                continue
            if not free:
                break
            vid = min(free, key=lambda v: (per[v][0].get(g, float("inf")), v))
            assignment[vid] = g
            free.remove(vid)
        for vid in free:
            commands[vid] = ("seg", evader_edge, None)
    else:  # individual
        for vid in pursuers:
            if vid in assignment:
                continue
            times = per[vid][0]
            assignment[vid] = max(
                urgent, key=lambda g: (t_e.get(g, 0.0) - times.get(g, float("inf")), g)
            )
    for vid, g in assignment.items():
        edge = _edge_into(g, per[vid][1], per[vid][2], net)
        commands[vid] = ("seg", edge, None) if edge else ("seg", evader_edge, None)
    return commands, assignment
