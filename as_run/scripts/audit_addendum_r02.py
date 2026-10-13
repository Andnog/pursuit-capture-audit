"""Audit addendum r02 (A-119): capture witness for the 188 extended persistence cases, and the
sensitivity of results to the R9 dispatch-bookkeeping defect.

W  each of the 188 cases extended in r01 (B1) is replayed with legacy dispatch, naturally and frozen
   (horizon t_c + 61 s). Recorded: reproduced capture time and finisher in both runs, the vehicle
   states at t_c in both runs (equality = the intervention starts from the historical state), and
   the 60-s follow-up.
S  200 sampled A-99 test episodes per method, run in legacy and in checked dispatch mode: OC
   outcome, capture time and every non-accepted dispatch (no_route / rejected / fallback).
Sealed packages are read only; the engine mode, the freeze and the horizon are set inside the audit
worker. Resumable chunks (--budget-min).
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

from run_ambush_optimization import Store, _init  # noqa: E402

EXP = os.path.join(ROOT, "experiments")
A99 = os.path.join(EXP, "20261002_ambush_optimization_r01")
METHODS = {"plus_opt": "ambush_plus", "ambush_a95": "ambush", "pursuit": "pursuit"}


def _mode(mode):
    import joint_interception.native.engine as engine

    engine.DISPATCH_MODE = mode


def _replay(m, i, seed, level, team, method, post=300.0):
    import audit_addendum as aa
    from audit_cage_certificate import replay

    return replay(
        m, i, seed, "PE11", "T", None, "policy", post, kind=METHODS[method], speed=1.0,
        level=level, team=team, learner={"params": aa._c215()} if method == "plus_opt" else None,
        reward_mode="certificate",
    )  # fmt: skip


def _state_at(ep, t):
    frame = min(ep.trace, key=lambda f: abs(f.time_s - t))
    return {
        v: [round(p.x, 3), round(p.y, 3), round(p.speed_mps, 3)]
        for v, p in sorted(frame.vehicles.items())
    }, round(frame.time_s, 1)


def witness(args):
    import audit_addendum as aa
    from audit_d06_persistence import _witness

    key, m, i, seed, level, team, method, t_c = args
    aa._patch()
    _mode("legacy")
    out = {"key": key, "t_c_sealed": t_c}
    try:
        ep, _ = _replay(m, i, seed, level, team, method)
        w = _witness(ep)
        out["natural_capture"] = None if w is None else [round(w[0], 1), w[1]]
        nat_state, nat_t = _state_at(ep, t_c)
        aa.CTRL["freeze"], aa.CTRL["horizon"] = t_c, t_c + 61.0
        ep2, _ = _replay(m, i, seed, level, team, method, post=400.0)
        w2 = _witness(ep2)
        out["frozen_capture"] = None if w2 is None else [round(w2[0], 1), w2[1]]
        frz_state, frz_t = _state_at(ep2, t_c)
        out["state_time"] = [nat_t, frz_t]
        out["states_equal_at_t_c"] = nat_state == frz_state
        out["n_vehicles_at_t_c"] = len(frz_state)
        out["reproduced"] = bool(
            w is not None and w2 is not None and abs(w[0] - t_c) < 0.05 and abs(w2[0] - t_c) < 0.05
        )
        out["follow_up"] = aa._escape_pc(ep2, t_c)
    except Exception as error:  # noqa: BLE001
        out["failed"] = f"{type(error).__name__}: {str(error)[:100]}"
    finally:
        aa.CTRL["freeze"] = aa.CTRL["horizon"] = None
        _mode("checked")
    return out


def sensitivity(args):
    from run_test_confirmation import _capture_time

    key, m, i, seed, level, team, method, mode = args
    _mode(mode)
    try:
        ep, _ = _replay(m, i, seed, level, team, method)
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    finally:
        _mode("checked")
    events = [e for e in (getattr(ep, "events", []) or []) if e.get("kind") == "dispatch"]
    counts = {}
    for e in events:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    return {
        "key": key,
        "d06": bool(ep.contact_capture),
        "capture_t": _capture_time(ep) if ep.contact_capture else None,
        "dispatch": counts,
        "refused": len(getattr(ep, "refused", []) or []),
    }


def episode(args):
    return witness(args) if args[0].startswith("W|") else sensitivity(args)


def tasks():
    out = []
    with open(os.path.join(EXP, "20261004_audit_addendum_r01", "results.jsonl")) as h:
        for x in h:
            r = json.loads(x)
            if r["key"].startswith("B1|") and "failed" not in r:
                _, _, method, m, i, seed, level, team = r["key"].split("|")
                out.append(
                    (f"W|{r['key'][3:]}", m, int(i), int(seed), level, int(team), method, r["t_c"])
                )
    with open(os.path.join(A99, "results.jsonl")) as h:
        keys = []
        for x in h:
            r = json.loads(x)
            k = r["key"].split("|")
            if k[0] == "test" and k[1] in METHODS and "failed" not in r:
                keys.append(r["key"])
    rng = random.Random(119)
    for method in METHODS:
        for k in rng.sample(sorted(k for k in keys if k.split("|")[1] == method), 200):
            _, _, m, i, seed, level, team = k.split("|")
            for mode in ("legacy", "checked"):
                out.append((f"S|{mode}|{k}", m, int(i), int(seed), level, int(team), method, mode))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    deadline = time.time() + 60 * args.budget_min
    todo = tasks()
    if args.limit:
        todo = todo[: args.limit] + [t for t in todo if t[0].startswith("S|")][: args.limit]
    store = Store(package)
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        done = store.run(pool, todo, deadline, episode)
    n = sum(t[0] in store.rows for t in todo)
    print(json.dumps({"stage": "done" if done else "chunk_done", "done": n, "of": len(todo)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
