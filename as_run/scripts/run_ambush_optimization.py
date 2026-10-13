"""Gradient-free optimisation of the pre-positioning ambush (A-98), then a pre-registered test.

Search (TRAINING cities, success = trapped or D06, episodes end at trapping):
- generation 1: 32 random configurations + the defaults, successive halving 48 -> 144 -> 384
  episodes (8 then 3 survivors);
- circuit breaker: if the best configuration does not beat the defaults by >= 0.02 on round 3,
  generation 2 is skipped and the defaults are kept;
- generation 2: 16 Gaussian perturbations of the best + the best + the defaults, same halving;
- validation: best vs defaults on fresh scenarios.
Test (fresh scenarios, 7 cities, full 300 s, D06): optimised and default pre-positioning ambush,
A-95 ambush, pursuit, and the optimised planner with each single pursuer alone (synergy), evader
AVOIDANT / RANDOM, teams 3, 5, 7. Resumable: each invocation works for at most --budget-min.
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import pickle
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from run_endpoint_validation import DEVELOPMENT, TRAINING  # noqa: E402
from run_robustness_study import bootstrap  # noqa: E402

SETTINGS = [("AVOIDANT", 3), ("AVOIDANT", 5), ("RANDOM", 3), ("RANDOM", 5)]
ROUNDS = [(3, 8), (9, 3), (24, 1)]  # (scenarios per city x setting, survivors)
SPACE = {
    "depth": ("int", 2, 6),
    "margin_s": ("float", 0.0, 4.0),
    "slow": ("float", 1.05, 1.6),
    "startup_s": ("float", 0.0, 5.0),
    "hold_m": ("float", 4.0, 25.0),
    "chasers": ("int", 0, 2),
    "pre_k_min": ("int", 1, 3),
    "pre_k_max": ("int", 2, 7),
    "pre_margin": ("float", -3.0, 4.0),
    "prepos_during_plan": ("int", 0, 1),
}
MIN_DELTA = 0.02
TEST = {"scenarios": 20, "reps": 2, "levels": ["AVOIDANT", "RANDOM"], "teams": [3, 5, 7]}


def sample(rng):
    out = {}
    for k, (t, lo, hi) in SPACE.items():
        out[k] = rng.randint(lo, hi) if t == "int" else round(rng.uniform(lo, hi), 3)
    return out


def perturb(base, rng):
    out = {}
    for k, (t, lo, hi) in SPACE.items():
        if t == "int":
            out[k] = min(hi, max(lo, base[k] + rng.choice([-1, 0, 0, 1])))
        else:
            out[k] = round(min(hi, max(lo, base[k] + rng.gauss(0, 0.15 * (hi - lo)))), 3)
    return out


def _init():
    import torch

    torch.set_num_threads(1)


def episode(args):
    from audit_cage_certificate import replay

    key, m, i, seed, salt, level, team, kind, params, single, full = args
    try:
        ep, _ = replay(
            m,
            i,
            seed,
            salt,
            "T",
            None,
            "policy",
            300.0,
            kind=kind,
            speed=1.0,
            level=level,
            team=team,
            learner={"params": params} if params is not None else None,
            active=None if single is None else [single],
            reward_mode="certificate" if full else "trap",
        )
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    st = getattr(ep, "planner_stats", {}) or {}
    return {
        "key": key,
        "success": bool(
            ep.contact_capture if full else (ep.trapped_at is not None or ep.contact_capture)
        ),
        "d06": bool(ep.contact_capture),
        "collided": ep.collided,
        "plan_share": round(st.get("steps_with_plan", 0) / max(1, st.get("steps", 1)), 3),
    }


def round_tasks(gen, rnd, configs):
    n = ROUNDS[rnd][0]
    out = []
    for cname, params in configs.items():
        for m in TRAINING:
            for level, team in SETTINGS:
                for i in range(n):
                    idx = 1000 * rnd + i
                    key = f"g{gen}r{rnd}|{cname}|{m}|{level}|{team}|{idx}"
                    out.append(
                        (
                            key,
                            m,
                            idx,
                            9500 + idx,
                            f"PO{gen}",
                            level,
                            team,
                            "ambush_plus",
                            params,
                            None,
                            False,
                        )
                    )
    return out


def val_tasks(configs):
    out = []
    for cname, params in configs.items():
        for m in TRAINING:
            for level, team in SETTINGS:
                for i in range(12):
                    key = f"val|{cname}|{m}|{level}|{team}|{i}"
                    out.append(
                        (
                            key,
                            m,
                            i,
                            9500 + i,
                            "PV11",
                            level,
                            team,
                            "ambush_plus",
                            params,
                            None,
                            False,
                        )
                    )
    return out


def test_tasks(opt_params, default_params):
    out = []
    pols = [
        ("plus_opt", "ambush_plus", opt_params),
        ("plus_default", "ambush_plus", default_params),
        ("ambush_a95", "ambush", None),
        ("pursuit", "pursuit", None),
    ]
    for m in TRAINING + DEVELOPMENT:
        for i in range(TEST["scenarios"]):
            for rep in range(TEST["reps"]):
                seed = 9500 + i + 100000 * rep
                for level in TEST["levels"]:
                    for team in TEST["teams"]:
                        base = f"{m}|{i}|{seed}|{level}|{team}"
                        for pname, kind, params in pols:
                            out.append(
                                (
                                    f"test|{pname}|{base}",
                                    m,
                                    i,
                                    seed,
                                    "PE11",
                                    level,
                                    team,
                                    kind,
                                    params,
                                    None,
                                    True,
                                )
                            )
                        for s in [f"p{k}" for k in range(1, team + 1)]:
                            out.append(
                                (
                                    f"test|plus_opt_only_{s}|{base}",
                                    m,
                                    i,
                                    seed,
                                    "PE11",
                                    level,
                                    team,
                                    "ambush_plus",
                                    opt_params,
                                    s,
                                    True,
                                )
                            )
    return out


class Store:
    def __init__(self, package):
        self.path = os.path.join(package, "results.jsonl")
        self.rows = {}
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as h:
                for x in h:
                    r = json.loads(x)
                    self.rows[r["key"]] = r

    def run(self, pool, tasks, deadline, fn=None):
        """`fn`: the episode function (A-101 r01 was void because the default was used with a
        different argument layout)."""
        todo = [t for t in tasks if t[0] not in self.rows]
        if not todo:
            return True
        with open(self.path, "a", encoding="utf-8") as h:
            for r in pool.imap_unordered(fn or episode, todo, chunksize=1):
                self.rows[r["key"]] = r
                h.write(json.dumps(r) + "\n")
                h.flush()
                if time.time() > deadline:
                    break
        return all(t[0] in self.rows for t in tasks)

    def score(self, prefix_list, cname):
        vals = [
            r["success"]
            for k, r in self.rows.items()
            if "failed" not in r and k.split("|")[1] == cname and k.split("|")[0] in prefix_list
        ]
        return sum(vals) / max(1, len(vals)), len(vals)


def main() -> int:
    from joint_interception.native.ambush_plus import DEFAULTS

    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    deadline = time.time() + 60 * args.budget_min
    spath = os.path.join(package, "state.pkl")
    st = pickle.load(open(spath, "rb")) if os.path.exists(spath) else {"phase": "g1"}  # noqa: SIM115
    store = Store(package)
    log = open(os.path.join(package, "log.jsonl"), "a", encoding="utf-8")  # noqa: SIM115

    def note(e):
        e["wall"] = round(time.time(), 1)
        log.write(json.dumps(e) + "\n")
        log.flush()
        print(json.dumps(e), flush=True)

    def save():
        with open(spath + ".tmp", "wb") as h:
            pickle.dump(st, h)
        os.replace(spath + ".tmp", spath)

    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        for gen in (1, 2):
            gkey = f"g{gen}"
            if st["phase"] not in (gkey,) and not st["phase"].startswith(gkey):
                continue
            if f"{gkey}_configs" not in st:
                rng = random.Random(97 + gen)
                cfgs = {"default": dict(DEFAULTS)}
                if gen == 1:
                    for k in range(32):
                        cfgs[f"c1_{k}"] = sample(rng)
                else:
                    best = st["g1_best_params"]
                    cfgs["g1best"] = dict(best)
                    for k in range(16):
                        cfgs[f"c2_{k}"] = perturb(best, rng)
                st[f"{gkey}_configs"] = cfgs
                st[f"{gkey}_alive"] = list(cfgs)
                st[f"{gkey}_round"] = 0
                save()
            cfgs = st[f"{gkey}_configs"]
            while st[f"{gkey}_round"] < len(ROUNDS):
                rnd = st[f"{gkey}_round"]
                alive = {c: cfgs[c] for c in st[f"{gkey}_alive"]}
                done = store.run(pool, round_tasks(gen, rnd, alive), deadline)
                if not done:
                    save()
                    note({"stage": "chunk_done", "phase": gkey, "round": rnd})
                    return 0
                prefixes = [f"g{gen}r{r}" for r in range(rnd + 1)]
                ranked = sorted(
                    [c for c in alive if c != "default"],
                    key=lambda c: -store.score(prefixes, c)[0],
                )
                keep = ranked[: ROUNDS[rnd][1]]
                note(
                    {
                        "stage": "round",
                        "gen": gen,
                        "round": rnd,
                        "default": store.score(prefixes, "default"),
                        "top": [(c, store.score(prefixes, c)) for c in ranked[:5]],
                    }
                )
                st[f"{gkey}_alive"] = ["default", *keep]
                st[f"{gkey}_round"] += 1
                save()
            best = st[f"{gkey}_alive"][1]
            r3 = [f"g{gen}r{len(ROUNDS) - 1}"]
            gain = store.score(r3, best)[0] - store.score(r3, "default")[0]
            st[f"{gkey}_best"], st[f"{gkey}_best_params"], st[f"{gkey}_gain_r3"] = (
                best,
                cfgs[best],
                gain,
            )
            note(
                {
                    "stage": "generation_end",
                    "gen": gen,
                    "best": best,
                    "params": cfgs[best],
                    "gain_vs_default_round3": round(gain, 4),
                }
            )
            if gen == 1 and gain < MIN_DELTA:
                st["breaker"] = "generation 2 skipped: best did not beat defaults by 0.02"
                st["final_params"], st["final_name"] = dict(DEFAULTS), "default"
                st["phase"] = "val"
                note({"stage": "breaker", "action": st["breaker"]})
                save()
                break
            st["phase"] = "g2" if gen == 1 else "val"
            if gen == 2:
                st["final_params"], st["final_name"] = cfgs[best], best
            save()
        if st["phase"] == "val":
            cfgs = {"final": st["final_params"], "default": dict(DEFAULTS)}
            if not store.run(pool, val_tasks(cfgs), deadline):
                save()
                note({"stage": "chunk_done", "phase": "val"})
                return 0
            v_final, v_def = store.score(["val"], "final")[0], store.score(["val"], "default")[0]
            st["val"] = {"final": v_final, "default": v_def}
            st["phase"] = "test"
            note(
                {
                    "stage": "validation",
                    "final": v_final,
                    "default": v_def,
                    "name": st["final_name"],
                }
            )
            save()
        if st["phase"] == "test":
            tasks = test_tasks(st["final_params"], dict(DEFAULTS))
            if not store.run(pool, tasks, deadline):
                save()
                n = sum(1 for t in tasks if t[0] in store.rows)
                note({"stage": "chunk_done", "phase": "test", "done": n, "of": len(tasks)})
                return 0
            st["phase"] = "summary"
            save()
        if st["phase"] == "summary":
            summarise(package, store, st)
            st["phase"] = "done"
            save()
            note({"stage": "done"})
    return 0


def summarise(package, store, st):
    tests = [r for k, r in store.rows.items() if k.startswith("test|")]
    by = {}
    for r in tests:
        if "failed" in r:
            continue
        _, pname, m, i, seed, level, team = r["key"].split("|")
        by.setdefault((pname, level, int(team), m, int(i)), []).append(float(r["d06"]))
    mean = {k: sum(v) / len(v) for k, v in by.items()}

    def per(p, level, team):
        return {k[3:]: v for k, v in mean.items() if k[0] == p and k[1] == level and k[2] == team}

    out = {
        "final_name": st.get("final_name"),
        "final_params": st.get("final_params"),
        "breaker": st.get("breaker"),
        "val": st.get("val"),
        "failed": sum("failed" in r for r in tests),
        "collisions": sum(r.get("collided", False) for r in tests if "failed" not in r),
        "cells": {},
    }
    for level in TEST["levels"]:
        for team in TEST["teams"]:
            opt, dft, a95, pur = (
                per(p, level, team) for p in ("plus_opt", "plus_default", "ambush_a95", "pursuit")
            )
            singles = [per(f"plus_opt_only_p{k}", level, team) for k in range(1, team + 1)]
            ks = sorted(set(opt).intersection(dft, a95, pur, *singles))
            union = [1 - math.prod(1 - s[k] for s in singles) for k in ks]
            out["cells"][f"{level}_team{team}"] = {
                "scenarios": len(ks),
                "plus_opt": bootstrap([opt[k] for k in ks]),
                "plus_default": bootstrap([dft[k] for k in ks]),
                "ambush_a95": bootstrap([a95[k] for k in ks]),
                "pursuit": bootstrap([pur[k] for k in ks]),
                "opt_minus_a95": bootstrap([opt[k] - a95[k] for k in ks]),
                "opt_minus_pursuit": bootstrap([opt[k] - pur[k] for k in ks]),
                "opt_minus_default": bootstrap([opt[k] - dft[k] for k in ks]),
                "default_minus_a95": bootstrap([dft[k] - a95[k] for k in ks]),
                "single_mean": bootstrap([sum(s[k] for s in singles) / team for k in ks]),
                "synergy": bootstrap([opt[k] - u for k, u in zip(ks, union, strict=True)]),
                "synergy_bonferroni": bootstrap(
                    [opt[k] - u for k, u in zip(ks, union, strict=True)], alpha=0.05 / 6
                ),
            }
    cells = out["cells"].values()
    out["primary_opt_minus_a95_pooled"] = None
    pooled = []
    for level in TEST["levels"]:
        for team in TEST["teams"]:
            opt, a95 = per("plus_opt", level, team), per("ambush_a95", level, team)
            pooled += [opt[k] - a95[k] for k in opt if k in a95]
    out["primary_opt_minus_a95_pooled"] = bootstrap(pooled)
    out["primary_passes"] = out["primary_opt_minus_a95_pooled"][1] > 0
    out["cooperation_cells"] = [
        c for c, v in out["cells"].items() if v["synergy_bonferroni"][1] > 0
    ]
    del cells
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
