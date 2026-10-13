"""Two stationary vehicles at forced bumper gaps; read SUMO's own collision report."""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from joint_interception.domain.contracts import load_domain  # noqa: E402
from joint_interception.simulator.sumo_adapter import TraciBackend  # noqa: E402
from run_traci_first_execution import training_map  # noqa: E402

GAPS = (3.0, 2.6, 2.4, 2.0, 1.0, 0.30)


def probe(extra_args, tag, record, vehicle, sumo_binary):
    import sumolib

    net = sumolib.net.readNet(record["path"])
    lane = next(
        lane
        for edge in sorted(net.getEdges(), key=lambda e: e.getID())
        if edge.allows("passenger") and not edge.isSpecial()
        for lane in edge.getLanes()
        if lane.getLength() > 80.0 and lane.allows("passenger")
    )
    lane_id, edge_id = lane.getID(), lane.getEdge().getID()
    rows = []
    backend = TraciBackend(
        record["path"], seed=20260924, step_s=0.1, sumo_binary=sumo_binary,
        label=f"coll_{tag}", collision_action="warn", extra_args=extra_args,
    )
    try:
        conn = backend._connection
        backend.add_route("r0", [edge_id])
        length = vehicle["body_length_m"]
        for index, gap in enumerate(GAPS):
            follower, leader = f"f{index}", f"l{index}"
            # Distinct, well-separated departures, so both can actually be inserted. The
            # void first run departed both at 0 and the second was never on the network.
            for vid, depart in ((follower, 0.0), (leader, 40.0)):
                backend.add_vehicle(
                    vid, "r0", type_id="DEFAULT_VEHTYPE", depart_position_m=depart,
                    depart_speed_mps=0.0, body_length_m=length,
                    body_width_m=vehicle["body_width_m"], min_gap_m=vehicle["min_gap_m"],
                )
            for _ in range(50):
                backend.step(1)
                live = set(conn.vehicle.getIDList())
                if {follower, leader} <= live:
                    break
            live = set(conn.vehicle.getIDList())
            if not {follower, leader} <= live:
                rows.append({"arm": tag, "intended_gap_m": gap, "valid": False,
                             "reason": "a vehicle was never inserted"})
                continue
            follower_front = 20.0
            leader_front = follower_front + length + gap
            for vid, pos in ((follower, follower_front), (leader, leader_front)):
                conn.vehicle.setSpeed(vid, 0.0)
                conn.vehicle.moveTo(vid, lane_id, pos)
            backend.step(1)
            measured = (
                conn.vehicle.getLanePosition(leader) - length
                - conn.vehicle.getLanePosition(follower)
            )
            collisions = conn.simulation.getCollisions()
            mine = [c for c in collisions if {c.collider, c.victim} & {follower, leader}]
            rows.append({
                "arm": tag, "intended_gap_m": gap, "measured_gap_m": round(measured, 6),
                "valid": abs(measured - gap) <= 0.05,
                "inside_capture_band": 0.30 <= gap <= 2.00,
                "below_min_gap": gap < vehicle["min_gap_m"],
                "sumo_reported_collision": bool(mine),
                "collision_types": sorted({c.type for c in mine}),
            })
            for vid in (follower, leader):
                if vid in conn.vehicle.getIDList():
                    conn.vehicle.remove(vid)
            backend.step(1)
    finally:
        backend.close()
    return rows


def main() -> int:
    domain = load_domain()
    record = training_map(None)
    sumo_binary = os.environ.get("SUMO_BINARY") or "sumo"
    rows = probe(None, "A_defaults", record, domain["vehicle"], sumo_binary)
    rows += probe(["--collision.mingap-factor", "0"], "B_mingap_factor_0", record, domain["vehicle"], sumo_binary)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.jsonl")
    with open(out, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    for row in rows:
        print(json.dumps(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
