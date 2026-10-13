"""Robustness study for publication (A-92). Equal speeds; primary endpoint D06 contact capture.

Blocks (package PROTOCOL_EN.md):
- F, factorial on 7 real cities without background traffic: evader level (RANDOM, AVOIDANT,
  OPTIMAL_ESCAPE) x team size (2, 3, 5). Runs: pursuit team, cut team, and pursuit by each single
  pursuer alone (same start). 20 scenarios per city x 3 SUMO seeds.
- T, background traffic: AVOIDANT, team 3, same scenarios and seeds as F, with ~300 random-trip
  cars per city (assets/background_traffic).
- L, literature-like regime: controlled grids C2 6x6 and C3 9x9, RANDOM evader, team 5, pursuit
  and cut, 60 scenarios x 3 seeds; lenient (5 m, 10 m) vs strict endpoints.
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from audit_cage_certificate import replay  # noqa: E402
from run_endpoint_validation import DEVELOPMENT, TRAINING, immobilised_at  # noqa: E402
from run_final_study import trap_type  # noqa: E402
from train_caging_pilot import _init_worker  # noqa: E402

LEVELS = ["RANDOM", "AVOIDANT", "OPTIMAL_ESCAPE"]
TEAMS = [2, 3, 5]
CITIES = TRAINING + DEVELOPMENT
GRIDS = ["C2_grid6x6", "C3_grid9x9"]
IDS = ["p1", "p2", "p3", "p4", "p5"]
SALT = "PR1"


def seed_of(index, rep):
    return 9500 + index + 100000 * rep


def task(args):
    block, map_id, index, rep, level, team, policy, single, traffic = args
    key = {
        "block": block,
        "map_id": map_id,
        "index": index,
        "rep": rep,
        "level": level,
        "team": team,
        "policy": policy if single is None else f"{policy}_only_{single}",
        "traffic": traffic,
    }
    extra = None
    if traffic:
        extra = ["-r", os.path.join(ROOT, "assets", "background_traffic", f"{map_id}.rou.xml")]
    try:
        ep, recs = replay(
            map_id,
            index,
            seed_of(index, rep),
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
            extra_sumo_args=extra,
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
    # Lenient proximity endpoints. Primary: BODY-to-body gap (every D06 capture is within it);
    # also centre-to-centre distance (SUMO positions; a car 1 m behind another is ~6 m away).
    from joint_interception.domain.geometry import body_separation_m

    min_d, near, centre5 = math.inf, {5.0: False, 10.0: False}, False
    for f in ep.trace:
        e = f.vehicles.get("e1")
        if e is None:
            continue
        for v, p in f.vehicles.items():
            if v == "e1":
                continue
            c = math.dist((e.x, e.y), (p.x, p.y))
            centre5 = centre5 or c <= 5.0
            if c > 16.0:
                continue
            d = body_separation_m(e.rectangle(), p.rectangle())
            min_d = min(min_d, d)
            for th in near:
                near[th] = near[th] or d <= th
    trapped = t_imm is not None or ep.contact_capture
    return key | {
        "d06": ep.contact_capture,
        "trapped": trapped,
        "trap_type": None
        if not trapped
        else (trap_type(compact, t_imm, map_id) if t_imm is not None else "CONTACT_ONLY"),
        "prox_5m": near[5.0],
        "prox_10m": near[10.0],
        "prox_5m_centre": centre5,
        "min_body_gap_m": None if min_d == math.inf else round(min_d, 2),
        "evader_exited": ep.evader_exited,
        "collided": ep.collided,
        "end_s": ep.end_s,
    }


def _task_key(t):
    block, map_id, index, rep, level, team, policy, single, traffic = t
    name = policy if single is None else f"{policy}_only_{single}"
    return (block, map_id, index, rep, level, team, name, traffic)


def _key(r):
    return (
        r["block"],
        r["map_id"],
        r["index"],
        r["rep"],
        r["level"],
        r["team"],
        r["policy"],
        r["traffic"],
    )


def tasks_for(scenarios, grid_scenarios, reps):
    out = []
    for m in CITIES:
        for i in range(scenarios):
            for rep in range(reps):
                for level in LEVELS:
                    for team in TEAMS:
                        for p in ("pursuit", "cut"):
                            out.append(("F", m, i, rep, level, team, p, None, False))
                        for s in IDS[:team]:
                            out.append(("F", m, i, rep, level, team, "pursuit", s, False))
                for p in ("pursuit", "cut"):
                    out.append(("T", m, i, rep, "AVOIDANT", 3, p, None, True))
                for s in IDS[:3]:
                    out.append(("T", m, i, rep, "AVOIDANT", 3, "pursuit", s, True))
    for m in GRIDS:
        for i in range(grid_scenarios):
            for rep in range(reps):
                for p in ("pursuit", "cut"):
                    out.append(("L", m, i, rep, "RANDOM", 5, p, None, False))
    return out


def bootstrap(xs, reps=10000, seed=7, alpha=0.05):
    if not xs:
        return None
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(reps))
    lo, hi = int(alpha / 2 * reps), int((1 - alpha / 2) * reps) - 1
    return [round(sum(xs) / len(xs), 3), round(means[lo], 3), round(means[hi], 3)]


def analyse(package):
    with open(os.path.join(package, "results.jsonl"), encoding="utf-8") as h:
        rows = [json.loads(x) for x in h]
    good = [r for r in rows if "failed" not in r]
    # Seed-averaged rate per (block, level, team, traffic, policy, map, index).
    acc = {}
    for r in good:
        k = (r["block"], r["level"], r["team"], r["traffic"], r["policy"], r["map_id"], r["index"])
        acc.setdefault(k, []).append(r)

    def rate(block, level, team, traffic, policy, field):
        out = {}
        for (b, lv, t, tr, p, m, i), rs in acc.items():
            if (b, lv, t, tr, p) == (block, level, team, traffic, policy):
                out[(m, i)] = sum(float(x[field]) for x in rs) / len(rs)
        return out

    n_cells = len(LEVELS) * len(TEAMS) + 1
    alpha_adj = 0.05 / n_cells
    summary = {
        "episodes": len(rows),
        "failed": len(rows) - len(good),
        "bonferroni_cells": n_cells,
        "cells": {},
    }
    cells = [("F", lv, t, False) for lv in LEVELS for t in TEAMS] + [("T", "AVOIDANT", 3, True)]
    for block, level, team, traffic in cells:
        singles = [
            rate(block, level, team, traffic, f"pursuit_only_{s}", "d06") for s in IDS[:team]
        ]
        tm = rate(block, level, team, traffic, "pursuit", "d06")
        cut = rate(block, level, team, traffic, "cut", "d06")
        ks = sorted(set(tm).intersection(cut, *singles))
        union = [1 - math.prod(1 - s[k] for s in singles) for k in ks]
        best = [max(s[k] for s in singles) for k in ks]
        mean = [sum(s[k] for s in singles) / team for k in ks]
        team_r = [tm[k] for k in ks]
        syn = [a - b for a, b in zip(team_r, union, strict=True)]
        p5 = rate(block, level, team, traffic, "pursuit", "prox_5m")
        trp = rate(block, level, team, traffic, "pursuit", "trapped")
        name = f"{block}_{level}_team{team}{'_traffic' if traffic else ''}"
        summary["cells"][name] = {
            "scenarios": len(ks),
            "pursuit_team_d06": bootstrap(team_r),
            "cut_team_d06": bootstrap([cut[k] for k in ks]),
            "single_mean_d06": bootstrap(mean),
            "independent_union_d06": bootstrap(union),
            "R1_synergy_team_minus_union": bootstrap(syn),
            "R1_synergy_bonferroni_ci": bootstrap(syn, alpha=alpha_adj),
            "team_minus_best_single": bootstrap([a - b for a, b in zip(team_r, best, strict=True)]),
            "team_minus_mean_single": bootstrap([a - b for a, b in zip(team_r, mean, strict=True)]),
            "R2_pursuit_minus_cut": bootstrap([tm[k] - cut[k] for k in ks]),
            "R3_prox5_minus_d06_pursuit": bootstrap([p5[k] - tm[k] for k in ks]),
            "pursuit_prox5": bootstrap([p5[k] for k in ks]),
            "pursuit_trapped": bootstrap([trp[k] for k in ks]),
        }
        c = summary["cells"][name]
        c["cooperation_detected"] = c["R1_synergy_bonferroni_ci"][1] > 0
    summary["any_cooperation_detected"] = any(
        c["cooperation_detected"] for c in summary["cells"].values()
    )
    # R4 traffic effect (paired, AVOIDANT team 3).
    a = rate("F", "AVOIDANT", 3, False, "pursuit", "d06")
    b = rate("T", "AVOIDANT", 3, True, "pursuit", "d06")
    ks = sorted(set(a).intersection(b))
    summary["R4_traffic_minus_no_traffic_pursuit_d06"] = bootstrap([b[k] - a[k] for k in ks])
    # L literature-like regime.
    lit = {}
    for p in ("pursuit", "cut"):
        for f in ("prox_5m", "prox_10m", "prox_5m_centre", "d06", "trapped"):
            r = rate("L", "RANDOM", 5, False, p, f)
            lit[f"{p}_{f}"] = bootstrap(list(r.values()))
        r5, rd = (
            rate("L", "RANDOM", 5, False, p, "prox_5m"),
            rate("L", "RANDOM", 5, False, p, "d06"),
        )
        lit[f"{p}_prox5_minus_d06"] = bootstrap([r5[k] - rd[k] for k in r5 if k in rd])
    summary["L_literature_like"] = lit
    # Trap-type composition per cell (pursuit team), pooled over seeds.
    comp = {}
    for r in good:
        if r["policy"] in ("pursuit", "cut") and r["trapped"]:
            k = f"{r['block']}_{r['level']}_team{r['team']}{'_traffic' if r['traffic'] else ''}"
            comp.setdefault(f"{k}_{r['policy']}", {}).setdefault(r["trap_type"], 0)
            comp[f"{k}_{r['policy']}"][r["trap_type"]] += 1
    summary["trap_types"] = comp
    summary["collisions"] = sum(r["collided"] for r in good)
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(summary, h, indent=2)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--phase", choices=["run", "analyse"], required=True)
    parser.add_argument("--scenarios", type=int, default=20, help="per city")
    parser.add_argument("--grid-scenarios", type=int, default=60)
    parser.add_argument("--reps", type=int, default=3)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--max-episodes",
        type=int,
        default=None,
        help="run at most this many pending episodes, then stop (resumable chunks)",
    )
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    if args.phase == "run":
        tasks = tasks_for(args.scenarios, args.grid_scenarios, args.reps)
        path = os.path.join(package, "results.jsonl")
        # Resumable: episodes already recorded are skipped (the background-task time limit
        # stops long runs; every episode is deterministic, so chunks compose exactly).
        seen = set()
        if os.path.exists(path):
            with open(path, encoding="utf-8") as h:
                for line in h:
                    r = json.loads(line)
                    seen.add(_key(r))
        total = len(tasks)
        tasks = [t for t in tasks if _task_key(t) not in seen]
        if args.max_episodes is not None:
            tasks = tasks[: args.max_episodes]
        print(
            json.dumps(
                {"phase": "run", "total": total, "already": len(seen), "this_chunk": len(tasks)}
            ),
            flush=True,
        )
        done = 0
        with (
            mp.get_context("spawn").Pool(args.workers, initializer=_init_worker) as pool,
            open(path, "a", encoding="utf-8") as h,
        ):
            for row in pool.imap_unordered(task, tasks, chunksize=4):
                h.write(json.dumps(row) + "\n")
                done += 1
                if done % 1000 == 0:
                    h.flush()
                    print(json.dumps({"progress": done, "of": len(tasks)}), flush=True)
        if len(seen) + done < total:
            print(json.dumps({"phase": "chunk_done", "remaining": total - len(seen) - done}))
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
