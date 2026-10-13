"""X03 (exploratory): first divergence of the model evader from the SUMO closed-loop evader."""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from joint_interception.domain.contracts import load_domain  # noqa: E402
from joint_interception.simulator.evader import EvaderLevel  # noqa: E402
from joint_interception.validation.diagnostic_set import run_model  # noqa: E402
from joint_interception.validation.sumo_replay import replay  # noqa: E402
from joint_interception.world.construction import Plan, Segment, make_scenario  # noqa: E402
from joint_interception.world.network import GraphNetwork  # noqa: E402

SUMO = "/Library/Frameworks/Python.framework/Versions/3.10/bin/sumo"
N03 = "experiments/20260926_w04_native_replication_n03_keepclear"


def main() -> int:
    import sumolib

    package = sys.argv[1]
    domain = load_domain()
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as h:
        paths = {m["map_id"]: m["path"] for m in json.load(h)["maps"]}
    with open(os.path.join(ROOT, N03, "results.jsonl"), encoding="utf-8") as h:
        rows = [json.loads(line) for line in h]
    out = []
    for r in rows:
        if not r["rejected"]:
            continue
        mid = r["map_id"]
        x = r["rejected"][0]
        net = GraphNetwork.from_sumo(paths[mid])
        snet = sumolib.net.readNet(paths[mid], withInternal=True)
        sc = make_scenario(
            net, mid, EvaderLevel[r["level"]], domain["team"]["pursuer_ids"], r["salt"]
        )
        plan = Plan({k: [Segment(**s) for s in v] for k, v in x["plan"].items()})
        run = run_model(net, sc, plan, domain, "factual")
        rec = replay(run, net, snet, paths[mid], domain, SUMO, closed_loop=True, label=f"d{mid}")
        model_route = run.routes["e1"]
        sumo_route = rec.evader_route
        k = next(
            (i for i, (a, b) in enumerate(zip(model_route, sumo_route, strict=False)) if a != b),
            None,
        )
        model_decisions = [
            {"t": d.decision_index, "edge": d.current_edge, "chosen": d.chosen}
            for d in run.world.evader.decisions
        ]
        # the time each evader reached the edge where the routes split
        split_edge = model_route[k - 1] if k else None
        t_model = next(
            (i * 0.1 for i, s in enumerate(run.states) if s["e1"][0] == split_edge), None
        )
        t_sumo = next(
            (i * 0.1 for i, s in enumerate(rec.states) if "e1" in s and s["e1"][0] == split_edge),
            None,
        )
        row = {
            "map_id": mid,
            "model_witness_start_s": x["factual"]["witness_start_s"],
            "routes_split_at_index": k,
            "split_after_edge": split_edge,
            "model_next": model_route[k] if k is not None and k < len(model_route) else None,
            "sumo_next": sumo_route[k] if k is not None and k < len(sumo_route) else None,
            "evader_on_split_edge_model_s": round(t_model, 1) if t_model is not None else None,
            "evader_on_split_edge_sumo_s": round(t_sumo, 1) if t_sumo is not None else None,
            "model_decisions": model_decisions[:12],
            "sumo_route_prefix": sumo_route[:12],
        }
        out.append(row)
        print(json.dumps(row)[:700], flush=True)
    with open(os.path.join(ROOT, package, "results.jsonl"), "w", encoding="utf-8") as h:
        for row in out:
            h.write(json.dumps(row) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
