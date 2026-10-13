"""Sensitivity of the main contrasts to the simulator's kinematic model (A-127 K, pre-registered).

Seven non-TEST cities (salt PK1), 20 scenarios x 2 SUMO seeds x AVOIDANT/RANDOM x teams 3/5/7 x
{PLB c2_15, pursuit} under three kinematic variants on the same scenarios and seeds:
K0 the model used throughout, K1 ballistic position update, K2 IDM car-following.
Every episode is scored under OC and under the 5 m proximity rules. Resumable chunks.

``--devcheck`` (salt DEVK, not gated) verifies that each option changes the simulated trajectories.
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

from addendum_reanalysis import fam_boot  # noqa: E402
from run_ambush_optimization import Store, _init  # noqa: E402
from run_endpoint_validation import DEVELOPMENT, TRAINING  # noqa: E402

SALT = "PK1"
VARIANTS = {
    "K0": [],
    "K1": ["--step-method.ballistic", "true"],
    "K2": ["--default.carfollowmodel", "IDM"],
}
LEVELS, TEAMS, METHODS = ["AVOIDANT", "RANDOM"], [3, 5, 7], ["plus_opt", "pursuit"]
A99 = os.path.join(ROOT, "experiments", "20261002_ambush_optimization_r01", "summary.json")


def _run(m, i, seed, salt, level, team, method, variant):
    from audit_cage_certificate import replay

    with open(A99, encoding="utf-8") as h:
        c215 = json.load(h)["final_params"]
    kind = {"plus_opt": "ambush_plus", "pursuit": "pursuit"}[method]
    return replay(
        m, i, seed, salt, "T", None, "policy", 300.0, kind=kind, speed=1.0, level=level, team=team,
        learner={"params": c215} if kind == "ambush_plus" else None,
        extra_sumo_args=VARIANTS[variant], reward_mode="certificate",
    )  # fmt: skip


def proximity(ep):
    """First-instant proximity flags of the episode: body gap <= 5 m and centre distance <= 5 m."""
    from joint_interception.domain.geometry import body_separation_m

    body5 = centre5 = False
    for f in ep.trace:
        e = f.vehicles.get("e1")
        if e is None:
            continue
        for v, p in f.vehicles.items():
            if v == "e1":
                continue
            c = math.dist((e.x, e.y), (p.x, p.y))
            centre5 = centre5 or c <= 5.0
            if c <= 16.0 and not body5:
                body5 = body_separation_m(e.rectangle(), p.rectangle()) <= 5.0
        if body5 and centre5:
            break
    return body5, centre5


def episode(args):
    key, m, i, seed, level, team, method, variant = args
    try:
        ep, _ = _run(m, i, seed, SALT, level, team, method, variant)
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    body5, centre5 = proximity(ep)
    return {
        "key": key,
        "d06": bool(ep.contact_capture),
        "prox_5m": body5,
        "prox_5m_centre": centre5,
        "collided": ep.collided,
        "evader_exited": ep.evader_exited,
    }


def devcheck(args):
    """One development episode per variant; returns a digest of the evader's trajectory."""
    m, variant = args
    try:
        ep, _ = _run(m, 0, 9500, "DEVK", "AVOIDANT", 5, "pursuit", variant)
    except Exception as error:  # noqa: BLE001
        return {
            "city": m,
            "variant": variant,
            "failed": f"{type(error).__name__}: {str(error)[:100]}",
        }
    path = [
        (round(f.time_s, 1), round(f.vehicles["e1"].x, 2), round(f.vehicles["e1"].y, 2))
        for f in ep.trace
        if "e1" in f.vehicles
    ]
    return {"city": m, "variant": variant, "n": len(path), "path": path[:600]}


def tasks():
    out = []
    for m in TRAINING + DEVELOPMENT:
        for i in range(20):
            for rep in range(2):
                seed = 9500 + i + 100000 * rep
                for level in LEVELS:
                    for team in TEAMS:
                        for method in METHODS:
                            for variant in VARIANTS:
                                key = f"K|{variant}|{method}|{m}|{i}|{seed}|{level}|{team}"
                                out.append((key, m, i, seed, level, team, method, variant))
    return out


def cell_means(rows, field):
    """{(variant, method, city, scenario, evader, team): seed-averaged value}."""
    acc = {}
    for k, r in rows.items():
        if "failed" in r:
            continue
        _, variant, method, m, i, _seed, level, team = k.split("|")
        acc.setdefault((variant, method, m, int(i), level, int(team)), []).append(float(r[field]))
    return {k: sum(v) / len(v) for k, v in acc.items()}


