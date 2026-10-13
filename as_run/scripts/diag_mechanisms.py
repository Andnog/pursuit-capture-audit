"""Mechanism diagnostics (A-123, post hoc, descriptive; not gated).

M1  lane duplication: coordinated vs independent PLB (A-121 ablation arms) on fresh scenarios (salt
    DGM1, 7 non-TEST cities, AVOIDANT / RANDOM / GOAL_DIRECTED, team 5). For every planner step we
    record the stop targets (edge, lane) and count steps where two or more pursuers share a target.
M2  trajectory identity of the dispatch fix: episodes run in legacy and checked dispatch mode; the
    full traces (all vehicles, every 0.1 s) are compared, not only the OC outcome.
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

A99 = os.path.join(ROOT, "experiments", "20261002_ambush_optimization_r01")


def _c215():
    with open(os.path.join(A99, "summary.json"), encoding="utf-8") as h:
        return json.load(h)["final_params"]


def _replay(m, i, seed, salt, level, team, kind, params):
    from audit_cage_certificate import replay

    return replay(
        m, i, seed, salt, "T", None, "policy", 300.0, kind=kind, speed=1.0, level=level, team=team,
        learner={"params": params} if params is not None else None, reward_mode="certificate",
    )  # fmt: skip


def m1(args):
    from joint_interception.native import ambush_plus

    key, m, i, seed, level, team, independent = args
    log = {"steps": 0, "dup_steps": 0, "pairs_same_lane": 0, "targets": 0}
    original = ambush_plus.AmbushPlusPlanner.__call__

    def wrapped(self, ctx):
        cmds = original(self, ctx)
        lanes = [(c[1], c[3]) for c in cmds.values() if c is not None and len(c) > 3]
        log["steps"] += 1
        log["targets"] += len(lanes)
        dup = len(lanes) - len(set(lanes))
        log["pairs_same_lane"] += dup
        log["dup_steps"] += int(dup > 0)
        return cmds

    ambush_plus.AmbushPlusPlanner.__call__ = wrapped
    try:
        p = dict(_c215()) | {"independent": independent}
        ep, _ = _replay(m, i, seed, "DGM1", level, team, "ambush_plus", p)
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    finally:
        ambush_plus.AmbushPlusPlanner.__call__ = original
    return {"key": key, "d06": bool(ep.contact_capture), **log}


def m2(args):
    import joint_interception.native.engine as engine

    key, m, i, seed, level, team, kind, params_name = args
    params = _c215() if params_name == "c215" else None
    traces, outcomes, events = {}, {}, {}
    try:
        for mode in ("legacy", "checked"):
            engine.DISPATCH_MODE = mode
            ep, _ = _replay(m, i, seed, "PE11", level, team, kind, params)
            traces[mode] = [
                (
                    round(f.time_s, 1),
                    tuple(sorted((v, round(p.x, 3), round(p.y, 3)) for v, p in f.vehicles.items())),
                )
                for f in ep.trace
            ]
            outcomes[mode] = bool(ep.contact_capture)
            events[mode] = sum(1 for e in (ep.events or []) if e.get("kind") == "dispatch")
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    finally:
        engine.DISPATCH_MODE = "checked"
    first_diff = next(
        (a[0] for a, b in zip(traces["legacy"], traces["checked"], strict=False) if a != b), None
    )
    return {
        "key": key,
        "identical_traces": traces["legacy"] == traces["checked"],
        "first_difference_s": first_diff,
        "same_outcome": outcomes["legacy"] == outcomes["checked"],
        "dispatch_events": events,
    }


def episode(args):
    return m1(args) if args[0].startswith("M1|") else m2(args)


def tasks():
    out = []
    for m in TRAINING + DEVELOPMENT:
        for i in range(5):
            for level in ("AVOIDANT", "RANDOM", "GOAL_DIRECTED"):
                for ind in (0, 1):
                    out.append((f"M1|{ind}|{m}|{i}|{level}|5", m, i, 9500 + i, level, 5, ind))
    with open(os.path.join(A99, "results.jsonl"), encoding="utf-8") as h:
        keys = [json.loads(x)["key"] for x in h]
    picked = [k for k in keys if k.startswith(("test|plus_opt|", "test|pursuit|"))][::40][:60]
    for k in picked:
        _, p, m, i, seed, level, team = k.split("|")
        kind, pn = ("ambush_plus", "c215") if p == "plus_opt" else ("pursuit", None)
        out.append((f"M2|{k}", m, int(i), int(seed), level, int(team), kind, pn))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=40.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    store = Store(package)
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        done = store.run(pool, tasks(), time.time() + 60 * args.budget_min, episode)
    print(json.dumps({"done": done, "rows": len(store.rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
