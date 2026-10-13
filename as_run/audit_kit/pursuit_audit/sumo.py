"""Optional helpers for SUMO through TraCI. Nothing here is imported by the scoring code.

Each function takes an open TraCI connection (or the `traci` module); the caller owns the
simulation. SUMO reports the FRONT-bumper position and a compass angle; `frame` converts both.
"""

from __future__ import annotations

from .geometry import Body, centre_from_front, heading_from_compass_deg
from .trace import Frame


def frame(conn, vehicle_ids, default_width_m: float = 1.8) -> Frame:
    """One trace frame for the listed vehicles, read from the running simulation."""
    vehicles = {}
    present = set(conn.vehicle.getIDList())
    for vid in vehicle_ids:
        if vid not in present:
            continue  # a missing vehicle breaks any witness; it is never filled in
        fx, fy = conn.vehicle.getPosition(vid)
        heading = heading_from_compass_deg(conn.vehicle.getAngle(vid))
        length = conn.vehicle.getLength(vid)
        try:
            width = conn.vehicle.getWidth(vid)
        except Exception:  # noqa: BLE001 - older TraCI versions
            width = default_width_m
        x, y = centre_from_front(fx, fy, heading, length)
        vehicles[vid] = Body(x, y, heading, conn.vehicle.getSpeed(vid), length, width)
    return Frame(float(conn.simulation.getTime()), vehicles)


def hold_audit(conn, pursuer_ids, evader_id: str, follow_s: float = 60.0, escape_m: float = 10.0):
    """Hold every pursuer and follow the evader: does a declared capture persist?

    Call it at the instant a capture is declared. Every pursuer is ordered to stand still; the
    simulation is advanced for `follow_s` seconds; the evader has escaped if it travels more than
    `escape_m`. A study should report the follow-up actually completed for every capture: if the
    simulation ends first, the case is censored, not a success.
    """
    for pid in pursuer_ids:
        if pid in conn.vehicle.getIDList():
            conn.vehicle.setSpeed(pid, 0.0)
    start_t = conn.simulation.getTime()
    start_d = conn.vehicle.getDistance(evader_id)
    travelled, escaped_at = 0.0, None
    while conn.simulation.getTime() - start_t < follow_s - 1e-9:
        conn.simulationStep()
        if evader_id not in conn.vehicle.getIDList():
            return {
                "followed_s": conn.simulation.getTime() - start_t,
                "complete": False,
                "evader_left_simulation": True,
                "travelled_m": travelled,
                "escaped": True,
            }
        travelled = conn.vehicle.getDistance(evader_id) - start_d
        if travelled > escape_m and escaped_at is None:
            escaped_at = conn.simulation.getTime() - start_t
    return {
        "followed_s": conn.simulation.getTime() - start_t,
        "complete": True,
        "evader_left_simulation": False,
        "travelled_m": travelled,
        "escaped": escaped_at is not None,
        "escaped_after_s": escaped_at,
    }
