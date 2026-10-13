"""Ambush-planner study (A-94): does an explicit lane-level cooperative planner produce synergy?

On 7 real cities (equal speeds, D06 primary), every scenario is played by the ambush planner with
the full team, by pursuit with the full team, and by the ambush planner with each single pursuer
alone (same start; the same planner, which with one pursuer can only close junctions whose exits
have a single lane). Synergy = team − [1 − Π(1 − p_i)] over the ambush singles. Resumable in chunks
(the background-task time limit is 30 min).
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from audit_cage_certificate import replay  # noqa: E402
from run_endpoint_validation import DEVELOPMENT, TRAINING, immobilised_at  # noqa: E402
from run_final_study import trap_type  # noqa: E402
from run_robustness_study import bootstrap  # noqa: E402
from train_caging_pilot import _init_worker  # noqa: E402

LEVELS = ["AVOIDANT", "RANDOM"]
TEAMS = [3, 5]
IDS = ["p1", "p2", "p3", "p4", "p5"]
SALT = "PA1"


def task(args):
    map_id, index, rep, level, team, policy, single = args
    key = {
        "map_id": map_id,
        "index": index,
        "rep": rep,
        "level": level,
        "team": team,
        "policy": policy if single is None else f"{policy}_only_{single}",
    }
    try:
        ep, recs = replay(
            map_id,
            index,
            9500 + index + 100000 * rep,
            SALT,
            "T",
            None,
            "policy",
            300.0,
            kind=policy,
            speed=1.0,
            active=None if single is None else [single],
            level=level,
            team=team,
        )
    except Exception as error:  # noqa: BLE001
        return key | {"failed": f"{type(error).__name__}: {str(error)[:160]}"}
    compact = [
        {
            "t": r["t"],
            "v": r["v_e"],
            "leader": r["leader"],
            "follower": r["follower"],
            "signal": r["signal"],
            "edge": r["edge"],
        }
        for r in recs
    ]
    t_imm = immobilised_at(compact, 10.0, 15.0, 30.0)
    trapped = t_imm is not None or ep.contact_capture
    stats = getattr(ep, "planner_stats", None)
    return key | {
        "d06": ep.contact_capture,
        "trapped": trapped,
        "trap_type": None
        if not trapped
        else (trap_type(compact, t_imm, map_id) if t_imm is not None else "CONTACT_ONLY"),
        "plan_share": None
        if not stats
        else round(stats["steps_with_plan"] / max(1, stats["steps"]), 3),
        "plans": None if not stats else stats["plans"],
        "evader_exited": ep.evader_exited,
        "collided": ep.collided,
    }


def tasks_for(scenarios, reps):
    out = []
    for m in TRAINING + DEVELOPMENT:
        for i in range(scenarios):
            for rep in range(reps):
                for level in LEVELS:
                    for team in TEAMS:
                        out.append((m, i, rep, level, team, "ambush", None))
                        out.append((m, i, rep, level, team, "pursuit", None))
                        for s in IDS[:team]:
                            out.append((m, i, rep, level, team, "ambush", s))
    return out


def _key(r):
    return (r["map_id"], r["index"], r["rep"], r["level"], r["team"], r["policy"])


def _task_key(t):
    m, i, rep, level, team, policy, single = t
    return (m, i, rep, level, team, policy if single is None else f"{policy}_only_{single}")


def analyse(package):
    with open(os.path.join(package, "results.jsonl"), encoding="utf-8") as h:
        rows = [json.loads(x) for x in h]
    good = [r for r in rows if "failed" not in r]
    acc = {}
    for r in good:
        acc.setdefault((r["level"], r["team"], r["policy"], r["map_id"], r["index"]), []).append(r)

    def rate(level, team, policy, field="d06"):
        return {
            (m, i): sum(float(x[field]) for x in rs) / len(rs)
            for (lv, t, p, m, i), rs in acc.items()
            if (lv, t, p) == (level, team, policy)
        }

    cells = [(lv, t) for lv in LEVELS for t in TEAMS]
    out = {"episodes": len(rows), "failed": len(rows) - len(good), "cells": {}}
    for level, team in cells:
        amb = rate(level, team, "ambush")
        pur = rate(level, team, "pursuit")
        singles = [rate(level, team, f"ambush_only_{s}") for s in IDS[:team]]
        ks = sorted(set(amb).intersection(pur, *singles))
        union = [1 - math.prod(1 - s[k] for s in singles) for k in ks]
        syn = [amb[k] - u for k, u in zip(ks, union, strict=True)]
        share = rate(level, team, "ambush", "plan_share")
        out["cells"][f"{level}_team{team}"] = {
            "scenarios": len(ks),
            "ambush_team_d06": bootstrap([amb[k] for k in ks]),
            "pursuit_team_d06": bootstrap([pur[k] for k in ks]),
            "ambush_single_mean_d06": bootstrap([sum(s[k] for s in singles) / team for k in ks]),
            "independent_union": bootstrap(union),
            "S1_synergy": bootstrap(syn),
            "S1_synergy_bonferroni": bootstrap(syn, alpha=0.05 / len(cells)),
            "S2_ambush_minus_pursuit": bootstrap([amb[k] - pur[k] for k in ks]),
            "ambush_plan_share": bootstrap([share[k] for k in ks if k in share]),
        }
        c = out["cells"][f"{level}_team{team}"]
        c["cooperation_detected"] = c["S1_synergy_bonferroni"][1] > 0
    out["any_cooperation_detected"] = any(c["cooperation_detected"] for c in out["cells"].values())
    types = {}
    for r in good:
        if r["trapped"] and not r["policy"].startswith("ambush_only"):
            k = f"{r['level']}_team{r['team']}_{r['policy']}"
            types.setdefault(k, {}).setdefault(r["trap_type"], 0)
            types[k][r["trap_type"]] += 1
    out["trap_types"] = types
    out["collisions"] = sum(r["collided"] for r in good)
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--phase", choices=["run", "analyse"], required=True)
    parser.add_argument("--scenarios", type=int, default=20)
    parser.add_argument("--reps", type=int, default=2)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-episodes", type=int, default=None)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    if args.phase == "run":
        tasks = tasks_for(args.scenarios, args.reps)
        path = os.path.join(package, "results.jsonl")
        seen = set()
        if os.path.exists(path):
            with open(path, encoding="utf-8") as h:
                seen = {_key(json.loads(x)) for x in h}
        total = len(tasks)
        tasks = [t for t in tasks if _task_key(t) not in seen]
        if args.max_episodes is not None:
            tasks = tasks[: args.max_episodes]
        print(
            json.dumps({"phase": "run", "total": total, "already": len(seen), "chunk": len(tasks)})
        )
        with (
            mp.get_context("spawn").Pool(args.workers, initializer=_init_worker) as pool,
            open(path, "a", encoding="utf-8") as h,
        ):
            for row in pool.imap_unordered(task, tasks, chunksize=4):
                h.write(json.dumps(row) + "\n")
                h.flush()
        if len(seen) + len(tasks) < total:
            print(json.dumps({"phase": "chunk_done", "remaining": total - len(seen) - len(tasks)}))
            return 0
    out = analyse(package)
    print(
        json.dumps(
            {"phase": "analyse", "any_cooperation_detected": out["any_cooperation_detected"]}
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
