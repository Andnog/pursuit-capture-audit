"""Single-shot evaluation on a second held-out set of cities (A-138, pre-registered).

Frozen methods (PLB c2_15, junction ambush A-95, pursuit) on four cities never used before, with
the AVOIDANT, RANDOM and OPTIMAL evaders and teams of 3, 5 and 7; plus a null team of five pursuers
driving random routes. Every episode is scored under OC and the 5 m proximity rules. Salt PB1.
Resumable chunks. After this run the four cities are spent.
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

REGISTERED = [
    "denver_downtown",
    "vancouver_downtown",
    "barcelona_eixample",
    "buenos_aires_microcentro",
]
SALT = "PB1"
LEVELS = ["AVOIDANT", "RANDOM", "OPTIMAL_ESCAPE"]
PRIMARY_LEVELS = ("AVOIDANT", "RANDOM")
TEAMS, METHODS = [3, 5, 7], ["plus_opt", "ambush_a95", "pursuit"]
FIELDS = ("d06", "prox_5m", "prox_5m_centre")


def cities():
    """The accepted cities of the build manifest; they must be the registered four."""
    with open(os.path.join(ROOT, "assets", "osm_b", "MANIFEST.json"), encoding="utf-8") as h:
        accepted = json.load(h)["accepted"]
    if accepted != REGISTERED:
        raise SystemExit(f"accepted cities {accepted} are not the registered set")
    return accepted


def null_episode(args, salt=SALT):
    """Five pursuers drive random routes without pursuing (the null team of A-115 B3)."""
    from audit_addendum import Wander
    from audit_cage_certificate import _net, _run
    from joint_interception.domain.contracts import load_domain
    from joint_interception.domain.geometry import body_separation_m
    from joint_interception.simulator.evader import EvaderLevel
    from joint_interception.world.construction import make_scenario

    key, m, i, seed, level = args
    net = _net(m)
    sc = make_scenario(net, m, EvaderLevel[level], [f"p{k}" for k in range(1, 6)], f"{salt}s{i}")
    if len(sc.pursuer_starts) != 5:
        return {"key": key, "failed": "ValueError: scenario could not place the team"}
    label = f"hbn{m[:3]}{i}_{seed}"
    try:
        ep = _run(
            net, m, sc, load_domain(), lambda obs: {}, 1.0, seed, label, "T", 300.0, None, None,
            Wander(seed), "certificate", 1.0,
        )  # fmt: skip
    except Exception as error:  # noqa: BLE001
        import traci

        try:
            traci.switch(label)
            traci.close()
        except Exception:  # noqa: BLE001
            pass
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    near5 = centre5 = False
    for f in ep.trace:
        e = f.vehicles.get("e1")
        if e is None:
            continue
        for v, p in f.vehicles.items():
            if v == "e1":
                continue
            c = math.dist((e.x, e.y), (p.x, p.y))
            centre5 = centre5 or c <= 5.0
            if c <= 16.0 and not near5:
                near5 = body_separation_m(e.rectangle(), p.rectangle()) <= 5.0
    return {
        "key": key,
        "d06": bool(ep.contact_capture),
        "prox_5m": near5,
        "prox_5m_centre": centre5,
        "collided": ep.collided,
    }


def episode(args):
    if args[0].startswith("HN|"):
        return null_episode(args)
    from run_test_confirmation import episode as controller_episode

    key, m, i, seed, level, team, method = args
    return controller_episode((key, m, i, seed, SALT, level, team, method, None))


def tasks(city_list):
    out = []
    for m in city_list:
        for i in range(20):
            for rep in range(2):
                seed = 9500 + i + 100000 * rep
                for level in LEVELS:
                    for team in TEAMS:
                        for method in METHODS:
                            key = f"HB|{method}|{m}|{i}|{seed}|{level}|{team}"
                            out.append((key, m, i, seed, level, team, method))
                for level in PRIMARY_LEVELS:
                    out.append((f"HN|null|{m}|{i}|{seed}|{level}|5", m, i, seed, level))
    return out


def cell_means(rows, field):
    """{(block, method, city, scenario, evader, team): seed-averaged value}."""
    acc = {}
    for k, r in rows.items():
        if "failed" in r:
            continue
        block, method, m, i, _seed, level, team = k.split("|")
        acc.setdefault((block, method, m, int(i), level, int(team)), []).append(float(r[field]))
    return {k: sum(v) / len(v) for k, v in acc.items()}


def paired(a, b, levels=PRIMARY_LEVELS, city=None, team=None):
    """Family-keyed paired cell differences a - b; inputs {(city, scenario, evader, team): x}."""
    fams = {}
    for k in sorted(set(a) & set(b)):
        if k[2] in levels and city in (None, k[0]) and team in (None, k[3]):
            fams.setdefault(k[:3], []).append(a[k] - b[k])
    return fams


def summarise(package, rows, city_list):
    tabs = {f: cell_means(rows, f) for f in FIELDS}

    def sub(field, method, block="HB"):
        return {k[2:]: v for k, v in tabs[field].items() if k[:2] == (block, method)}

    def rate(field, method, levels=PRIMARY_LEVELS, block="HB"):
        v = [x for k, x in sub(field, method, block).items() if k[2] in levels]
        return round(sum(v) / len(v), 4) if v else None

    plb, amb, pur = sub("d06", "plus_opt"), sub("d06", "ambush_a95"), sub("d06", "pursuit")
    b1 = paired(plb, pur)
    b2 = paired(sub("prox_5m", "pursuit"), pur)
    p1, p2 = fam_boot(b1, alpha=0.025), fam_boot(b2, alpha=0.025)
    out = {
        "cities": city_list,
        "episodes": len(rows),
        "failed": sum("failed" in r for r in rows.values()),
        "collisions": sum(bool(r.get("collided")) for r in rows.values()),
        "families": len(b1),
        "cells": sum(len(v) for v in b1.values()),
        "rates_primary_levels": {m: {f: rate(f, m) for f in FIELDS} for m in METHODS},
        "rates_optimal": {m: rate("d06", m, levels=("OPTIMAL_ESCAPE",)) for m in METHODS},
        "null_team": {f: rate(f, "null", block="HN") for f in FIELDS},
        "B1_plb_minus_pursuit_family_97.5": p1,
        "B1_passes": bool(p1) and p1[1] > 0,
        "B1_family_95": fam_boot(b1),
        "B1_city_family_95": fam_boot(b1, two_stage=True),
        "B2_prox5_minus_oc_pursuit_family_97.5": p2,
        "B2_passes": bool(p2) and p2[1] > 0,
        "B2_city_family_95": fam_boot(b2, two_stage=True),
        "by_city_plb_minus_pursuit": {c: fam_boot(paired(plb, pur, city=c)) for c in city_list},
        "optimal_plb_minus_pursuit_family_95": fam_boot(
            paired(plb, pur, levels=("OPTIMAL_ESCAPE",))
        ),
        "plb_minus_ambush_family_95": fam_boot(paired(plb, amb)),
        "centre5_minus_oc_pursuit_family_95": fam_boot(
            paired(sub("prox_5m_centre", "pursuit"), pur)
        ),
        "plb_minus_pursuit_under_body_gap_5m": fam_boot(
            paired(sub("prox_5m", "plus_opt"), sub("prox_5m", "pursuit"))
        ),
        "plb_minus_pursuit_under_centre_5m": fam_boot(
            paired(sub("prox_5m_centre", "plus_opt"), sub("prox_5m_centre", "pursuit"))
        ),
        "by_team_plb_minus_pursuit": {
            f"team{t}": fam_boot(paired(plb, pur, team=t)) for t in TEAMS
        },
    }
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    return out


def _chunk(store, pool, todo, deadline, stall_s=900.0):
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    city_list = cities()
    store, todo = Store(package), tasks(city_list)
    deadline = time.time() + 60 * args.budget_min
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        pending = [t for t in todo if t[0] not in store.rows]
        done = _chunk(store, pool, pending, deadline) if pending else True
    if done:
        summarise(package, store.rows, city_list)
    n = sum(t[0] in store.rows for t in todo)
    print(json.dumps({"stage": "done" if done else "chunk_done", "done": n, "of": len(todo)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