def paired(a, b):
    """Family-keyed paired cell differences a - b; inputs: {(city, scenario, evader, team): x}."""
    fams = {}
    for k in sorted(set(a) & set(b)):
        fams.setdefault(k[:3], []).append(a[k] - b[k])
    return fams


def summarise(package, rows):
    d06, prox = cell_means(rows, "d06"), cell_means(rows, "prox_5m")
    centre = cell_means(rows, "prox_5m_centre")

    def sub(table, variant, method):
        return {k[2:]: v for k, v in table.items() if k[:2] == (variant, method)}

    def rate(table, variant, method):
        v = list(sub(table, variant, method).values())
        return round(sum(v) / len(v), 4) if v else None

    out = {
        "failed": sum("failed" in r for r in rows.values()),
        "episodes": len(rows),
        "variants": {},
    }
    for variant in VARIANTS:
        plb, pur = sub(d06, variant, "plus_opt"), sub(d06, variant, "pursuit")
        fams = paired(plb, pur)
        block = {
            "families": len(fams),
            "cells": sum(len(v) for v in fams.values()),
            "oc": {"plb": rate(d06, variant, "plus_opt"), "pursuit": rate(d06, variant, "pursuit")},
            "prox_5m_pursuit": rate(prox, variant, "pursuit"),
            "prox_5m_centre_pursuit": rate(centre, variant, "pursuit"),
            "plb_minus_pursuit_family_95": fam_boot(fams),
            "plb_minus_pursuit_city_family_95": fam_boot(fams, two_stage=True),
            "prox5_minus_oc_pursuit_family_95": fam_boot(
                paired(sub(prox, variant, "pursuit"), pur)
            ),
        }
        if variant != "K0":
            for method in METHODS:
                block[f"oc_minus_K0_{method}_family_95"] = fam_boot(
                    paired(sub(d06, variant, method), sub(d06, "K0", method))
                )
            b = block["plb_minus_pursuit_family_95"]
            block["primary_passes"] = bool(b) and b[1] > 0
        out["variants"][variant] = block
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--devcheck", action="store_true")
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    if args.devcheck:
        jobs = [(m, v) for m in (TRAINING[0], DEVELOPMENT[0]) for v in VARIANTS]
        with mp.get_context("spawn").Pool(min(args.workers, len(jobs)), initializer=_init) as pool:
            res = pool.map(devcheck, jobs)
        by, report = {(r["city"], r["variant"]): r for r in res}, {}
        for city in (TRAINING[0], DEVELOPMENT[0]):
            base = by[(city, "K0")]
            for v in ("K1", "K2"):
                r = by[(city, v)]
                if "failed" in r or "failed" in base:
                    report[f"{city}|{v}"] = {"failed": r.get("failed") or base.get("failed")}
                    continue
                first = next(
                    (a[0] for a, b in zip(base["path"], r["path"], strict=False) if a != b), None
                )
                report[f"{city}|{v}"] = {
                    "differs_from_K0": base["path"] != r["path"],
                    "first_difference_s": first,
                }
        with open(os.path.join(package, "DEVCHECK.json"), "w", encoding="utf-8") as h:
            json.dump(report, h, indent=2)
        print(json.dumps(report))
        return 0
    store = Store(package)
    todo = tasks()
    deadline = time.time() + 60 * args.budget_min
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        todo_now = [t for t in todo if t[0] not in store.rows]
        done = _run_chunk(store, pool, todo_now, deadline) if todo_now else True
    if done:
        summarise(package, store.rows)
    n = sum(t[0] in store.rows for t in todo)
    print(json.dumps({"stage": "done" if done else "chunk_done", "done": n, "of": len(todo)}))
    return 0


def _run_chunk(store, pool, todo, deadline, stall_s=900.0):
    """Never blocks past the deadline; gives up a chunk after `stall_s` without any result."""
    it = pool.imap_unordered(episode, todo, chunksize=1)
    last = time.time()
    with open(store.path, "a", encoding="utf-8") as h:
        while True:
            try:
                r = it.next(timeout=30)
            except StopIteration:
                break
            except mp.TimeoutError:
                if time.time() > deadline or time.time() - last > stall_s:
                    break
                continue
            last = time.time()
            store.rows[r["key"]] = r
            h.write(json.dumps(r) + "\n")
            h.flush()
            if time.time() > deadline:
                break
    return all(t[0] in store.rows for t in todo)


if __name__ == "__main__":
    raise SystemExit(main())
