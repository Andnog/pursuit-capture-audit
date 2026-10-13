"""Stage B3 (A-66): coordination as a capture-probability difference, in SUMO.

Per scenario: (1) deterministic native search collects plans whose capture needs the helper;
(2) up to 3 of them are screened on 10 selection seeds (sigma 0.5), with and without the helper,
and the one with the highest capture count is kept; (3) the kept plan is estimated on 20 FRESH
seeds, with and without the helper (paired by seed). Per map: mean paired difference over
scenarios and a scenario-cluster bootstrap 95% interval.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

SUMO = "/Library/Frameworks/Python.framework/Versions/3.10/bin/sumo"
SELECTION_SEEDS = [2000 + k for k in range(1, 11)]
ESTIMATION_SEEDS = [5000 + k for k in range(1, 21)]
SIGMA = 0.5


def _path(map_id):
    with open(os.path.join(ROOT, "assets", "controlled", "manifest.json"), encoding="utf-8") as h:
        m = json.load(h)
    if map_id in m:
        return os.path.join(ROOT, m[map_id]["path"])
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as h:
        return {x["map_id"]: x["path"] for x in json.load(h)["maps"]}[map_id]


def task(args):
    map_id, level_name, index, salt, budget, package, screen = args
    from joint_interception.domain.contracts import load_domain
    from joint_interception.native.engine import run_plan, search_scenario
    from joint_interception.simulator.evader import EvaderLevel
    from joint_interception.world.construction import Plan, Segment, make_scenario
    from joint_interception.world.network import GraphNetwork

    domain = load_domain()
    path = _path(map_id)
    net = GraphNetwork.from_sumo(path)
    sc = make_scenario(
        net, map_id, EvaderLevel[level_name], domain["team"]["pursuer_ids"], f"{salt}s{index}"
    )
    tag = f"{map_id[:3]}{level_name[:1]}{index}"
    res = search_scenario(net, path, sc, domain, SUMO, budget, robustness_seeds=0, label=tag + "_")
    row = {
        "map_id": map_id,
        "level": level_name,
        "index": index,
        "scenario_seed": sc.seed,
        "plans_tried": res.plans_tried,
        "captures": res.captures,
        "labels": res.labels,
        "necessary_found": len(res.necessary),
        "search_cpu_s": res.cpu_seconds,
    }
    if not res.necessary:
        return row

    def captures(plan, seeds, t):
        return [
            run_plan(
                net, path, sc, plan, domain, SUMO, sigma=SIGMA, seed=s, label=f"{tag}{t}{s}"
            ).verdict.verdict.value
            == "SUPPORTED"
            for s in seeds
        ]

    screened = []
    for n, c in enumerate(res.necessary[:screen]):
        plan = Plan({k: [Segment(**s) for s in v] for k, v in c["plan"].items()})
        absent = Plan({k: v for k, v in plan.segments.items() if k != c["helper"]})
        w = captures(plan, SELECTION_SEEDS, f"w{n}")
        wo = captures(absent, SELECTION_SEEDS, f"o{n}")
        screened.append(
            {
                "candidate": n,
                "label": c["label"],
                "helper": c["helper"],
                "finisher": c["finisher"],
                "with": sum(w),
                "without": sum(wo),
                "plan": c["plan"],
            }
        )
    best = max(screened, key=lambda x: (x["with"] - x["without"], x["with"], -x["candidate"]))
    plan = Plan({k: [Segment(**s) for s in v] for k, v in best["plan"].items()})
    absent = Plan({k: v for k, v in plan.segments.items() if k != best["helper"]})
    w = captures(plan, ESTIMATION_SEEDS, "W")
    wo = captures(absent, ESTIMATION_SEEDS, "O")
    row.update(
        {
            "screened": [{k: v for k, v in x.items() if k != "plan"} for x in screened],
            "selected": {k: v for k, v in best.items() if k != "plan"},
            "selected_plan": best["plan"],
            "estimate": {
                "with": w,
                "without": wo,
                "p_with": sum(w) / len(w),
                "p_without": sum(wo) / len(wo),
                "delta": (sum(w) - sum(wo)) / len(w),
            },
        }
    )
    return row


def bootstrap(deltas, reps=10000, seed=7):
    if not deltas:
        return None, None, None
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(deltas) for _ in deltas) / len(deltas) for _ in range(reps))
    return sum(deltas) / len(deltas), means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--maps", nargs="+", required=True)
    parser.add_argument("--extra", nargs="*", default=[])
    parser.add_argument("--scenarios", type=int, default=8)
    parser.add_argument("--budget", type=float, required=True)
    parser.add_argument("--salt", required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--screen", type=int, default=3, help="candidates screened per scenario")
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    if os.path.isfile(os.path.join(package, "checksums.json")):
        print("REFUSED: sealed", file=sys.stderr)
        return 2
    pairs = [(m, "AVOIDANT") for m in args.maps] + [tuple(x.split(":")) for x in args.extra]
    tasks = [
        (m, lv, i, args.salt, args.budget, package, args.screen)
        for m, lv in pairs
        for i in range(args.scenarios)
    ]
    rows = []
    with (
        mp.get_context("spawn").Pool(args.workers) as pool,
        open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as out,
    ):
        for row in pool.imap_unordered(task, tasks):
            rows.append(row)
            out.write(json.dumps(row) + "\n")
            out.flush()
            e = row.get("estimate")
            print(
                row["map_id"],
                row["level"],
                row["index"],
                "necessary",
                row["necessary_found"],
                "delta",
                None if e is None else round(e["delta"], 2),
                flush=True,
            )
    summary = {}
    for m, lv in pairs:
        rs = [r for r in rows if r["map_id"] == m and r["level"] == lv]
        deltas = [r["estimate"]["delta"] for r in rs if "estimate" in r]
        mean, lo, hi = bootstrap(deltas)
        summary[f"{m}:{lv}"] = {
            "scenarios": len(rs),
            "with_necessary_plan": len(deltas),
            "p_with_mean": round(
                sum(r["estimate"]["p_with"] for r in rs if "estimate" in r) / max(1, len(deltas)), 3
            ),
            "p_without_mean": round(
                sum(r["estimate"]["p_without"] for r in rs if "estimate" in r)
                / max(1, len(deltas)),
                3,
            ),
            "delta_mean": None if mean is None else round(mean, 3),
            "delta_ci95": None if lo is None else [round(lo, 3), round(hi, 3)],
            "passes": lo is not None and lo > 0 and len(deltas) >= 4,
        }
    avoidant = [
        r["estimate"]["delta"] for r in rows if r["level"] == "AVOIDANT" and "estimate" in r
    ]
    mean, lo, hi = bootstrap(avoidant)
    summary["POOLED_AVOIDANT"] = {
        "contributing_scenarios": len(avoidant),
        "scenarios": sum(1 for r in rows if r["level"] == "AVOIDANT"),
        "delta_mean": None if mean is None else round(mean, 3),
        "delta_ci95": None if lo is None else [round(lo, 3), round(hi, 3)],
        "passes": lo is not None and lo > 0 and len(avoidant) >= 20,
    }
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(summary, h, indent=2)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
