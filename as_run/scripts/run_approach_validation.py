"""Validate the signal-aware approach model against SUMO.

Runs each route with speed control RELEASED, so SUMO drives as fast as it legally can, and
compares that against the model's computed earliest arrival. A model that is EARLIER than
SUMO's best is optimistic and does not earn UNDER, whatever its accuracy.
"""

import json
import os
import statistics
import sys

ROOT = "/Volumes/SSD Mac/PHD/Union/doctoral_joint_interception"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)
import sumolib  # noqa: E402

from approach_extract import build_segments, signal_programs  # noqa: E402
from joint_interception.domain.contracts import load_domain  # noqa: E402
from joint_interception.opportunities.approach import earliest_arrival_on_approach  # noqa: E402
from joint_interception.simulator.sumo_adapter import TraciBackend  # noqa: E402
from run_constructive_on_network import INVALID_DOUBLE, build  # noqa: E402
from run_constructive_replication import TRAINING_MAPS, map_record, pick_routes  # noqa: E402

SB = "/Library/Frameworks/Python.framework/Versions/3.10/bin/sumo"
dom = load_domain()
step = dom["timing"]["physical_step_s"]


def drive_free(backend, vid, target_distance, max_steps):
    """Release speed control entirely: let SUMO drive as fast as it legally can."""
    origin = backend._connection.vehicle.getDistance(vid)
    backend._connection.vehicle.setSpeed(vid, -1)
    for _ in range(max_steps):
        if vid not in backend._connection.vehicle.getIDList():
            return {"arrived": False, "reason": "left network"}
        cov = backend._connection.vehicle.getDistance(vid) - origin
        if cov == INVALID_DOUBLE:
            return {"arrived": False, "reason": "sentinel"}
        if cov >= target_distance:
            return {"arrived": True, "time_s": backend.time_s, "covered_m": cov}
        backend.step(1)
    return {"arrived": False, "reason": "budget"}


rows = []
for mid in TRAINING_MAPS:
    rec = map_record(mid)
    net = sumolib.net.readNet(rec["path"], withInternal=True, withPrograms=True)
    progs = signal_programs(net)
    p = TraciBackend(rec["path"], seed=20260924, step_s=step, sumo_binary=SB, label=f"p_{mid}")
    try:
        routes = pick_routes(p, rec["path"], 3, 6)
    finally:
        p.close()
    for ri, edges in enumerate(routes):
        b = TraciBackend(
            rec["path"], seed=20260924, step_s=step, sumo_binary=SB, label=f"v_{mid}_{ri}"
        )
        try:
            build(b, edges, dom, ["p1"])
            si = max(1, int(len(edges) * 0.6))
            se = edges[si]
            spos = b._connection.lane.getLength(f"{se}_0") * 0.5
            dist = b._connection.vehicle.getDrivingDistance("p1", se, spos)
            if not dist or dist <= 0 or dist > 1e6:
                continue
            obs = drive_free(b, "p1", dist, int(900.0 / step))
        finally:
            b.close()
        segs, mdist = build_segments(net, edges, se, spos)
        r = earliest_arrival_on_approach(segs, progs, 0.0, 2.6, 4.5)
        rows.append(
            {
                "map": mid,
                "route": ri,
                "segments": len(segs),
                "internal": sum(1 for s in segs if s.is_internal),
                "signalled": sum(1 for s in segs if s.signal),
                "sumo_distance_m": round(dist, 2),
                "model_distance_m": round(mdist, 2),
                "model_earliest_s": round(r["time_s"], 3),
                "signal_waits": len(r["signal_waits"]),
                "total_wait_s": r["total_wait_s"],
                "converged": r["stop_set_converged"],
                "sumo_free_arrival_s": round(obs["time_s"], 3) if obs.get("arrived") else None,
                "model_minus_sumo_s": round(r["time_s"] - obs["time_s"], 3)
                if obs.get("arrived")
                else None,
            }
        )
out_path = os.environ.get("OUT", "approach_validation.json")
with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(rows, handle, indent=1)

ok = [r for r in rows if r["model_minus_sumo_s"] is not None]
d = [r["model_minus_sumo_s"] for r in ok]
print(f"{'map':20s} {'rt':>2s} {'sig':>3s} {'wait':>7s} {'model':>9s} {'sumo':>9s} {'m-s':>9s}")
for r in ok:
    print(
        f"{r['map']:20s} {r['route']:2d} {r['signalled']:3d} "
        f"{r['total_wait_s']:7.1f} {r['model_earliest_s']:9.2f} "
        f"{r['sumo_free_arrival_s']:9.2f} {r['model_minus_sumo_s']:+9.3f}"
    )
print()
print(
    f"n={len(d)}  model - SUMO free run:  min {min(d):+.3f}  "
    f"median {statistics.median(d):+.3f}  max {max(d):+.3f}"
)
under = sum(1 for x in d if x >= -0.1)
print(f"model UNDER-approximates (model >= sumo free run) in {under}/{len(d)} routes")
