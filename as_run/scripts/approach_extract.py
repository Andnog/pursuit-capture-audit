"""Build an approach model from a SUMO network: the chain of lanes a route actually uses.

Includes the INTERNAL junction lanes the edges connect through, which A-42 showed the
earlier speed-limit calculation ignored, and the signal guarding each controlled entry.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from joint_interception.opportunities.approach import Segment, SignalProgram  # noqa: E402


def signal_programs(net) -> dict[str, SignalProgram]:
    """Read every fixed-time program from the network."""
    out: dict[str, SignalProgram] = {}
    for tls in net.getTrafficLights():
        programs = tls.getPrograms()
        if not programs:
            continue
        program = next(iter(programs.values()))
        phases = program.getPhases()
        if not phases:
            continue
        out[tls.getID()] = SignalProgram(
            tls_id=tls.getID(),
            phase_durations=tuple(float(p.duration) for p in phases),
            phase_states=tuple(p.state for p in phases),
            offset=float(getattr(program, "offset", 0.0) or 0.0),
        )
    return out


def _connection(net, from_edge: str, to_edge: str):
    try:
        outgoing = net.getEdge(from_edge).getOutgoing()
    except KeyError:
        return None
    if not isinstance(outgoing, dict):
        return None
    for edge, connections in outgoing.items():
        if edge.getID() == to_edge and connections:
            return connections[0]
    return None


def build_segments(net, route_edges: list[str], station_edge: str, station_pos_m: float):
    """Ordered lanes from the route start to the station, internal lanes included.

    Returns `(segments, distance_m)`. The distance is the sum of the segment lengths, so it
    is the distance the MODEL believes it is covering; a caller comparing against SUMO's own
    driving distance should compare the two rather than assume they agree.
    """
    segments: list[Segment] = []
    total = 0.0

    for index, edge_id in enumerate(route_edges):
        try:
            edge = net.getEdge(edge_id)
        except KeyError:
            continue
        lane = min(edge.getLanes(), key=lambda lane: lane.getSpeed())
        length = lane.getLength()
        if edge_id == station_edge:
            length = min(length, station_pos_m)
            segments.append(Segment(lane.getID(), length, lane.getSpeed()))
            total += length
            break
        segments.append(Segment(lane.getID(), length, lane.getSpeed()))
        total += length

        if index + 1 < len(route_edges):
            connection = _connection(net, edge_id, route_edges[index + 1])
            if connection is None:
                continue
            via = connection.getViaLaneID()
            tls_id = connection.getTLSID()
            link_index = connection.getTLLinkIndex()
            signal = (
                (tls_id, link_index)
                if tls_id and link_index is not None and link_index >= 0
                else None
            )
            if via:
                try:
                    via_lane = net.getLane(via)
                except KeyError:
                    continue
                segments.append(
                    Segment(via, via_lane.getLength(), via_lane.getSpeed(), True, signal)
                )
                total += via_lane.getLength()
            elif signal is not None and segments:
                last = segments[-1]
                segments[-1] = Segment(
                    last.lane_id, last.length_m, last.speed_limit_mps, last.is_internal, signal
                )
    return segments, total
