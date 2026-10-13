"""D06 persistence audit (A-108): is a contact capture a held capture?

Every D06-positive test episode of `plus_opt` (c2_15), `ambush_a95` and `pursuit` in the sealed A-99
test (salt PE11) is replayed twice:
- natural: the sealed episode (determinism check); t_c = end of the first D06 witness;
- frozen: identical until t_c, then every pursuer is held at speed 0 for the rest of the episode.
Escape: the evader is more than ESCAPE_M from its t_c position within WINDOW_S (or leaves the
network). Static measures at t_c (natural pass): red/yellow signal within 40 m; a lane of the
evader's edge with no pursuer ahead. Resumable chunks (--budget-min). The freeze wraps the engine
controller inside the audit worker only; no source module is modified.
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

from run_ambush_optimization import Store, _init  # noqa: E402
from run_robustness_study import bootstrap  # noqa: E402

SOURCE = os.path.join(ROOT, "experiments", "20261002_ambush_optimization_r01")
METHODS = {"plus_opt": "ambush_plus", "ambush_a95": "ambush", "pursuit": "pursuit"}
ESCAPE_M = 10.0
WINDOW_S = 60.0
SIGNAL_M = 40.0
FREEZE: dict = {"t": None}


class _Frozen:
    """Engine controller wrapper: the policy runs (and the probe records) until `t_f`; from then on
    every pursuer is held at speed 0 and no new command is issued."""

    def __init__(self, inner, t_f):
        object.__setattr__(self, "inner", inner)
        object.__setattr__(self, "t_f", t_f)

    def __setattr__(self, name, value):  # run_plan sets .evader / .decision_s on the controller
        setattr(self.inner, name, value)

    def __call__(self, d, t, states, conn):
        out = self.inner(d, t, states, conn)
        if t >= self.t_f - 1e-9:
            if FREEZE.get("snap") is None:
                FREEZE["snap"] = _snapshot(t, states, conn)
            for v in states:
                if v != "e1":
                    conn.vehicle.setSpeed(v, 0.0)
            return {}
        return out


def _snapshot(t, states, conn):
    """Exact static measures at the freeze: another lane of the evader's edge with no pursuer
    ahead (a lane-change way round the finisher), and a red or yellow signal ahead of the evader."""
    out = {"t": round(t, 1), "edge": None, "lanes": None, "free_lane": None, "red_signal": None}
    try:
        edge = conn.vehicle.getRoadID("e1")
        out["edge"] = edge
        tls = conn.vehicle.getNextTLS("e1")
        out["red_signal"] = bool(tls and tls[0][2] <= SIGNAL_M and str(tls[0][3]) in "rRyYu")
        if edge.startswith(":"):
            out["free_lane"] = "internal"
            return out
        pos = conn.vehicle.getLanePosition("e1")
        lanes = []
        for k in range(conn.edge.getLaneNumber(edge)):
            allowed = conn.lane.getAllowed(f"{edge}_{k}")
            if not allowed or "passenger" in allowed:
                lanes.append(f"{edge}_{k}")
        blocked = {
            conn.vehicle.getLaneID(v)
            for v in states
            if v != "e1"
            and conn.vehicle.getRoadID(v) == edge
            and conn.vehicle.getLanePosition(v) > pos
        }
        own = conn.vehicle.getLaneID("e1")
        out["lanes"] = len(lanes)
        out["evader_lane_blocked_on_edge"] = own in blocked
        out["free_lane"] = any(ln not in blocked for ln in lanes if ln != own)
    except Exception as error:  # noqa: BLE001
        out["error"] = str(error)[:80]
    return out


def _patch():
    import joint_interception.rl.rollout as ro

    if getattr(ro, "_a108_patched", False):
        return
    original = ro.run_plan

    def run_plan(*args, controller=None, **kwargs):
        if FREEZE["t"] is not None and controller is not None:
            controller = _Frozen(controller, FREEZE["t"])
        return original(*args, controller=controller, **kwargs)

    ro.run_plan = run_plan
    ro._a108_patched = True


def _replay(m, i, seed, level, team, kind, params):
    from audit_cage_certificate import replay

    return replay(
        m,
        i,
        seed,
        "PE11",
        "T",
        None,
        "policy",
        300.0,
        kind=kind,
        speed=1.0,
        level=level,
        team=team,
        learner={"params": params} if params is not None else None,
        reward_mode="certificate",
    )


def _witness(ep):
    """Earliest capture: the first frame at which any pursuer's continuous D06 run reaches the
    dwell (the judge reports the first pursuer in id order, not the earliest capture)."""
    from joint_interception.domain.contracts import CaptureParameters, load_domain
    from joint_interception.evaluation.capture_judge import _conditions_hold

    params = CaptureParameters.from_domain(load_domain())
    since: dict[str, float] = {}
    for f in ep.trace:
        e = f.vehicles.get("e1")
        for pid, p in f.vehicles.items():
            if pid == "e1":
                continue
            if e is not None and _conditions_hold(p, e, params)[0]:
                start = since.setdefault(pid, f.time_s)
                if f.time_s - start + 1e-9 >= params.dwell_time_s:
                    return f.time_s, pid
            else:
                since.pop(pid, None)
    return None


def _escape(ep, t_c):
    frames = [f for f in ep.trace if f.time_s >= t_c - 1e-9]
    if not frames or "e1" not in frames[0].vehicles:
        return None
    x0, y0 = frames[0].vehicles["e1"].x, frames[0].vehicles["e1"].y
    out = {"window_s": round(min(WINDOW_S, frames[-1].time_s - t_c), 1)}
    for w in (10.0, 30.0, WINDOW_S):
        moved, left = 0.0, False
        for f in frames:
            if f.time_s > t_c + w + 1e-9:
                break
            e = f.vehicles.get("e1")
            if e is None:
                left = True
                break
            moved = max(moved, math.dist((x0, y0), (e.x, e.y)))
        out[f"escape_{int(w)}s"] = bool(left or moved > ESCAPE_M)
        out[f"moved_{int(w)}s"] = round(moved, 1)
    return out


def task(args):
    key, m, i, seed, level, team, kind, params = args
    _patch()
    row = {"key": key}
    try:
        FREEZE["t"] = None
        ep, _ = _replay(m, i, seed, level, team, kind, params)
        w = _witness(ep)
        row["reproduced"] = w is not None and bool(ep.contact_capture)
        if w is None:
            return row
        t_c, finisher = w
        row.update(t_c=round(t_c, 1), finisher=finisher)
        row["natural"] = _escape(ep, t_c)
        FREEZE["t"], FREEZE["snap"] = t_c, None
        ep2, _ = _replay(m, i, seed, level, team, kind, params)
        w2 = _witness(ep2)
        row["frozen_same_witness"] = w2 is not None and abs(w2[0] - t_c) < 1e-6
        row["frozen"] = _escape(ep2, t_c)
        row["static"] = FREEZE["snap"] or {}
    except Exception as error:  # noqa: BLE001
        row["failed"] = f"{type(error).__name__}: {str(error)[:120]}"
    finally:
        FREEZE["t"], FREEZE["snap"] = None, None
    return row


def tasks():
    with open(os.path.join(SOURCE, "summary.json"), encoding="utf-8") as h:
        c215 = json.load(h)["final_params"]
    out = []
    with open(os.path.join(SOURCE, "results.jsonl"), encoding="utf-8") as h:
        for x in h:
            r = json.loads(x)
            k = r["key"].split("|")
            if k[0] != "test" or k[1] not in METHODS or "failed" in r or not r["d06"]:
                continue
            _, method, m, i, seed, level, team = k
            params = c215 if method == "plus_opt" else None
            out.append((r["key"], m, int(i), int(seed), level, int(team), METHODS[method], params))
    return sorted(out)


def summarise(package, store):
    sealed = {}
    with open(os.path.join(SOURCE, "results.jsonl"), encoding="utf-8") as h:
        for x in h:
            r = json.loads(x)
            k = r["key"].split("|")
            if k[0] == "test" and k[1] in METHODS and "failed" not in r:
                sealed[r["key"]] = r
    rows = {k: r for k, r in store.rows.items() if k in sealed}
    out = {"per_method": {}, "claims": {}, "n_audited": len(rows)}

    def rate(xs):
        n = len(xs)
        if not n:
            return None
        p = sum(xs) / n
        z = 1.96
        c = (p + z * z / (2 * n)) / (1 + z * z / n)
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
        return [round(p, 3), round(c - h, 3), round(c + h, 3), n]

    for method in METHODS:
        rs = [r for k, r in rows.items() if k.split("|")[1] == method]
        ok = [r for r in rs if r.get("reproduced") and "frozen" in r and r["frozen"]]
        out["per_method"][method] = {
            "d06_positive": len(rs),
            "failed": sum("failed" in r for r in rs),
            "reproduced": rate([bool(r.get("reproduced")) for r in rs if "failed" not in r]),
            "frozen_same_witness": rate([bool(r.get("frozen_same_witness")) for r in ok]),
            "frozen_escape_60s": rate([r["frozen"]["escape_60s"] for r in ok]),
            "frozen_escape_10s": rate([r["frozen"]["escape_10s"] for r in ok]),
            "natural_escape_10s": rate([r["natural"]["escape_10s"] for r in ok if r["natural"]]),
            "natural_escape_60s": rate([r["natural"]["escape_60s"] for r in ok if r["natural"]]),
            "red_signal": rate([bool(r["static"].get("red_signal")) for r in ok]),
            "free_lane": rate([r["static"].get("free_lane") is True for r in ok]),
            "internal_edge": rate([r["static"].get("free_lane") == "internal" for r in ok]),
            "frozen_escape_given_free_lane": rate(
                [r["frozen"]["escape_60s"] for r in ok if r["static"].get("free_lane") is True]
            ),
            "frozen_escape_given_no_free_lane": rate(
                [r["frozen"]["escape_60s"] for r in ok if r["static"].get("free_lane") is False]
            ),
            "window_censored": sum(r["frozen"]["window_s"] < WINDOW_S - 1e-6 for r in ok),
            "primary_pass": None,
        }
        fe = out["per_method"][method]["frozen_escape_60s"]
        out["per_method"][method]["primary_pass"] = bool(fe and fe[0] <= 0.10)

    # Persistent capture for every sealed test episode (non-captures stay 0), seed-averaged per
    # scenario, paired across methods; same estimand and bootstrap as A-99.
    def persistent(key):
        r = sealed[key]
        if not r["d06"]:
            return 0.0
        a = rows.get(key)
        if not a or "failed" in a or not a.get("reproduced") or not a.get("frozen"):
            return float("nan")
        return 0.0 if a["frozen"]["escape_60s"] else 1.0

    by = {}
    for key in sealed:
        _, method, m, i, seed, level, team = key.split("|")
        by.setdefault((method, level, int(team), m, int(i)), {})[seed] = (
            persistent(key),
            float(sealed[key]["d06"]),
        )
    mean = {}
    for k, v in by.items():
        vals = [p for p, _ in v.values() if not math.isnan(p)]
        mean[k] = (sum(vals) / len(vals) if vals else None, sum(d for _, d in v.values()) / len(v))

    def per(method, level, team, idx):
        return {
            k[3:]: x[idx]
            for k, x in mean.items()
            if k[:3] == (method, level, team) and x[idx] is not None
        }

    pooled = {"persistent": [], "d06": []}
    for level in ("AVOIDANT", "RANDOM"):
        for team in (3, 5, 7):
            cell = {}
            for idx, name in ((1, "d06"), (0, "persistent")):
                o, a, p = (per(x, level, team, idx) for x in METHODS)
                ks = sorted(set(o) & set(a) & set(p))
                cell[name] = {
                    "n": len(ks),
                    "plus_opt": bootstrap([o[k] for k in ks]),
                    "ambush_a95": bootstrap([a[k] for k in ks]),
                    "pursuit": bootstrap([p[k] for k in ks]),
                    "opt_minus_pursuit": bootstrap([o[k] - p[k] for k in ks]),
                    "opt_minus_a95": bootstrap([o[k] - a[k] for k in ks]),
                }
                pooled[name] += [o[k] - a[k] for k in ks]
            out["claims"][f"{level}_team{team}"] = cell
    out["claims"]["pooled_opt_minus_a95"] = {k: bootstrap(v) for k, v in pooled.items()}
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0, help="smoke test: first N tasks only")
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    deadline = time.time() + 60 * args.budget_min
    todo = tasks()
    if args.limit:
        todo = todo[: args.limit]
    store = Store(package)
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        done = store.run(pool, todo, deadline, task)
    print(json.dumps({"done": sum(t[0] in store.rows for t in todo), "of": len(todo)}), flush=True)
    if done and not args.limit:
        print(json.dumps(summarise(package, store)["per_method"], indent=1), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
