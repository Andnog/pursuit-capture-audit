"""Acceptance test of the D06 remedy (A-46) in SUMO, with the independent capture judge."""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from joint_interception.domain.contracts import (  # noqa: E402
    CaptureParameters,
    load_domain,
    min_gap_for,
    simulator_arguments,
)
from joint_interception.evaluation.capture_judge import (  # noqa: E402
    TraceFrame,
    VehicleFrame,
    judge_capture,
)
from joint_interception.simulator.sumo_adapter import TraciBackend  # noqa: E402
from run_traci_first_execution import training_map  # noqa: E402

DOMAIN = load_domain()
STEP = DOMAIN["timing"]["physical_step_s"]
VEH = DOMAIN["vehicle"]


def straight_lane(record):
    import sumolib

    net = sumolib.net.readNet(record["path"])
    return next(
        lane
        for edge in sorted(net.getEdges(), key=lambda e: e.getID())
        if edge.allows("passenger") and not edge.isSpecial()
        for lane in edge.getLanes()
        if lane.getLength() > 120.0 and lane.allows("passenger")
    )


def start(record, tag):
    return TraciBackend(
        record["path"], seed=20260924, step_s=STEP,
        sumo_binary=os.environ.get("SUMO_BINARY") or "sumo", label=f"remedy_{tag}",
        collision_action="warn", extra_args=simulator_arguments(DOMAIN),
    )


def place(backend, lane, specs):
    conn = backend._connection
    backend.add_route("r0", [lane.getEdge().getID()])
    for vid, klass, depart in specs:
        backend.add_vehicle(
            vid, "r0", type_id="DEFAULT_VEHTYPE", depart_position_m=depart,
            depart_speed_mps=0.0, body_length_m=VEH["body_length_m"],
            body_width_m=VEH["body_width_m"], min_gap_m=min_gap_for(klass, DOMAIN),
        )
        backend.assign_class(vid, klass)
    wanted = {vid for vid, _, _ in specs}
    for _ in range(80):
        backend.step(1)
        if wanted <= set(conn.vehicle.getIDList()):
            return True
    return False


def frame(backend, ids):
    vehicles = {}
    for vid in ids:
        s = backend.vehicle_state(vid)
        vehicles[vid] = VehicleFrame(vid, s.x, s.y, s.heading_rad, s.speed_mps,
                                     s.body_length_m, s.body_width_m)
    return TraceFrame(round(backend.time_s, 6), vehicles)


def bumper_gap(backend, leader, follower):
    conn = backend._connection
    return (conn.vehicle.getLanePosition(leader) - conn.vehicle.getLength(leader)
            - conn.vehicle.getLanePosition(follower))


def approach(backend, lane, closer, target, steps=500):
    """Stop `target`; command `closer` to 5 m/s; record the trace until it rests."""
    conn = backend._connection
    conn.vehicle.setSpeed(target, 0.0)
    conn.vehicle.moveTo(target, lane.getID(), 90.0)
    conn.vehicle.moveTo(closer, lane.getID(), 40.0)
    trace, collisions, smallest, rested_at = [], [], float("inf"), None
    for step in range(steps):
        conn.vehicle.setSpeed(closer, 5.0)
        backend.step(1)
        gap = bumper_gap(backend, target, closer)
        smallest = min(smallest, gap)
        trace.append(frame(backend, [closer, target]))
        collisions += [(c.collider, c.victim) for c in conn.simulation.getCollisions()]
        if rested_at is None and conn.vehicle.getSpeed(closer) < 1e-6 and step > 20:
            rested_at = step
        if rested_at is not None and step - rested_at >= 40:
            break
    return {"smallest_gap_m": round(smallest, 4),
            "rest_gap_m": round(bumper_gap(backend, target, closer), 4),
            "collisions": collisions, "trace": trace}


def main() -> int:
    record = training_map(None)
    lane = straight_lane(record)
    params = CaptureParameters.from_domain(DOMAIN)
    band = (params.contact_gap_min_m, params.contact_gap_max_m)
    out = {"simulator_arguments": simulator_arguments(DOMAIN),
           "min_gap_by_class": VEH["min_gap_m_by_class"], "capture_band_m": band}

    b = start(record, "arm1")
    try:
        assert place(b, lane, [("pursuer", "pursuer", 0.0), ("evader", "evader", 60.0)])
        r = approach(b, lane, closer="pursuer", target="evader")
        verdict = judge_capture(r["trace"], "evader", params, STEP)
        out["arm1_pursuer_trails_evader"] = {
            "rest_gap_m": r["rest_gap_m"], "smallest_gap_m": r["smallest_gap_m"],
            "outside_band": r["smallest_gap_m"] > band[1], "collisions": r["collisions"],
            "judge": verdict.verdict.value, "judge_reason": verdict.reason}
    finally:
        b.close()

    b = start(record, "arm2")
    try:
        assert place(b, lane, [("evader", "evader", 0.0), ("pursuer", "pursuer", 60.0)])
        r = approach(b, lane, closer="evader", target="pursuer")
        verdict = judge_capture(r["trace"], "evader", params, STEP)
        out["arm2_evader_stops_behind_pursuer"] = {
            "rest_gap_m": r["rest_gap_m"], "inside_band": band[0] <= r["rest_gap_m"] <= band[1],
            "collisions": r["collisions"], "judge": verdict.verdict.value,
            "judge_reason": verdict.reason, "witness_duration_s": verdict.witness_duration_s}
    finally:
        b.close()

    b = start(record, "arm3")
    try:
        assert place(b, lane, [("a", "pursuer", 0.0), ("b", "evader", 60.0)])
        conn = b._connection
        for vid in ("a", "b"):
            conn.vehicle.setSpeed(vid, 0.0)
        conn.vehicle.moveTo("b", lane.getID(), 50.0)
        conn.vehicle.moveTo("a", lane.getID(), 48.0)
        b.step(1)
        coll = [(c.collider, c.victim) for c in conn.simulation.getCollisions()]
        out["arm3_forced_overlap_control"] = {"bumper_gap_m": round(bumper_gap(b, "b", "a"), 4),
                                              "collision_reported": bool(coll), "collisions": coll}
    finally:
        b.close()

    a1, a2, a3 = (out["arm1_pursuer_trails_evader"], out["arm2_evader_stops_behind_pursuer"],
                  out["arm3_forced_overlap_control"])
    failed = []
    if not (a1["outside_band"] and not a1["collisions"]):
        failed.append("arm1")
    if not (a2["inside_band"] and not a2["collisions"] and a2["judge"] == "SUPPORTED"):
        failed.append("arm2")
    if not a3["collision_reported"]:
        failed.append("arm3")
    out["verdict"] = "REMEDY_VERIFIED" if not failed else "REMEDY_FAILED"
    out["failed_arms"] = failed
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "result_raw.json"), "w",
              encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
