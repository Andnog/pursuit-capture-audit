"""Commitment study (A-106): does holding lane orders for commit_s seconds improve the optimised
planner? Pre-registered replication of the incidental A-105 finding, with a dose-response.

The A-99 planner (c2_15) with commit_s in {1, 2, 3, 5} on fresh scenarios (salt PE14), 7 cities,
20 scenarios x 2 SUMO seeds, evader AVOIDANT / RANDOM, teams 3 / 5 / 7, full 300 s, D06.
Primary: commit 3 s - commit 1 s, pooled, bootstrap CI lower bound > 0. Resumable chunks.
"""

from __future__ import annotations

import argparse
import json
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
from run_sensitivity_study import episode  # noqa: E402

COMMITS = [1.0, 2.0, 3.0, 5.0]


def tasks(c215):
    out = []
    for m in TRAINING + DEVELOPMENT:
        for i in range(20):
            for rep in range(2):
                seed = 9500 + i + 100000 * rep
                for level in ("AVOIDANT", "RANDOM"):
                    for team in (3, 5, 7):
                        for c in COMMITS:
                            p = dict(c215)
                            p["commit_s"] = c
                            out.append(
                                (
                                    f"C|{c}|{m}|{i}|{seed}|{level}|{team}",
                                    m,
                                    i,
                                    seed,
                                    "PE14",
                                    level,
                                    team,
                                    "ambush_plus",
                                    p,
                                    1.0,
                                    True,
                                )
                            )
    return out


def summarise(package, store):
    by = {}
    for k, r in store.rows.items():
        if "failed" in r:
            continue
        _, c, m, i, seed, level, team = k.split("|")
        by.setdefault((float(c), level, int(team), m, int(i)), []).append(float(r["d06"]))
    mean = {k: sum(v) / len(v) for k, v in by.items()}

    def per(c, cells=None):
        return {
            k[1:]: v
            for k, v in mean.items()
            if k[0] == c and (cells is None or (k[1], k[2]) in cells)
        }

    base = per(1.0)
    out = {"rates": {}, "vs_commit1": {}, "cells": {}}
    for c in COMMITS:
        x = per(c)
        ks = sorted(set(x).intersection(base))
        out["rates"][str(c)] = bootstrap([x[k] for k in ks])
        out["vs_commit1"][str(c)] = bootstrap([x[k] - base[k] for k in ks])
    for level in ("AVOIDANT", "RANDOM"):
        for team in (3, 5, 7):
            b, t3 = per(1.0, {(level, team)}), per(3.0, {(level, team)})
            ks = sorted(set(b).intersection(t3))
            out["cells"][f"{level}_team{team}"] = {
                "commit1": bootstrap([b[k] for k in ks]),
                "commit3": bootstrap([t3[k] for k in ks]),
                "diff": bootstrap([t3[k] - b[k] for k in ks]),
            }
    p = out["vs_commit1"]["3.0"]
    out["primary_commit3_minus_commit1"] = p
    out["primary_passes"] = p[1] > 0
    out["failed"] = sum(1 for r in store.rows.values() if "failed" in r)
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
    with open(
        os.path.join(ROOT, "experiments", "20261002_ambush_optimization_r01", "summary.json"),
        encoding="utf-8",
    ) as h:
        c215 = json.load(h)["final_params"]
    store = Store(package)
    ts = tasks(c215)
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        done = store.run(pool, ts, time.time() + 60 * args.budget_min, episode)
    n = sum(1 for t in ts if t[0] in store.rows)
    print(json.dumps({"done": n, "of": len(ts)}), flush=True)
    if done:
        out = summarise(package, store)
        print(json.dumps({"primary": out["primary_commit3_minus_commit1"], "rates": out["rates"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
