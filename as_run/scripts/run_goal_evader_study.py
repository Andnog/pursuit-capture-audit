"""Goal-directed evader study (A-112, pre-registered).

Seven non-TEST cities (salt PE16), GOAL_DIRECTED evader, 20 scenarios x 2 SUMO seeds x teams 3/5/7 x
{PLB c2_15, A-95 ambush, pursuit}, plus PLB singles p1..p7 (team-7 placement). D06 primary; the PLB
predictor's next-turn hit rate is recorded. Resumable chunks (--budget-min).
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from run_ambush_optimization import Store, _init  # noqa: E402
from run_endpoint_validation import DEVELOPMENT, TRAINING  # noqa: E402
from run_robustness_study import bootstrap  # noqa: E402

LEVEL, SALT = "GOAL_DIRECTED", "PE16"
TEAMS, METHODS = [3, 5, 7], ["plus_opt", "ambush_a95", "pursuit"]
A99 = os.path.join(ROOT, "experiments", "20261002_ambush_optimization_r01", "summary.json")


def episode(args):
    from audit_cage_certificate import replay

    key, m, i, seed, team, method, single = args
    with open(A99, encoding="utf-8") as h:
        c215 = json.load(h)["final_params"]
    kind = {"plus_opt": "ambush_plus", "ambush_a95": "ambush", "pursuit": "pursuit"}[method]
    try:
        ep, _ = replay(
            m,
            i,
            seed,
            SALT,
            "T",
            None,
            "policy",
            300.0,
            kind=kind,
            speed=1.0,
            level=LEVEL,
            team=team,
            learner={"params": c215} if kind == "ambush_plus" else None,
            active=None if single is None else [single],
            reward_mode="certificate",
        )
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    st = getattr(ep, "planner_stats", {}) or {}
    return {
        "key": key,
        "d06": bool(ep.contact_capture),
        "collided": ep.collided,
        "evader_exited": ep.evader_exited,
        "pred_hits": st.get("pred_hits"),
        "pred_total": st.get("pred_total"),
    }


def tasks():
    out = []
    for m in TRAINING + DEVELOPMENT:
        for i in range(20):
            for rep in range(2):
                seed = 9500 + i + 100000 * rep
                base = f"{m}|{i}|{seed}"
                for team in TEAMS:
                    for method in METHODS:
                        out.append((f"GD|{method}|{base}|{team}", m, i, seed, team, method, None))
                for k in range(1, 8):
                    out.append(
                        (f"GS|plus_opt_only_p{k}|{base}|7", m, i, seed, 7, "plus_opt", f"p{k}")
                    )
    return out


def summarise(package, store):
    def table(block):
        by = {}
        for k, r in store.rows.items():
            p = k.split("|")
            if p[0] != block or "failed" in r:
                continue
            _, method, m, i, _seed, team = p
            by.setdefault((method, int(team), m, int(i)), []).append(float(r["d06"]))
        return {k: sum(v) / len(v) for k, v in by.items()}

    gd, gs = table("GD"), table("GS")

    def per(tab, method, team):
        return {k[2:]: v for k, v in tab.items() if k[:2] == (method, team)}

    out = {"cells": {}, "failed": sum("failed" in r for r in store.rows.values())}
    pooled = []
    for team in TEAMS:
        r = {mt: per(gd, mt, team) for mt in METHODS}
        ks = sorted(set.intersection(*(set(r[mt]) for mt in METHODS)))
        sg = [per(gs, f"plus_opt_only_p{j}", 7) for j in range(1, team + 1)]
        ks2 = [k for k in ks if all(k in s for s in sg)]
        union = [1 - math.prod(1 - s[k] for s in sg) for k in ks2]
        syn = [r["plus_opt"][k] - u for k, u in zip(ks2, union, strict=True)]
        out["cells"][f"team{team}"] = {
            "n": len(ks),
            **{mt: bootstrap([r[mt][k] for k in ks]) for mt in METHODS},
            "opt_minus_pursuit": bootstrap([r["plus_opt"][k] - r["pursuit"][k] for k in ks]),
            "opt_minus_a95": bootstrap([r["plus_opt"][k] - r["ambush_a95"][k] for k in ks]),
            "single_mean": bootstrap([sum(s[k] for s in sg) / team for k in ks2]),
            "synergy": bootstrap(syn),
            "synergy_bonferroni": bootstrap(syn, alpha=0.05 / 3),
        }
        pooled += [r["plus_opt"][k] - r["pursuit"][k] for k in ks]
    out["primary_opt_minus_pursuit_pooled"] = bootstrap(pooled)
    out["primary_passes"] = bool(pooled) and out["primary_opt_minus_pursuit_pooled"][1] > 0
    hits = [
        (r["pred_hits"], r["pred_total"])
        for k, r in store.rows.items()
        if k.startswith("GD|plus_opt") and "failed" not in r and r.get("pred_total")
    ]
    out["plb_predictor_hit_rate"] = round(sum(h for h, _ in hits) / sum(t for _, t in hits), 3)
    out["evader_exited"] = {
        mt: round(
            sum(
                r["evader_exited"]
                for k, r in store.rows.items()
                if k.startswith(f"GD|{mt}|") and "failed" not in r
            )
            / max(
                1,
                sum(
                    1
                    for k, r in store.rows.items()
                    if k.startswith(f"GD|{mt}|") and "failed" not in r
                ),
            ),
            3,
        )
        for mt in METHODS
    }
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    deadline = time.time() + 60 * args.budget_min
    store = Store(package)
    todo = tasks()
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        if not store.run(pool, todo, deadline, episode):
            done = sum(t[0] in store.rows for t in todo)
            print(json.dumps({"stage": "chunk_done", "done": done, "of": len(todo)}), flush=True)
            return 0
    out = summarise(package, store)
    print(json.dumps({"stage": "done", "primary": out["primary_opt_minus_pursuit_pooled"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
