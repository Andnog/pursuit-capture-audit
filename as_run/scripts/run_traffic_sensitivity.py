"""PLB and pursuit with background traffic (A-127 T, pre-registered addition).

Same scenarios and seeds as the kinematic study (salt PK1, seven non-TEST cities) with the
background traffic of A-92 (about 300 random-trip cars per city). The paired reference without
traffic is arm K0 of the kinematic package. Resumable chunks.
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

import run_kinematic_sensitivity as ks  # noqa: E402
from addendum_reanalysis import fam_boot  # noqa: E402
from run_ambush_optimization import Store, _init  # noqa: E402

K_PACKAGE = os.path.join(ROOT, "experiments", "20261005_kinematic_sensitivity_r01")


def traffic_args(map_id):
    return ["-r", os.path.join(ROOT, "assets", "background_traffic", f"{map_id}.rou.xml")]


def episode(args):
    from audit_cage_certificate import replay

    key, m, i, seed, level, team, method = args
    with open(ks.A99, encoding="utf-8") as h:
        c215 = json.load(h)["final_params"]
    kind = {"plus_opt": "ambush_plus", "pursuit": "pursuit"}[method]
    try:
        ep, _ = replay(
            m, i, seed, ks.SALT, "T", None, "policy", 300.0, kind=kind, speed=1.0, level=level,
            team=team, learner={"params": c215} if kind == "ambush_plus" else None,
            extra_sumo_args=traffic_args(m), reward_mode="certificate",
        )  # fmt: skip
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    body5, centre5 = ks.proximity(ep)
    return {
        "key": key,
        "d06": bool(ep.contact_capture),
        "prox_5m": body5,
        "prox_5m_centre": centre5,
        "collided": ep.collided,
        "evader_exited": ep.evader_exited,
    }


def tasks():
    """The K design restricted to one arm; keys 'K|KT|method|city|scenario|seed|evader|team'."""
    out = []
    for key, m, i, seed, level, team, method, variant in ks.tasks():
        if variant == "K0":
            out.append((key.replace("|K0|", "|KT|", 1), m, i, seed, level, team, method))
    return out


def summarise(package, rows):
    reference = {}
    with open(os.path.join(K_PACKAGE, "results.jsonl"), encoding="utf-8") as h:
        for line in h:
            r = json.loads(line)
            if r["key"].startswith("K|K0|"):
                reference[r["key"]] = r
    both = dict(reference) | dict(rows)
    d06, prox = ks.cell_means(both, "d06"), ks.cell_means(both, "prox_5m")

    def sub(table, variant, method):
        return {k[2:]: v for k, v in table.items() if k[:2] == (variant, method)}

    def rate(table, variant, method):
        v = list(sub(table, variant, method).values())
        return round(sum(v) / len(v), 4) if v else None

    plb, pur = sub(d06, "KT", "plus_opt"), sub(d06, "KT", "pursuit")
    fams = ks.paired(plb, pur)
    primary = fam_boot(fams)
    out = {
        "episodes": len(rows),
        "failed": sum("failed" in r for r in rows.values()),
        "collisions": sum(bool(r.get("collided")) for r in rows.values()),
        "families": len(fams),
        "oc": {
            "traffic": {"plb": rate(d06, "KT", "plus_opt"), "pursuit": rate(d06, "KT", "pursuit")},
            "no_traffic": {
                "plb": rate(d06, "K0", "plus_opt"),
                "pursuit": rate(d06, "K0", "pursuit"),
            },
        },
        "prox_5m_pursuit": {
            "traffic": rate(prox, "KT", "pursuit"),
            "no_traffic": rate(prox, "K0", "pursuit"),
        },
        "primary_plb_minus_pursuit_traffic_family_95": primary,
        "primary_city_family_95": fam_boot(fams, two_stage=True),
        "primary_passes": bool(primary) and primary[1] > 0,
        "plb_minus_pursuit_no_traffic_family_95": fam_boot(
            ks.paired(sub(d06, "K0", "plus_opt"), sub(d06, "K0", "pursuit"))
        ),
        "traffic_minus_no_traffic_plb_family_95": fam_boot(
            ks.paired(plb, sub(d06, "K0", "plus_opt"))
        ),
        "traffic_minus_no_traffic_pursuit_family_95": fam_boot(
            ks.paired(pur, sub(d06, "K0", "pursuit"))
        ),
        "prox5_minus_oc_pursuit_traffic_family_95": fam_boot(
            ks.paired(sub(prox, "KT", "pursuit"), pur)
        ),
    }
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    store, todo = Store(package), tasks()
    deadline = time.time() + 60 * args.budget_min
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        pending = [t for t in todo if t[0] not in store.rows]
        done = _chunk(store, pool, pending, deadline) if pending else True
    if done:
        summarise(package, store.rows)
    n = sum(t[0] in store.rows for t in todo)
    print(json.dumps({"stage": "done" if done else "chunk_done", "done": n, "of": len(todo)}))
    return 0


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


if __name__ == "__main__":
    raise SystemExit(main())
