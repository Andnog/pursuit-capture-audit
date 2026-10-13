"""Post-hoc (A-69): joint plan vs its best single pursuer, on a probability-stage package.

For every selected plan: P(capture | full plan) and, for each participant i, P(capture | only i
acts; the others park off-lane), on the same 20 estimation seeds (sigma 0.5). Joint effect
Delta_joint = P(full) - max_i P(only i). Credit only to the acting pursuers (A-68 judge).
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
SUMO = "/Library/Frameworks/Python.framework/Versions/3.10/bin/sumo"
SEEDS = [5000 + k for k in range(1, 21)]


def task(row):
    from joint_interception.domain.contracts import load_domain
    from joint_interception.native.engine import run_plan
    from joint_interception.simulator.evader import EvaderLevel
    from joint_interception.world.construction import Plan, Segment, make_scenario
    from joint_interception.world.network import GraphNetwork

    domain = load_domain()
    with open(os.path.join(ROOT, "assets", "controlled", "manifest.json"), encoding="utf-8") as h:
        path = os.path.join(ROOT, json.load(h)[row["map_id"]]["path"])
    net = GraphNetwork.from_sumo(path)
    sc = make_scenario(
        net,
        row["map_id"],
        EvaderLevel[row["level"]],
        domain["team"]["pursuer_ids"],
        f"{row['salt']}s{row['index']}",
    )
    full = Plan({k: [Segment(**s) for s in v] for k, v in row["selected_plan"].items()})

    def p(plan, tag):
        return sum(
            run_plan(
                net,
                path,
                sc,
                plan,
                domain,
                SUMO,
                sigma=0.5,
                seed=s,
                label=f"j{row['map_id'][:3]}{row['index']}{tag}{s}",
            ).verdict.verdict.value
            == "SUPPORTED"
            for s in SEEDS
        ) / len(SEEDS)

    singles = {i: p(Plan({i: full.segments[i]}), i) for i in sorted(full.segments)}
    p_full = row["estimate"]["p_with"]
    return {
        "map_id": row["map_id"],
        "index": row["index"],
        "participants": sorted(full.segments),
        "p_full": p_full,
        "p_single": singles,
        "delta_joint": p_full - max(singles.values()),
        "delta_helper_removed": row["estimate"]["delta"],
    }


def bootstrap(xs, reps=10000, seed=7):
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(reps))
    return sum(xs) / len(xs), means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def main() -> int:
    package, salt = sys.argv[1], sys.argv[2]
    with open(os.path.join(ROOT, package, "results.jsonl"), encoding="utf-8") as h:
        rows = [dict(json.loads(line), salt=salt) for line in h]
    rows = [r for r in rows if "estimate" in r]
    with mp.get_context("spawn").Pool(8) as pool:
        out = pool.map(task, rows)
    with open(
        os.path.join(ROOT, package, "post_hoc_joint_vs_individual.jsonl"), "w", encoding="utf-8"
    ) as h:
        for r in out:
            h.write(json.dumps(r) + "\n")
    summary = {}
    for m in sorted({r["map_id"] for r in out}) + ["POOLED"]:
        xs = [r["delta_joint"] for r in out if m == "POOLED" or r["map_id"] == m]
        mean, lo, hi = bootstrap(xs)
        summary[m] = {
            "n": len(xs),
            "delta_joint": round(mean, 3),
            "ci95": [round(lo, 3), round(hi, 3)],
            "positive": sum(x > 0 for x in xs),
            "zero": sum(x == 0 for x in xs),
            "negative": sum(x < 0 for x in xs),
        }
    with open(
        os.path.join(ROOT, package, "post_hoc_joint_vs_individual_summary.json"),
        "w",
        encoding="utf-8",
    ) as h:
        json.dump(summary, h, indent=2)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
