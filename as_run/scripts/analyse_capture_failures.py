"""X02 (exploratory): classify the A-47 gate's non-reproduced captures by mechanism."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from joint_interception.domain.contracts import load_domain  # noqa: E402
from joint_interception.validation.diagnostic_set import generate  # noqa: E402
from joint_interception.validation.sumo_replay import replay  # noqa: E402
from joint_interception.world.network import GraphNetwork  # noqa: E402

SUMO = "/Library/Frameworks/Python.framework/Versions/3.10/bin/sumo"
GATE = "experiments/20260926_w04_model_validation_r01"


def first_on(states, vid, edge, sumo):
    for k, st in enumerate(states):
        if vid in st:
            here = st[vid][0]
            if here == edge and (sumo or st[vid][1] is None):
                return round(k * 0.1, 1)
    return None


def main() -> int:
    import sumolib

    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    args = parser.parse_args()
    domain = load_domain()
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as h:
        paths = {m["map_id"]: m["path"] for m in json.load(h)["maps"]}
    with open(os.path.join(ROOT, GATE, "results.jsonl"), encoding="utf-8") as h:
        rows = [json.loads(line) for line in h]
    out = []
    for r in rows:
        if not r["model_capture"] or r["m3"][0]["reproduced"]:
            continue
        mid = r["map_id"]
        net = GraphNetwork.from_sumo(paths[mid])
        snet = sumolib.net.readNet(paths[mid], withInternal=True)
        run = generate(net, mid, r["index"], domain, domain["team"]["pursuer_ids"])
        rec = replay(run, net, snet, paths[mid], domain, SUMO, label=f"f{mid}{r['index']}")
        f = run.capture["finisher"]
        tw = run.capture["witness_start_s"]
        k = int(round(tw / 0.1))
        m, s = run.states[k], rec.states[min(k, len(rec.states) - 1)]
        edge = m[f][0]
        sf, se = s.get(f), s.get("e1")
        row = {
            "map_id": mid,
            "index": r["index"],
            "kind": run.kind,
            "sumo_judge": r["m3"][0]["sumo_verdict"],
            "sumo_finisher": r["m3"][0]["sumo_finisher"],
            "blocking_edge": edge,
            "blocking_edge_lanes": net.edges[edge].lanes,
            "model": {
                "finisher_on_edge_s": first_on(run.states, f, edge, False),
                "evader_on_edge_s": first_on(run.states, "e1", edge, False),
            },
            "sumo": {
                "finisher_on_edge_s": first_on(rec.states, f, edge, True),
                "evader_on_edge_s": first_on(rec.states, "e1", edge, True),
            },
            "sumo_at_witness": {
                "finisher": [sf[0], sf[8], round(sf[2], 1), round(sf[3], 2)] if sf else None,
                "evader": [se[0], se[8], round(se[2], 1), round(se[3], 2)] if se else None,
            },
            "sumo_lane_changes": {k2: len(v) for k2, v in rec.lane_changes.items()},
            "sumo_collisions": len(rec.collisions),
        }
        mo, so = row["model"], row["sumo"]
        if so["evader_on_edge_s"] is None:
            mode = "SUMO evader never reaches the blocking edge"
        elif so["finisher_on_edge_s"] is None:
            mode = "SUMO finisher never reaches the blocking edge"
        elif (
            so["evader_on_edge_s"]
            < so["finisher_on_edge_s"]
            <= (mo["finisher_on_edge_s"] or 0) + 99
        ):
            mode = "SUMO evader reaches the blocking edge before the finisher"
        elif sf and se and sf[0] == se[0] == edge and se[2] > sf[2]:
            mode = "SUMO evader ahead of the finisher on the blocking edge (overtook)"
        elif r["m3"][0]["sumo_verdict"] == "SUPPORTED":
            mode = "SUMO captures, but earlier/later or by another pursuer"
        else:
            mode = "both on the edge in order, no dwell (gap or speed outside band)"
        row["mode"] = mode
        out.append(row)
        print(json.dumps(row), flush=True)
    counts = {}
    for row in out:
        counts[row["mode"]] = counts.get(row["mode"], 0) + 1
    with open(os.path.join(ROOT, args.package, "results.jsonl"), "w", encoding="utf-8") as h:
        for row in out:
            h.write(json.dumps(row) + "\n")
    with open(os.path.join(ROOT, args.package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump({"failures": len(out), "modes": counts}, h, indent=2)
    print(json.dumps(counts, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
