"""Can a pursuer, with SUMO's safety checks ON, close to within the capture band at all?

Collision DETECTION and car-following are separate in SUMO. Setting the collision
mingap-factor to 0 changes what is reported; it does not change how close the follower's
own safe-speed logic lets it come. This measures the smallest bumper gap reached.
"""

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


def main() -> int:
    import sumolib

    domain = load_domain()
    vehicle = domain["vehicle"]
    record = training_map(None)
    net = sumolib.net.readNet(record["path"])
    lane = next(
        lane
        for edge in sorted(net.getEdges(), key=lambda e: e.getID())
        if edge.allows("passenger") and not edge.isSpecial()
        for lane in edge.getLanes()
        if lane.getLength() > 80.0 and lane.allows("passenger")
    )
    backend = TraciBackend(
        record["path"], seed=20260924, step_s=0.1,
        sumo_binary=os.environ.get("SUMO_BINARY") or "sumo", label="approach",
        collision_action="warn", extra_args=["--collision.mingap-factor", "0"],
    )
    rows = []
    try:
        conn = backend._connection
        backend.add_route("r0", [lane.getEdge().getID()])
        length = vehicle["body_length_m"]
        for vid, depart in (("pursuer", 0.0), ("evader", 40.0)):
            backend.add_vehicle(
                vid, "r0", type_id="DEFAULT_VEHTYPE", depart_position_m=depart,
                depart_speed_mps=0.0, body_length_m=length,
                body_width_m=vehicle["body_width_m"], min_gap_m=vehicle["min_gap_m"],
            )
        for _ in range(50):
            backend.step(1)
            if {"pursuer", "evader"} <= set(conn.vehicle.getIDList()):
                break
        conn.vehicle.setSpeed("evader", 0.0)
        conn.vehicle.moveTo("evader", lane.getID(), 60.0)
        conn.vehicle.moveTo("pursuer", lane.getID(), 20.0)
        smallest = float("inf")
        for step in range(400):
            conn.vehicle.setSpeed("pursuer", 5.0)
            backend.step(1)
            gap = (conn.vehicle.getLanePosition("evader") - length
                   - conn.vehicle.getLanePosition("pursuer"))
            smallest = min(smallest, gap)
            if step % 50 == 0 or conn.vehicle.getSpeed("pursuer") < 1e-6:
                rows.append({"step": step, "gap_m": round(gap, 4),
                             "pursuer_speed_mps": round(conn.vehicle.getSpeed("pursuer"), 4)})
            if conn.vehicle.getSpeed("pursuer") < 1e-6 and step > 20:
                break
        result = {"speed_mode": conn.vehicle.getSpeedMode("pursuer"),
                  "min_gap_m": vehicle["min_gap_m"],
                  "smallest_bumper_gap_reached_m": round(smallest, 4),
                  "capture_band_m": [0.30, 2.00],
                  "reached_capture_band": 0.30 <= smallest <= 2.00,
                  "trace": rows}
    finally:
        backend.close()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "approach_results.json")
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "trace"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
