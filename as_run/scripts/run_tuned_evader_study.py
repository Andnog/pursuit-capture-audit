"""An evader tuned against PLB (A-127 E, pre-registered).

The evader family is EvaderLevel.TUNED: a weighted sum of public features per continuation. The
weights are searched on TRAINING cities to minimise OC capture by PLB c2_15 (two rungs), and the
selected evader is then tested on fresh scenarios of the seven non-TEST cities against PLB, the
junction ambush and pursuit. A reference weight vector reproduces OPTIMAL_ESCAPE on the same
scenarios. Resumable chunks (--budget-min); stages are derived from the stored results.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from addendum_reanalysis import fam_boot  # noqa: E402
from run_ambush_optimization import Store, _init  # noqa: E402
from run_endpoint_validation import DEVELOPMENT, TRAINING  # noqa: E402

N_FEATURES, N_CANDIDATES, GEN_SEED = 7, 32, 20261005
REFERENCE = (1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
KEEP, BREAKER = 8, 0.02
TEAMS = [3, 5, 7]
TEST_ARMS = [
    ("sel", "plus_opt"),
    ("sel", "ambush_a95"),
    ("sel", "pursuit"),
    ("ref", "plus_opt"),
    ("ref", "pursuit"),
]
A99 = os.path.join(ROOT, "experiments", "20261002_ambush_optimization_r01", "summary.json")


def candidates():
    """The registered candidate set: a reference that reproduces OPTIMAL plus 32 sampled vectors."""
    rng = random.Random(GEN_SEED)
    out = {"ref": REFERENCE}
    for k in range(N_CANDIDATES):
        out[f"c{k:02d}"] = tuple(round(rng.uniform(-1.0, 1.0), 4) for _ in range(N_FEATURES))
    return out


def episode(args):
    import joint_interception.simulator.evader as evader_module
    from audit_cage_certificate import replay

    key, m, i, seed, salt, team, method, weights = args
    with open(A99, encoding="utf-8") as h:
        c215 = json.load(h)["final_params"]
    kind = {"plus_opt": "ambush_plus", "ambush_a95": "ambush", "pursuit": "pursuit"}[method]
    evader_module.TUNED_WEIGHTS = tuple(weights)
    try:
        ep, _ = replay(
            m, i, seed, salt, "T", None, "policy", 300.0, kind=kind, speed=1.0, level="TUNED",
            team=team, learner={"params": c215} if kind == "ambush_plus" else None,
            reward_mode="certificate",
        )  # fmt: skip
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    finally:
        evader_module.TUNED_WEIGHTS = REFERENCE
    return {
        "key": key,
        "d06": bool(ep.contact_capture),
        "collided": ep.collided,
        "evader_exited": ep.evader_exited,
    }


def rung1_tasks(cands):
    out = []
    for name, w in cands.items():
        for m in TRAINING:
            for i in range(6):
                seed = 9500 + i
                out.append((f"R1|{name}|{m}|{i}|{seed}|5", m, i, seed, "ES1", 5, "plus_opt", w))
    return out


def rung2_tasks(cands, names):
    out = []
    for name in names:
        for m in TRAINING:
            for i in range(20):
                seed = 9500 + i
                for team in TEAMS:
                    key = f"R2|{name}|{m}|{i}|{seed}|{team}"
                    out.append((key, m, i, seed, "ES2", team, "plus_opt", cands[name]))
    return out


def test_tasks(cands, selected):
    weights = {"sel": cands[selected], "ref": cands["ref"]}
    out = []
    for m in TRAINING + DEVELOPMENT:
        for i in range(20):
            for rep in range(2):
                seed = 9500 + i + 100000 * rep
                for team in TEAMS:
                    for evader, method in TEST_ARMS:
                        key = f"T|{evader}|{method}|{m}|{i}|{seed}|TUNED|{team}"
                        out.append((key, m, i, seed, "PE21", team, method, weights[evader]))
    return out


def rung_rates(rows, rung, names):
    """Capture by PLB per candidate, on the scenario cells every listed candidate completed."""
    by = {n: {} for n in names}
    for k, r in rows.items():
        p = k.split("|")
        if p[0] != rung or p[1] not in by or "failed" in r:
            continue
        by[p[1]][tuple(p[2:])] = float(r["d06"])
    common = set.intersection(*(set(v) for v in by.values())) if by else set()
    if not common:
        return {}, 0
    return {n: sum(by[n][c] for c in common) / len(common) for n in names}, len(common)


def lowest(rates, names, k):
    """The k names with the lowest rate; ties broken by name."""
    return sorted(names, key=lambda n: (rates[n], n))[:k]


def cells(rows, evader, method):
    """{(city, scenario, 'TUNED', team): seed-averaged OC} for one test arm."""
    acc = {}
    for k, r in rows.items():
        p = k.split("|")
        if p[0] != "T" or p[1] != evader or p[2] != method or "failed" in r:
            continue
        acc.setdefault((p[3], int(p[4]), p[6], int(p[7])), []).append(float(r["d06"]))
    return {k: sum(v) / len(v) for k, v in acc.items()}


def paired(a, b, team=None):
    fams = {}
    for k in sorted(set(a) & set(b)):
        if team is None or k[3] == team:
            fams.setdefault(k[:3], []).append(a[k] - b[k])
    return fams


def summarise(package, rows, cands, search):
    t = {arm: cells(rows, *arm) for arm in TEST_ARMS}

    def rate(arm, team=None):
        v = [x for k, x in t[arm].items() if team is None or k[3] == team]
        return round(sum(v) / len(v), 4) if v else None

    out = {
        "search": search,
        "weights": {n: list(cands[n]) for n in ("ref", search["selected"])},
        "failed": sum("failed" in r for r in rows.values()),
        "episodes": len(rows),
        "rates": {
            f"{e}|{m}": {"all": rate((e, m))} | {f"team{k}": rate((e, m), k) for k in TEAMS}
            for e, m in TEST_ARMS
        },
    }
    sel_plb, sel_pur = t[("sel", "plus_opt")], t[("sel", "pursuit")]
    ref_plb, ref_pur = t[("ref", "plus_opt")], t[("ref", "pursuit")]
    fams = paired(sel_plb, sel_pur)
    out["primary_plb_minus_pursuit_vs_tuned_family_95"] = fam_boot(fams)
    out["primary_city_family_95"] = fam_boot(fams, two_stage=True)
    b = out["primary_plb_minus_pursuit_vs_tuned_family_95"]
    out["primary_passes"] = bool(b) and b[1] > 0
    out["families"] = len(fams)
    out["by_team_plb_minus_pursuit_vs_tuned"] = {
        f"team{k}": fam_boot(paired(sel_plb, sel_pur, k)) for k in TEAMS
    }
    out["plb_minus_ambush_vs_tuned_family_95"] = fam_boot(paired(sel_plb, t[("sel", "ambush_a95")]))
    out["plb_minus_pursuit_vs_reference_family_95"] = fam_boot(paired(ref_plb, ref_pur))
    out["plb_tuned_minus_reference_family_95"] = fam_boot(paired(sel_plb, ref_plb))
    out["pursuit_tuned_minus_reference_family_95"] = fam_boot(paired(sel_pur, ref_pur))
    exited = {}
    for e, m in TEST_ARMS:
        v = [
            float(r["evader_exited"])
            for k, r in rows.items()
            if k.startswith(f"T|{e}|{m}|") and "failed" not in r
        ]
        exited[f"{e}|{m}"] = round(sum(v) / len(v), 4) if v else None
    out["evader_exited"] = exited
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    return out


def run_chunk(store, pool, todo, deadline, stall_s=900.0):
    """Never blocks past the deadline; gives up a chunk after `stall_s` without any result."""
    todo = [t for t in todo if t[0] not in store.rows]
    if not todo:
        return True
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
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    store, cands = Store(package), candidates()
    deadline = time.time() + 60 * args.budget_min
    stage = "rung1"
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        if run_chunk(store, pool, rung1_tasks(cands), deadline):
            sampled = [n for n in cands if n != "ref"]
            r1, n1 = rung_rates(store.rows, "R1", list(cands))
            kept = lowest(r1, sampled, KEEP)
            stage = "rung2"
            if run_chunk(store, pool, rung2_tasks(cands, kept + ["ref"]), deadline):
                r2, n2 = rung_rates(store.rows, "R2", kept + ["ref"])
                selected = lowest(r2, kept, 1)[0]
                search = {
                    "rung1": {"cells": n1, "rates": {k: round(v, 4) for k, v in r1.items()}},
                    "kept": kept,
                    "rung2": {"cells": n2, "rates": {k: round(v, 4) for k, v in r2.items()}},
                    "selected": selected,
                    "reference_minus_selected": round(r2["ref"] - r2[selected], 4),
                    "stronger_evader_found": bool(r2["ref"] - r2[selected] >= BREAKER),
                }
                stage = "test"
                if run_chunk(store, pool, test_tasks(cands, selected), deadline):
                    summarise(package, store.rows, cands, search)
                    stage = "done"
    print(json.dumps({"stage": stage, "rows": len(store.rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
