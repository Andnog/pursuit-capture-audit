"""Single-shot confirmation on the TEST cities, and the strongest evader (A-110, pre-registered).

Blocks (package PROTOCOL_EN.md):
- TX: TEST cities (salt PT1), 20 scenarios x 2 SUMO seeds x RANDOM / AVOIDANT / OPTIMAL_ESCAPE
  x teams 3 / 5 / 7 x {c2_15 planner, A-95 ambush, pursuit, MAPPO-KAN, MAPPO-MLP}.
- TS: TEST singles, c2_15 with one pursuer p1..p7 alone (team-7 placement, nested).
- OX / OS: OPTIMAL_ESCAPE on the 7 non-TEST cities (salt PE15), c2_15, A-95, pursuit, and singles.
- CA: every TX pursuit episode whose certificate fired, replayed with the A-72 hold condition.
Frozen methods; resumable chunks (--budget-min); analysis written before launch.
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import pickle
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from run_ambush_optimization import Store, _init  # noqa: E402
from run_endpoint_validation import (  # noqa: E402
    DEVELOPMENT,
    TRAINING,
    certified_at,
    immobilised_at,
)
from run_robustness_study import bootstrap  # noqa: E402

TEST_CITIES = ["chicago_loop", "melbourne_cbd", "salt_lake_city", "minneapolis_downtown"]
LEVELS = ["RANDOM", "AVOIDANT", "OPTIMAL_ESCAPE"]
TEAMS = [3, 5, 7]
SCENARIOS, REPS = 20, 2
METHODS = ["plus_opt", "ambush_a95", "pursuit", "mappo_kan", "mappo_mlp"]
OX_METHODS = ["plus_opt", "ambush_a95", "pursuit"]
AUDIT_WINDOW_S = 60.0
A99 = os.path.join(ROOT, "experiments", "20261002_ambush_optimization_r01", "summary.json")
MAPPO = os.path.join(ROOT, "experiments", "20261002_mappo_r01", "state.pkl")
_CACHE: dict = {}


def _c215():
    if "c215" not in _CACHE:
        with open(A99, encoding="utf-8") as h:
            _CACHE["c215"] = json.load(h)["final_params"]
    return _CACHE["c215"]


def _mappo(head):
    if "mappo" not in _CACHE:
        with open(MAPPO, "rb") as h:
            runs = pickle.load(h)["runs"]
        _CACHE["mappo"] = {n.split("_s")[0]: r["best_model"] for n, r in runs.items()}
    return _CACHE["mappo"][head]


def _kind(method, i):
    if method.startswith("plus_opt"):
        return "ambush_plus", {"params": _c215()}
    if method == "ambush_a95":
        return "ambush", None
    if method == "pursuit":
        return "pursuit", None
    head = method.split("_")[1]
    learner = {
        "params": _c215(),
        "head": head,
        "weights": _mappo(head),
        "mode": "greedy",
        "seed": i,
    }
    return "mappo", learner


def _capture_time(ep):
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
                    return round(f.time_s, 1)
            else:
                since.pop(pid, None)
    return None


def episode(args):
    from audit_cage_certificate import replay
    from joint_interception.domain.geometry import body_separation_m

    key, m, i, seed, salt, level, team, method, single = args
    kind, learner = _kind(method, i)
    try:
        ep, recs = replay(
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
            learner=learner,
            active=None if single is None else [single],
            reward_mode="certificate",
        )
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    row = {"key": key, "d06": bool(ep.contact_capture), "collided": ep.collided}
    if single is not None:
        return row
    near, centre5 = {5.0: False, 10.0: False}, False
    for f in ep.trace:
        e = f.vehicles.get("e1")
        if e is None:
            continue
        for v, p in f.vehicles.items():
            if v == "e1":
                continue
            c = math.dist((e.x, e.y), (p.x, p.y))
            centre5 = centre5 or c <= 5.0
            if c > 16.0:
                continue
            d = body_separation_m(e.rectangle(), p.rectangle())
            for th in near:
                near[th] = near[th] or d <= th
    flags = [
        {"t": r["t"], "cj": r["caged_now"], "cln": r["caged_lane_now"] and len(r["gates"]) >= 1}
        for r in recs
    ]
    compact = [
        {"t": r["t"], "v": r["v_e"], "leader": r["leader"], "follower": r["follower"]}
        | {"signal": r["signal"], "edge": r["edge"]}
        for r in recs
    ]
    immobile = immobilised_at(compact, 10.0, 15.0, 30.0) is not None
    return row | {
        "trapped": bool(ep.contact_capture or immobile),
        "capture_t": _capture_time(ep) if ep.contact_capture else None,
        "prox_5m": near[5.0],
        "prox_10m": near[10.0],
        "prox_5m_centre": centre5,
        "cert_junction_at": certified_at(flags, "cj"),
        "cert_lane_nv_at": certified_at(flags, "cln"),
        "evader_exited": ep.evader_exited,
    }


def cert_audit(args):
    """A-90 audit, with the level, team and seed of the TX episode."""
    from audit_cage_certificate import replay
    from train_caging_pilot import _net

    key, m, i, seed, level, team, cert, expected = args
    try:
        ep, recs = replay(
            m,
            i,
            seed,
            "PT1",
            "T",
            None,
            "hold",
            300.0,
            kind="pursuit",
            hold_on=cert,
            speed=1.0,
            level=level,
            team=team,
            reward_mode="certificate",
        )
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
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
    gates = set(at["gates"])
    net = _net(m)
    window = [r for r in recs if t_cert - 1e-6 <= r["t"] <= t_cert + AUDIT_WINDOW_S + 1e-6]
    escape, edge0 = None, at["edge"]
    for r in window:
        e = r["edge"]
        if e == edge0 or e.startswith(":") or e not in net.edges:
            continue
        if net.edges[e].from_node in gates:
            escape = r["t"] - t_cert
            break
        edge0 = e
    return {
        "key": key,
        "reproduced": abs(t_cert - expected) < 1e-6,
        "t_cert": t_cert,
        "escaped": escape is not None,
        "left_network": ep.evader_exited and escape is None,
        "d06": bool(ep.contact_capture),
    }


def main_tasks():
    out = []
    for block, cities, salt, levels, methods in (
        ("TX", TEST_CITIES, "PT1", LEVELS, METHODS),
        ("OX", TRAINING + DEVELOPMENT, "PE15", ["OPTIMAL_ESCAPE"], OX_METHODS),
    ):
        singles_block = "TS" if block == "TX" else "OS"
        for m in cities:
            for i in range(SCENARIOS):
                for rep in range(REPS):
                    seed = 9500 + i + 100000 * rep
                    for level in levels:
                        base = f"{m}|{i}|{seed}|{level}"
                        for team in TEAMS:
                            for method in methods:
                                out.append(
                                    (f"{block}|{method}|{base}|{team}", m, i, seed, salt, level)
                                    + (team, method, None)
                                )
                        for k in range(1, 8):
                            out.append(
                                (f"{singles_block}|plus_opt_only_p{k}|{base}|7", m, i, seed, salt)
                                + (level, 7, "plus_opt", f"p{k}")
                            )
    return out


def audit_tasks(store):
    out = []
    for k, r in sorted(store.rows.items()):
        p = k.split("|")
        if p[0] != "TX" or p[1] != "pursuit" or "failed" in r:
            continue
        _, _, m, i, seed, level, team = p
        for cert, field in (("junction", "cert_junction_at"), ("lane_nv", "cert_lane_nv_at")):
            if r.get(field) is not None:
                out.append(
                    (f"CA|{cert}|{m}|{i}|{seed}|{level}|{team}", m, int(i), int(seed), level)
                    + (int(team), cert, r[field])
                )
    return out


# -- analysis (written before launch) ------------------------------------------------------------
def _table(store, block, field="d06"):
    """Seed-averaged value per (method, level, team, map, index)."""
    by = {}
    for k, r in store.rows.items():
        p = k.split("|")
        if p[0] != block or "failed" in r or field not in r:
            continue
        _, method, m, i, _seed, level, team = p
        by.setdefault((method, level, int(team), m, int(i)), []).append(float(r[field]))
    return {k: sum(v) / len(v) for k, v in by.items()}


def _per(tab, method, level, team):
    return {k[3:]: v for k, v in tab.items() if k[:3] == (method, level, team)}


def _paired(a, b, ks, alpha=0.05):
    return bootstrap([a[k] - b[k] for k in ks], alpha=alpha)


def _city_cluster(diffs_by_city, reps=10000, seed=11, alpha=0.05):
    import random

    rng = random.Random(seed)
    cities = sorted(diffs_by_city)
    means = []
    for _ in range(reps):
        xs = []
        for c in (rng.choice(cities) for _ in cities):
            d = diffs_by_city[c]
            xs += [rng.choice(d) for _ in d]
        means.append(sum(xs) / len(xs))
    means.sort()
    lo, hi = int(alpha / 2 * reps), int((1 - alpha / 2) * reps) - 1
    return [round(means[lo], 3), round(means[hi], 3)]


def summarise(package, store):
    out = {"failed": {}, "collisions": 0, "TX": {}, "OX": {}, "H1": {}, "H2": {}, "S": {}}
    for k, r in store.rows.items():
        b = k.split("|")[0]
        out["failed"][b] = out["failed"].get(b, 0) + ("failed" in r)
        out["collisions"] += bool(r.get("collided"))
    tx, ts = _table(store, "TX"), _table(store, "TS")
    ox, os_ = _table(store, "OX"), _table(store, "OS")

    def singles(tab, level, team):
        return [
            {k[3:]: v for k, v in tab.items() if k[:3] == (f"plus_opt_only_p{j}", level, 7)}
            for j in range(1, team + 1)
        ]

    def cells(block, tab, stab, levels, methods):
        res = {}
        for level in levels:
            for team in TEAMS:
                r = {mt: _per(tab, mt, level, team) for mt in methods}
                ks = sorted(set.intersection(*(set(r[mt]) for mt in methods)))
                if not ks:
                    continue
                c = {"n": len(ks), **{mt: bootstrap([r[mt][k] for k in ks]) for mt in methods}}
                c["opt_minus_pursuit"] = _paired(r["plus_opt"], r["pursuit"], ks)
                c["opt_minus_a95"] = _paired(r["plus_opt"], r["ambush_a95"], ks)
                for mt in methods:
                    if mt.startswith("mappo"):
                        c[f"{mt}_minus_opt"] = _paired(r[mt], r["plus_opt"], ks)
                if "mappo_kan" in methods:
                    c["kan_minus_mlp"] = _paired(r["mappo_kan"], r["mappo_mlp"], ks)
                sg = singles(stab, level, team)
                ks2 = [k for k in ks if all(k in s for s in sg)]
                if ks2:
                    union = [1 - math.prod(1 - s[k] for s in sg) for k in ks2]
                    syn = [r["plus_opt"][k] - u for k, u in zip(ks2, union, strict=True)]
                    c["single_mean"] = bootstrap([sum(s[k] for s in sg) / team for k in ks2])
                    c["synergy"] = bootstrap(syn)
                    c["synergy_bonferroni"] = bootstrap(syn, alpha=0.05 / (len(levels) * 3))
                res[f"{level}_team{team}"] = c
        return res

    out["TX"] = cells("TX", tx, ts, LEVELS, METHODS)
    out["OX"] = cells("OX", ox, os_, ["OPTIMAL_ESCAPE"], OX_METHODS)

    # H1: c2_15 - pursuit on TEST, pooled over AVOIDANT/RANDOM x teams (A-99 estimand), 97.5 %.
    pooled, by_city = [], {}
    for level in ("AVOIDANT", "RANDOM"):
        for team in TEAMS:
            o, p = _per(tx, "plus_opt", level, team), _per(tx, "pursuit", level, team)
            for k in sorted(set(o) & set(p)):
                pooled.append(o[k] - p[k])
                by_city.setdefault(k[0], []).append(o[k] - p[k])
    out["H1"] = {
        "opt_minus_pursuit_pooled_97.5": bootstrap(pooled, alpha=0.025),
        "n": len(pooled),
        "per_city": {c: bootstrap(v) for c, v in sorted(by_city.items())},
        "city_cluster_95": _city_cluster(by_city) if by_city else None,
    }
    out["H1"]["passes"] = bool(pooled) and out["H1"]["opt_minus_pursuit_pooled_97.5"][1] > 0

    # H2: pursuit, body-gap <= 5 m success - D06, pooled over the three evaders and teams, 97.5 %.
    p5, pd = _table(store, "TX", "prox_5m"), tx
    pc = _table(store, "TX", "prox_5m_centre")
    d2, dc, rates = [], [], {"prox_5m": [], "prox_5m_centre": [], "d06": []}
    for k, v in p5.items():
        if k[0] == "pursuit" and k in pd:
            d2.append(v - pd[k])
            dc.append(pc[k] - pd[k])
            rates["prox_5m"].append(v)
            rates["prox_5m_centre"].append(pc[k])
            rates["d06"].append(pd[k])
    out["H2"] = {
        "prox5_minus_d06_pursuit_97.5": bootstrap(d2, alpha=0.025),
        "centre5_minus_d06_pursuit": bootstrap(dc),
        "rates": {f: bootstrap(v) for f, v in rates.items()},
        "n": len(d2),
    }
    out["H2"]["passes"] = bool(d2) and out["H2"]["prox5_minus_d06_pursuit_97.5"][1] > 0
    out["H2"]["by_method_prox5_minus_d06"] = {
        mt: bootstrap([v - pd[k] for k, v in p5.items() if k[0] == mt and k in pd])
        for mt in METHODS
    }

    # S1 c2_15 - A-95 pooled on TEST; S4 MAPPO - c2_15 and KAN - MLP pooled (AVOIDANT/RANDOM).
    def pooled_diff(a, b, levels=("AVOIDANT", "RANDOM")):
        xs = []
        for level in levels:
            for team in TEAMS:
                x, y = _per(tx, a, level, team), _per(tx, b, level, team)
                xs += [x[k] - y[k] for k in sorted(set(x) & set(y))]
        return bootstrap(xs)

    out["S"]["S1_opt_minus_a95_pooled"] = pooled_diff("plus_opt", "ambush_a95")
    out["S"]["S4_mappo_kan_minus_opt"] = pooled_diff("mappo_kan", "plus_opt")
    out["S"]["S4_mappo_mlp_minus_opt"] = pooled_diff("mappo_mlp", "plus_opt")
    out["S"]["S4_kan_minus_mlp"] = pooled_diff("mappo_kan", "mappo_mlp")
    out["S"]["S2_optimal_TEST_opt_minus_pursuit_pooled"] = pooled_diff(
        "plus_opt", "pursuit", ("OPTIMAL_ESCAPE",)
    )
    oxp = []
    for team in TEAMS:
        x, y = (
            _per(ox, "plus_opt", "OPTIMAL_ESCAPE", team),
            _per(ox, "pursuit", "OPTIMAL_ESCAPE", team),
        )
        oxp += [x[k] - y[k] for k in sorted(set(x) & set(y))]
    out["S"]["S2_optimal_OX_opt_minus_pursuit_pooled"] = bootstrap(oxp)
    out["S"]["S3_cooperation_cells"] = [
        f"{b}:{c}"
        for b in ("TX", "OX")
        for c, v in out[b].items()
        if v.get("synergy_bonferroni") and v["synergy_bonferroni"][1] > 0
    ]

    # S5 certificate audit on TEST.
    ca = [r for k, r in store.rows.items() if k.startswith("CA|") and "failed" not in r]
    ok = [r for r in ca if r.get("reproduced")]
    trapped = {}
    for k, r in store.rows.items():
        p = k.split("|")
        if p[0] == "TX" and p[1] == "pursuit" and "failed" not in r:
            trapped[tuple(p[2:])] = r
    s5 = {"audited": len(ca), "reproduced": len(ok)}
    for cert, field in (("junction", "cert_junction_at"), ("lane_nv", "cert_lane_nv_at")):
        rs = [r for r in ok if r["key"].split("|")[1] == cert]
        fired = [r for r in trapped.values() if r.get(field) is not None]
        s5[cert] = {
            "n": len(rs),
            "escape": bootstrap([float(r["escaped"]) for r in rs]),
            "left_network": bootstrap([float(r["left_network"]) for r in rs]),
            "precision_trapped": bootstrap([float(r["trapped"]) for r in fired]),
            "precision_d06": bootstrap([float(r["d06"]) for r in fired]),
            "fired": len(fired),
        }
    lane = s5["lane_nv"]
    s5["lane_confirmed"] = bool(
        lane["n"] >= 30
        and lane["escape"][2] <= 0.10
        and lane["left_network"][2] <= 0.10
        and lane["precision_trapped"][1] >= 0.90
    )
    s5["junction_failure_replicates"] = bool(
        s5["junction"]["n"] >= 30 and s5["junction"]["escape"][1] > 0.10
    )
    out["S"]["S5_certificates"] = s5
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0, help="smoke test: first N main tasks only")
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    deadline = time.time() + 60 * args.budget_min
    store = Store(package)
    log = open(os.path.join(package, "log.jsonl"), "a", encoding="utf-8")  # noqa: SIM115

    def note(e):
        e["wall"] = round(time.time(), 1)
        log.write(json.dumps(e) + "\n")
        log.flush()
        print(json.dumps(e), flush=True)

    tasks = main_tasks()
    if args.limit:
        tasks = tasks[: args.limit]
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        if not store.run(pool, tasks, deadline, episode):
            note(
                {
                    "stage": "chunk_done",
                    "phase": "main",
                    "done": sum(t[0] in store.rows for t in tasks),
                    "of": len(tasks),
                }
            )
            return 0
        if args.limit:
            note({"stage": "smoke_done"})
            return 0
        audits = audit_tasks(store)
        if not store.run(pool, audits, deadline, cert_audit):
            note(
                {
                    "stage": "chunk_done",
                    "phase": "audit",
                    "done": sum(t[0] in store.rows for t in audits),
                    "of": len(audits),
                }
            )
            return 0
    out = summarise(package, store)
    note({"stage": "done", "H1": out["H1"].get("passes"), "H2": out["H2"].get("passes")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
