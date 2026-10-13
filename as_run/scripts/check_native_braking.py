"""Post-hoc: SUMO emergency braking in accepted native constructions (decel > 4.5 m/s^2 + 0.05)."""

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


def hard_braking(rec, limit=4.5 * 0.1 + 0.05):
    out = []
    for k in range(1, len(rec.states)):
        for vid, s in rec.states[k].items():
            p = rec.states[k - 1].get(vid)
            if p is not None and p[3] - s[3] > limit:
                out.append(
                    {"t": round(k * 0.1, 1), "vid": vid, "decel": round((p[3] - s[3]) / 0.1, 2)}
                )
    return out


def main() -> int:
    import sumolib

    package = sys.argv[1]
    domain = load_domain()
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as h:
        paths = {m["map_id"]: m["path"] for m in json.load(h)["maps"]}
    report = []
    with open(os.path.join(ROOT, package, "results.jsonl"), encoding="utf-8") as h:
        rows = [json.loads(line) for line in h]
    for r in rows:
        if r["verdict"] != "NATIVE_CONSTRUCTED":
            continue
        mid = r["map_id"]
        net = GraphNetwork.from_sumo(paths[mid])
        snet = sumolib.net.readNet(paths[mid], withInternal=True)
        sc = make_scenario(
            net, mid, EvaderLevel[r["level"]], domain["team"]["pursuer_ids"], r["salt"]
        )
        plan = Plan({k: [Segment(**s) for s in v] for k, v in r["result"]["plan"].items()})
        helper = r["result"]["d12"]["helper"]
        b = r["result"]["d12"]["intervention_decisions"][0]
        arms = {
            "factual": (plan, None),
            "b1": (plan, (helper, b, b + 5)),
            "helper_never_acts": (
                Plan({k: v for k, v in plan.segments.items() if k != helper}),
                None,
            ),
        }
        for arm, (p, b1) in arms.items():
            run = run_model(net, sc, p, domain, arm, b1)
            for loop in ("open", "closed"):
                rec = replay(
                    run,
                    net,
                    snet,
                    paths[mid],
                    domain,
                    SUMO,
                    closed_loop=loop == "closed",
                    label=f"hb{mid}{arm}{loop}",
                )
                hb = hard_braking(rec)
                report.append(
                    {
                        "map_id": mid,
                        "arm": arm,
                        "loop": loop,
                        "hard_braking_steps": len(hb),
                        "first": hb[:3],
                    }
                )
                print(report[-1], flush=True)
    with open(os.path.join(ROOT, package, "post_hoc_braking.json"), "w", encoding="utf-8") as h:
        json.dump(report, h, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
