"""Audit addendum r03 (A-121): coordination ablation, active escape after capture, R9 at scale and
reproduction of sealed packages. No TEST episode is run.

AB  coordinated PLB (c2_15) vs the same planner without joint assignment (`independent=1`);
    salt PE18, 7 non-TEST cities, AVOIDANT / RANDOM / GOAL_DIRECTED, teams 3 / 5 / 7; checked
    dispatch.
AE  the 1,433 audited captures, pursuers held from t_c, horizon t_c + 61 s, legacy dispatch; from
    t_c the evader actively tries every second to change to an adjacent lane that continues, and to
    reroute through it.
RC  the full A-99 test main cohort and the goal-directed cohort re-run with checked dispatch.
RP  100 sampled sealed episodes each from five packages, legacy dispatch, through their own episode
    functions; reproduction of the sealed OC outcome.
Resumable chunks (--budget-min).
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

from run_ambush_optimization import Store, _init  # noqa: E402
from run_endpoint_validation import DEVELOPMENT, TRAINING  # noqa: E402

EXP = os.path.join(ROOT, "experiments")
A99 = os.path.join(EXP, "20261002_ambush_optimization_r01")
METHODS = {"plus_opt": "ambush_plus", "ambush_a95": "ambush", "pursuit": "pursuit"}
ESC: dict = {"t": None}


def _mode(mode):
    import joint_interception.native.engine as engine

    engine.DISPATCH_MODE = mode


def _c215():
    with open(os.path.join(A99, "summary.json"), encoding="utf-8") as h:
        return json.load(h)["final_params"]


def rows(path):
    with open(path, encoding="utf-8") as h:
        return [json.loads(x) for x in h]


# -- AE: active escape ---------------------------------------------------------------------
def _active_escape(conn):
    """One escape attempt: change to an adjacent lane with an onward link and reroute through it."""
    try:
        edge = conn.vehicle.getRoadID("e1")
        if not edge or edge.startswith(":"):
            return "internal"
        lane = conn.vehicle.getLaneIndex("e1")
        n = conn.edge.getLaneNumber(edge)
        for k in (lane - 1, lane + 1):
            if not 0 <= k < n:
                continue
            lid = f"{edge}_{k}"
            allowed = conn.lane.getAllowed(lid)
            if allowed and "passenger" not in allowed:
                continue
            links = conn.lane.getLinks(lid)
            if not links:
                continue
            succ = conn.lane.getEdgeID(links[0][0])
            conn.vehicle.setRoute("e1", [edge, succ])
            conn.vehicle.changeLane("e1", k, 5.0)
            return "lane_change"
        links = conn.lane.getLinks(f"{edge}_{lane}")
        if links:
            conn.vehicle.setRoute("e1", [edge, conn.lane.getEdgeID(links[-1][0])])
            return "reroute"
    except Exception:  # noqa: BLE001
        return "error"
    return "none"


class _FrozenActive:
    def __init__(self, inner, t_f, log):
        object.__setattr__(self, "inner", inner)
        object.__setattr__(self, "t_f", t_f)
        object.__setattr__(self, "log", log)

    def __setattr__(self, name, value):
        setattr(self.inner, name, value)

    def __call__(self, d, t, states, conn):
        out = self.inner(d, t, states, conn)
        if t >= self.t_f - 1e-9:
            for v in states:
                if v != "e1":
                    conn.vehicle.setSpeed(v, 0.0)
            res = _active_escape(conn)
            self.log[res] = self.log.get(res, 0) + 1
            return {}
        return out


def _patch_active():
    import joint_interception.rl.rollout as ro

    if getattr(ro, "_a121_patched", False):
        return
    original = ro.run_plan

    def run_plan(*args, controller=None, **kwargs):
        if ESC["t"] is not None and controller is not None:
            controller = _FrozenActive(controller, ESC["t"], ESC["log"])
            kwargs["horizon_s"] = ESC["t"] + 61.0
        return original(*args, controller=controller, **kwargs)

    ro.run_plan = run_plan
    ro._a121_patched = True


def active(args):
    import audit_addendum as aa
    from audit_cage_certificate import replay
    from audit_d06_persistence import _witness

    key, m, i, seed, level, team, method, t_c = args
    _patch_active()
    _mode("legacy")
    ESC["t"], ESC["log"] = t_c, {}
    try:
        ep, _ = replay(
            m, i, seed, "PE11", "T", None, "policy", 400.0, kind=METHODS[method], speed=1.0,
            level=level, team=team, learner={"params": _c215()} if method == "plus_opt" else None,
            reward_mode="certificate",
        )  # fmt: skip
        w = _witness(ep)
        out = {
            "key": key,
            "reproduced": bool(w is not None and abs(w[0] - t_c) < 0.05),
            "follow_up": aa._escape_pc(ep, t_c),
            "attempts": dict(ESC["log"]),
        }
    except Exception as error:  # noqa: BLE001
        out = {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    finally:
        ESC["t"] = None
        _mode("checked")
    return out


# -- AB / RC / RP -------------------------------------------------------------------------
def ab(args):
    from run_sensitivity_study import episode as sens_episode

    _mode("checked")
    return sens_episode(args[1:]) | {"key": args[0]}


def rc(args):
    key, which, inner, sealed = args
    _mode("checked")
    try:
        if which == "a99":
            from run_ambush_optimization import episode as e

            r = e(inner)
        else:
            from run_goal_evader_study import episode as e

            r = e(inner)
    finally:
        _mode("checked")
    if "failed" in r:
        return {"key": key, "failed": r["failed"]}
    return {"key": key, "d06": bool(r["d06"]), "sealed_d06": sealed}


def rp(args):
    key, pkg, inner, sealed = args
    _mode("legacy")
    try:
        if pkg == "robustness":
            from run_robustness_study import task as e
        elif pkg in ("sensitivity", "commitment"):
            from run_sensitivity_study import episode as e
        elif pkg == "goal":
            from run_goal_evader_study import episode as e
        else:
            from train_mappo_v2 import episode as e
        r = e(inner)
    finally:
        _mode("checked")
    if "failed" in r:
        return {"key": key, "failed": r["failed"]}
    return {"key": key, "d06": bool(r["d06"]), "sealed_d06": sealed}


def episode(args):
    return {"AB": ab, "AE": active, "RC": rc, "RP": rp}[args[0][:2]](args)


def tasks():
    c215 = _c215()
    ind = dict(c215) | {"independent": 1}
    out = []
    # AB
    for m in TRAINING + DEVELOPMENT:
        for i in range(20):
            for rep in range(2):
                seed = 9500 + i + 100000 * rep
                for level in ("AVOIDANT", "RANDOM", "GOAL_DIRECTED"):
                    for team in (3, 5, 7):
                        for name, p in (("coord", c215), ("indep", ind)):
                            out.append(
                                (
                                    f"AB|{name}|{m}|{i}|{seed}|{level}|{team}",
                                    f"AB|{name}|{m}|{i}|{seed}|{level}|{team}",
                                )
                                + (m, i, seed, "PE18", level, team, "ambush_plus", p, 1.0, True)
                            )
    # AE
    for r in rows(os.path.join(EXP, "20261003_d06_persistence_audit_r01", "results.jsonl")):
        if r.get("t_c") is None:
            continue
        _, method, m, i, seed, level, team = r["key"].split("|")
        out.append((f"AE|{r['key']}", m, int(i), int(seed), level, int(team), method, r["t_c"]))
    rng = random.Random(121)
    # RP: robustness
    rob = [
        r
        for r in rows(os.path.join(EXP, "20261001_robustness_study_r01", "results.jsonl"))
        if "failed" not in r
    ]
    for r in rng.sample(rob, 100):
        pol = r["policy"]
        policy, single = (pol.split("_only_") + [None])[:2] if "_only_" in pol else (pol, None)
        inner = (
            r["block"],
            r["map_id"],
            r["index"],
            r["rep"],
            r["level"],
            r["team"],
            policy,
            single,
            r["traffic"],
        )
        k = "|".join(
            str(r[x])
            for x in ("block", "map_id", "index", "rep", "level", "team", "policy", "traffic")
        )
        out.append((f"RP|robustness|{k}", "robustness", inner, bool(r["d06"])))
    # RP: sensitivity r02 (test blocks)
    with open(os.path.join(EXP, "20261002_sensitivity_r02", "state.pkl"), "rb") as h:
        sst = pickle.load(h)
    from joint_interception.native.ambush_plus import DEFAULTS

    old_defaults = {k: v for k, v in DEFAULTS.items() if k not in ("commit_s", "independent")}
    pmap = {"tuned7": sst["tuned"], "c215": c215, "default": old_defaults, "pursuit": None}
    sens = [
        r for r in rows(os.path.join(EXP, "20261002_sensitivity_r02", "results.jsonl"))
        if r["key"].startswith(("T7|", "SP|")) and "failed" not in r
    ]  # fmt: skip
    for r in rng.sample(sens, 100):
        block, pname, m, i, seed, level, team, psf = r["key"].split("|")
        kind = "pursuit" if pname == "pursuit" else "ambush_plus"
        inner = (
            r["key"],
            m,
            int(i),
            int(seed),
            "PE12",
            level,
            int(team),
            kind,
            pmap[pname],
            float(psf),
            True,
        )
        out.append((f"RP|sensitivity|{r['key']}", "sensitivity", inner, bool(r["d06"])))
    # RP: commitment
    com = [
        r
        for r in rows(os.path.join(EXP, "20261003_commitment_r01", "results.jsonl"))
        if "failed" not in r
    ]
    for r in rng.sample(com, 100):
        _, c, m, i, seed, level, team = r["key"].split("|")
        p = dict(c215) | {"commit_s": float(c)}
        inner = (
            r["key"],
            m,
            int(i),
            int(seed),
            "PE14",
            level,
            int(team),
            "ambush_plus",
            p,
            1.0,
            True,
        )
        out.append((f"RP|commitment|{r['key']}", "commitment", inner, bool(r["d06"])))
    # RP + RC: goal-directed
    import run_goal_evader_study as gs

    gseal = {
        r["key"]: r for r in rows(os.path.join(EXP, "20261003_goal_evader_r01", "results.jsonl"))
    }
    gtasks = [t for t in gs.tasks() if t[0] in gseal and "failed" not in gseal[t[0]]]
    for t in rng.sample(gtasks, 100):
        out.append((f"RP|goal|{t[0]}", "goal", t, bool(gseal[t[0]]["d06"])))
    for t in gtasks:
        if t[0].startswith("GD|"):
            out.append((f"RC|goal|{t[0]}", "goal", t, bool(gseal[t[0]]["d06"])))
    # RP: MAPPO-v2 test
    import train_mappo_v2 as tm

    with open(os.path.join(EXP, "20261004_mappo_v2_r01", "state.pkl"), "rb") as h:
        mst = pickle.load(h)
    with open(os.path.join(EXP, "20261002_mappo_r01", "state.pkl"), "rb") as h:
        old = pickle.load(h)["runs"]
    pols = [
        ("planner_c215", "ambush_plus", None, None, None),
        ("teacher_v2", "mappo_v2", "mlp", None, "teacher"),
        ("pursuit", "pursuit", None, None, None),
        ("old_mlp", "mappo", "mlp", old["mlp_s1"]["best_model"], "greedy"),
        ("old_kan", "mappo", "kan", old["kan_s1"]["best_model"], "greedy"),
    ]
    for name, run in sorted(mst["runs"].items()):
        pols.append((f"v2_{name}", "mappo_v2", name.split("_s")[0], run["best_model"], "greedy"))
    mseal = {r["key"]: r for r in rows(os.path.join(EXP, "20261004_mappo_v2_r01", "results.jsonl"))}
    mtasks = [t for t in tm.test_tasks(pols) if t[0] in mseal and "failed" not in mseal[t[0]]]
    for t in rng.sample(mtasks, 100):
        out.append((f"RP|mappo_v2|{t[0]}", "mappo_v2", t, bool(mseal[t[0]]["d06"])))
    # RC: A-99 test main cohort
    params = {"plus_opt": c215, "plus_default": None, "ambush_a95": None, "pursuit": None}
    kinds = {
        "plus_opt": "ambush_plus",
        "plus_default": "ambush_plus",
        "ambush_a95": "ambush",
        "pursuit": "pursuit",
    }
    a99 = rows(os.path.join(A99, "results.jsonl"))
    for r in a99:
        k = r["key"].split("|")
        if k[0] != "test" or k[1] not in kinds or "failed" in r:
            continue
        _, p, m, i, seed, level, team = k
        pp = params[p] if p != "plus_default" else old_defaults
        inner = (r["key"], m, int(i), int(seed), "PE11", level, int(team), kinds[p], pp, None, True)
        out.append((f"RC|a99|{r['key']}", "a99", inner, bool(r["d06"])))
    order = {"AB": 0, "AE": 1, "RP": 2, "RC": 3}
    return sorted(out, key=lambda t: order[t[0][:2]])


def run_with_timeout(store, pool, tasks, deadline, stall_s=900.0):
    """Like Store.run, but never blocks past the deadline: waits for results with a timeout and
    gives up a chunk after `stall_s` seconds without any result (the pool is then terminated)."""
    todo = [t for t in tasks if t[0] not in store.rows]
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
    return all(t[0] in store.rows for t in tasks)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    deadline = time.time() + 60 * args.budget_min
    todo = tasks()
    if args.smoke:
        seen, pick = {}, []
        for t in todo:
            p = t[0].split("|")[0] + "|" + t[0].split("|")[1]
            if seen.get(p, 0) < 1:
                seen[p] = seen.get(p, 0) + 1
                pick.append(t)
        todo = pick
    store = Store(package)
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        done = run_with_timeout(store, pool, todo, deadline)
    n = sum(t[0] in store.rows for t in todo)
    print(json.dumps({"stage": "done" if done else "chunk_done", "done": n, "of": len(todo)}))
    return 0


__all__ = ["math"]

if __name__ == "__main__":
    raise SystemExit(main())
