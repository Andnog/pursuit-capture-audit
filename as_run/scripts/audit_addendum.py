"""Versioned audit addendum (A-115): completion of follow-up and a negative control.

B1  the 188 right-censored PC persistence replays (A-108), frozen, horizon extended to t_c + 61 s;
B2T the TEST certificate audits (A-110 CA) and B2F the A-91 certificate audits, hold condition,
    horizon extended to t_cert + 61 s; gate-escape time, network-exit time, censoring, joint escape;
B3  null team: five pursuers drive random routes without pursuing (7 non-TEST cities, salt PN1);
B6  prevalence of the "no route" branch in 100 natural A-99 test episodes per method.
Original packages are read only. The horizon extension and the freeze wrap the engine call inside
the audit worker; no source module is modified. Resumable chunks (--budget-min).
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from run_ambush_optimization import Store, _init  # noqa: E402
from run_endpoint_validation import DEVELOPMENT, TRAINING, certified_at  # noqa: E402

EXP = os.path.join(ROOT, "experiments")
A99 = os.path.join(EXP, "20261002_ambush_optimization_r01")
METHODS = {"plus_opt": "ambush_plus", "ambush_a95": "ambush", "pursuit": "pursuit"}
CTRL: dict = {"horizon": None, "freeze": None}


class _Frozen:
    def __init__(self, inner, t_f):
        object.__setattr__(self, "inner", inner)
        object.__setattr__(self, "t_f", t_f)

    def __setattr__(self, name, value):
        setattr(self.inner, name, value)

    def __call__(self, d, t, states, conn):
        out = self.inner(d, t, states, conn)
        if t >= self.t_f - 1e-9:
            for v in states:
                if v != "e1":
                    conn.vehicle.setSpeed(v, 0.0)
            return {}
        return out


def _patch():
    import joint_interception.rl.rollout as ro

    if getattr(ro, "_a115_patched", False):
        return
    original = ro.run_plan

    def run_plan(*args, controller=None, **kwargs):
        if CTRL["freeze"] is not None and controller is not None:
            controller = _Frozen(controller, CTRL["freeze"])
        if CTRL["horizon"] is not None:
            kwargs["horizon_s"] = CTRL["horizon"]
        return original(*args, controller=controller, **kwargs)

    ro.run_plan = run_plan
    ro._a115_patched = True


def _c215():
    with open(os.path.join(A99, "summary.json"), encoding="utf-8") as h:
        return json.load(h)["final_params"]


def _no_route(ep):
    return sum(1 for r in getattr(ep, "refused", []) or [] if "no route" in r.get("why", ""))


def _escape_pc(ep, t_c, window=60.0):
    frames = [f for f in ep.trace if f.time_s >= t_c - 1e-9]
    if not frames or "e1" not in frames[0].vehicles:
        return None
    x0, y0 = frames[0].vehicles["e1"].x, frames[0].vehicles["e1"].y
    moved, left_at = 0.0, None
    for f in frames:
        if f.time_s > t_c + window + 1e-9:
            break
        e = f.vehicles.get("e1")
        if e is None:
            left_at = f.time_s
            break
        moved = max(moved, math.dist((x0, y0), (e.x, e.y)))
    return {
        "follow_up_s": round(min(window, frames[-1].time_s - t_c), 1),
        "moved_m": round(moved, 1),
        "left_at": left_at,
        "escape": bool(left_at is not None or moved > 10.0),
    }


def b1(args):
    from audit_cage_certificate import replay

    key, m, i, seed, level, team, method, t_c = args
    _patch()
    CTRL["freeze"], CTRL["horizon"] = t_c, t_c + 61.0
    try:
        ep, _ = replay(
            m, i, seed, "PE11", "T", None, "policy", 400.0, kind=METHODS[method], speed=1.0,
            level=level, team=team, learner={"params": _c215()} if method == "plus_opt" else None,
            reward_mode="certificate",
        )  # fmt: skip
        out = {"key": key, "t_c": t_c, "frozen": _escape_pc(ep, t_c), "no_route": _no_route(ep)}
    except Exception as error:  # noqa: BLE001
        out = {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    finally:
        CTRL["freeze"] = CTRL["horizon"] = None
    return out


def b2(args):
    from audit_cage_certificate import replay
    from train_caging_pilot import _net

    key, m, i, seed, salt, level, team, kind, cert, expected = args
    _patch()
    CTRL["horizon"] = max(300.0, expected + 61.0)
    try:
        ep, recs = replay(
            m, i, seed, salt, "T", None, "hold", 400.0, kind=kind, hold_on=cert, speed=1.0,
            level=level, team=team, reward_mode="certificate",
        )  # fmt: skip
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    finally:
        CTRL["horizon"] = None
    flags = [
        {
            "t": r["t"],
            "c": r["caged_now"]
            if cert == "junction"
            else (r["caged_lane_now"] and len(r["gates"]) >= 1),
        }
        for r in recs
    ]
    t_cert = certified_at(flags, "c")
    if t_cert is None:
        return {"key": key, "reproduced": False}
    at = next(r for r in recs if abs(r["t"] - t_cert) < 1e-6)
    gates, net = set(at["gates"]), _net(m)
    gate_t, edge0 = None, at["edge"]
    for r in recs:
        if r["t"] < t_cert - 1e-6:
            continue
        e = r["edge"]
        if e == edge0 or e.startswith(":") or e not in net.edges:
            continue
        if net.edges[e].from_node in gates:
            gate_t = r["t"] - t_cert
            break
        edge0 = e
    last_e1 = max((f.time_s for f in ep.trace if "e1" in f.vehicles), default=0.0)
    end = ep.trace[-1].time_s if ep.trace else 0.0
    exit_t = (last_e1 - t_cert) if (ep.evader_exited and last_e1 < end - 1e-6) else None
    follow = round(min(60.0, end - t_cert), 1)
    gate60 = gate_t is not None and gate_t <= 60.0
    exit60 = exit_t is not None and exit_t <= 60.0
    return {
        "key": key,
        "reproduced": abs(t_cert - expected) < 1e-6,
        "t_cert": t_cert,
        "follow_up_s": follow,
        "gate_escape_s": gate_t,
        "exit_s": exit_t,
        "gate_escape_60": gate60,
        "exit_60": exit60,
        "joint_escape_60": gate60 or exit60,
        "censored": follow < 60.0 - 1e-6 and not (gate60 or exit60),
        "d06": bool(ep.contact_capture),
        "no_route": _no_route(ep),
    }


class Wander:
    """Null team: each pursuer drives to random reachable edges, never towards the evader."""

    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.target: dict = {}
        self.stats = {"steps": 0}
        self.history: list = []

    def __call__(self, ctx):
        self.stats["steps"] += 1
        cmds = {}
        for v in sorted(ctx["per"]):
            reach = ctx["per"][v][1]
            tgt = self.target.get(v)
            st = ctx["states"].get(v)
            arrived = tgt is not None and st is not None and st[0] == tgt and st[3] < 0.5
            if tgt is None or arrived:
                cands = sorted(
                    e for e, t in reach.items() if 20.0 <= t <= 120.0 and not e.startswith(":")
                )
                if not cands:
                    continue
                self.target[v] = tgt = self.rng.choice(cands)
                cmds[v] = ("seg", tgt, None)
        return cmds


def b3(args):
    from audit_cage_certificate import _net, _run
    from joint_interception.domain.contracts import load_domain
    from joint_interception.domain.geometry import body_separation_m
    from joint_interception.simulator.evader import EvaderLevel
    from joint_interception.world.construction import make_scenario

    key, m, i, seed, level = args
    domain = load_domain()
    net = _net(m)
    sc = make_scenario(net, m, EvaderLevel[level], [f"p{k}" for k in range(1, 6)], f"PN1s{i}")
    if len(sc.pursuer_starts) != 5:
        return {"key": key, "failed": "ValueError: scenario could not place the team"}
    label = f"nul{m[:3]}{i}_{seed}"
    try:
        ep = _run(
            net, m, sc, domain, lambda obs: {}, 1.0, seed, label, "T", 300.0, None, None,
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
    near5 = near10 = centre5 = False
    for f in ep.trace:
        e = f.vehicles.get("e1")
        if e is None:
            continue
        for v, p in f.vehicles.items():
            if v == "e1":
                continue
            c = math.dist((e.x, e.y), (p.x, p.y))
            centre5 = centre5 or c <= 5.0
            if c <= 16.0:
                d = body_separation_m(e.rectangle(), p.rectangle())
                near5, near10 = near5 or d <= 5.0, near10 or d <= 10.0
    return {
        "key": key,
        "d06": bool(ep.contact_capture),
        "prox_5m": near5,
        "prox_10m": near10,
        "prox_5m_centre": centre5,
        "collided": ep.collided,
    }


def b6(args):
    from audit_cage_certificate import replay

    key, m, i, seed, level, team, method = args
    try:
        ep, _ = replay(
            m, i, seed, "PE11", "T", None, "policy", 300.0, kind=METHODS[method], speed=1.0,
            level=level, team=team, learner={"params": _c215()} if method == "plus_opt" else None,
            reward_mode="certificate",
        )  # fmt: skip
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    refused = getattr(ep, "refused", []) or []
    return {
        "key": key,
        "no_route": _no_route(ep),
        "refused_total": len(refused),
        "d06": bool(ep.contact_capture),
    }


def episode(args):
    return {"B1": b1, "B2": b2, "B3": b3, "B6": b6}[args[0][:2]](args)


def tasks():
    out = []
    # B1: censored persistence replays.
    with open(os.path.join(EXP, "20261003_d06_persistence_audit_r01", "results.jsonl")) as h:
        for x in h:
            r = json.loads(x)
            if r.get("frozen") and r["frozen"]["window_s"] < 60.0 - 1e-6:
                _, method, m, i, seed, level, team = r["key"].split("|")
                out.append(
                    (f"B1|{r['key']}", m, int(i), int(seed), level, int(team), method, r["t_c"])
                )
    # B2T: TEST certificate audits.
    with open(os.path.join(EXP, "20261003_test_confirmation_r01", "results.jsonl")) as h:
        for x in h:
            r = json.loads(x)
            if r["key"].startswith("CA|") and r.get("reproduced"):
                _, cert, m, i, seed, level, team = r["key"].split("|")
                out.append(
                    (f"B2T|{r['key']}", m, int(i), int(seed), "PT1", level, int(team), "pursuit")
                    + (cert, r["t_cert"])
                )
    # B2F: A-91 certificate audits (salt PE7, seed 9500 + index, AVOIDANT, team 3).
    with open(os.path.join(EXP, "20261001_final_study_r01", "audit.jsonl")) as h:
        for x in h:
            r = json.loads(x)
            if r.get("reproduced"):
                k = f"B2F|{r['policy']}|{r['map_id']}|{r['index']}|{r['cert']}"
                out.append(
                    (k, r["map_id"], r["index"], 9500 + r["index"], "PE7", "AVOIDANT", 3)
                    + (r["policy"], r["cert"], r["t_cert"])
                )
    # B3: null team.
    for m in TRAINING + DEVELOPMENT:
        for i in range(20):
            for rep in range(2):
                for level in ("AVOIDANT", "RANDOM"):
                    seed = 9500 + i + 100000 * rep
                    out.append((f"B3|{m}|{i}|{seed}|{level}|5", m, i, seed, level))
    # B6: 100 natural A-99 test episodes per method.
    with open(os.path.join(A99, "results.jsonl")) as h:
        keys = [
            json.loads(x)["key"]
            for x in h
            if json.loads(x)["key"].split("|")[0] == "test"
            and json.loads(x)["key"].split("|")[1] in METHODS
            and "failed" not in json.loads(x)
        ]
    rng = random.Random(115)
    for method in METHODS:
        pick = rng.sample(sorted(k for k in keys if k.split("|")[1] == method), 100)
        for k in pick:
            _, _, m, i, seed, level, team = k.split("|")
            out.append((f"B6|{k}", m, int(i), int(seed), level, int(team), method))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--only", default="", help="smoke test: comma-separated task keys prefixes")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    deadline = time.time() + 60 * args.budget_min
    todo = tasks()
    if args.only:
        pre = tuple(args.only.split(","))
        todo = [t for t in todo if t[0].startswith(pre)]
    if args.limit:
        todo = todo[: args.limit]
    store = Store(package)
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        done = store.run(pool, todo, deadline, episode)
    n = sum(t[0] in store.rows for t in todo)
    print(json.dumps({"stage": "done" if done else "chunk_done", "done": n, "of": len(todo)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
