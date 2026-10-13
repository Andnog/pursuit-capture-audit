"""Final consolidated study (A-90): equal speeds; is there real coordination; calibration against
lenient literature endpoints; confirmation of the lane-level certificate and trap decomposition.

Phase `run`: on 7 cities, every scenario is played by four team policies (pursuit, cut, individual,
random) and by pursuit with each single pursuer alone (same start positions; the other two are not
inserted). Per episode: trapping endpoint (A-84), trap type (A-89 decomposition), minimum
evader-pursuer centre distance over the 0.1 s trace (lenient proximity endpoint), and both
certificates. Phase `audit`: hold-condition re-simulation of every team episode in which the
junction-level or the non-vacuous lane-level certificate fired. Phase `analyse`: pre-registered
tests (package PROTOCOL_EN.md).
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import multiprocessing as mp
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from audit_cage_certificate import PURSUERS, replay  # noqa: E402
from run_endpoint_validation import (  # noqa: E402
    DEVELOPMENT,
    TRAINING,
    _read_jsonl,
    bootstrap,
    certified_at,
    immobilised_at,
)
from train_caging_pilot import _init_worker, _net, _paths  # noqa: E402

SPEED = 1.0
TEAM_POLICIES = ["pursuit", "cut", "individual", "random"]
SINGLES = ["p1", "p2", "p3"]
PROX_M = (5.0, 10.0)
AUDIT_WINDOW_S = 60.0
_SNET: dict = {}


def _snet(map_id):
    import sumolib

    if map_id not in _SNET:
        _SNET[map_id] = sumolib.net.readNet(_paths()[map_id])
    return _SNET[map_id]


def trap_type(recs, t0, map_id):
    win = [r for r in recs if t0 - 1e-6 <= r["t"] <= t0 + 10.0 + 1e-6]
    if any(
        r["follower"] and r["follower"][0] in PURSUERS and r["follower"][1] <= 30.0 for r in win
    ):
        return "SANDWICH"
    edge = win[0]["edge"] if win else ":"
    if not edge.startswith(":"):
        net = _snet(map_id)
        e = net.getEdge(edge)
        outs = e.getToNode().getOutgoing()
        if all(o.getToNode().getID() == e.getFromNode().getID() for o in outs):
            return "DEAD_END"
    return "FRONT_ONLY"


def run_task(args):
    policy, single, map_id, index, salt = args
    name = policy if single is None else f"{policy}_only_{single}"
    key = {"policy": name, "map_id": map_id, "index": index}
    try:
        ep, recs = replay(
            map_id,
            index,
            9500 + index,
            salt,
            "T",
            None,
            "policy",
            300.0,
            kind=policy,
            speed=SPEED,
            active=None if single is None else [single],
        )
    except Exception as error:  # noqa: BLE001
        return key | {"failed": f"{type(error).__name__}: {str(error)[:160]}"}, None
    compact = [
        {
            "t": r["t"],
            "v": r["v_e"],
            "leader": r["leader"],
            "follower": r["follower"],
            "signal": r["signal"],
            "edge": r["edge"],
            "cj": r["caged_now"],
            "cl": r["caged_lane_now"],
            "ng": len(r["gates"]),
        }
        for r in recs
    ]
    for c in compact:
        c["cln"] = c["cl"] and c["ng"] >= 1
    t_imm = immobilised_at(compact, 10.0, 15.0, 30.0)
    min_d, first = math.inf, {}
    for f in ep.trace:
        e = f.vehicles.get("e1")
        if e is None:
            continue
        for v, p in f.vehicles.items():
            if v == "e1":
                continue
            d = math.dist((e.x, e.y), (p.x, p.y))
            min_d = min(min_d, d)
            for th in PROX_M:
                if d <= th and th not in first:
                    first[th] = f.time_s
    trapped = t_imm is not None or ep.contact_capture
    row = key | {
        "trapped": trapped,
        "immobilised_at": t_imm,
        "contact_capture": ep.contact_capture,
        "trap_type": (
            None
            if not trapped
            else (trap_type(compact, t_imm, map_id) if t_imm is not None else "CONTACT_ONLY")
        ),
        "min_distance_m": None if min_d == math.inf else round(min_d, 2),
        **{f"prox_{int(th)}m": th in first for th in PROX_M},
        **{f"prox_{int(th)}m_at": first.get(th) for th in PROX_M},
        "cert_junction_at": certified_at(compact, "cj"),
        "cert_lane_nv_at": certified_at(compact, "cln"),
        "evader_exited": ep.evader_exited,
        "collided": ep.collided,
        "emergencies": ep.emergencies,
        "end_s": ep.end_s,
    }
    return row, compact


def audit_task(args):
    policy, map_id, index, salt, cert, expected = args
    key = {"policy": policy, "map_id": map_id, "index": index, "cert": cert}
    try:
        ep, recs = replay(
            map_id,
            index,
            9500 + index,
            salt,
            "T",
            None,
            "hold",
            300.0,
            kind=policy,
            hold_on=cert,
            speed=SPEED,
        )
    except Exception as error:  # noqa: BLE001
        return key | {"failed": f"{type(error).__name__}: {str(error)[:160]}"}
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
        return key | {"reproduced": False}
    at = next(r for r in recs if abs(r["t"] - t_cert) < 1e-6)
    gates = set(at["gates"])
    net = _net(map_id)
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
    return key | {
        "reproduced": abs(t_cert - expected) < 1e-6,
        "t_cert": t_cert,
        "window_s": round(window[-1]["t"] - t_cert, 1) if window else 0.0,
        "escaped": escape is not None,
        "left_network": ep.evader_exited and escape is None,
        "contact_capture": ep.contact_capture,
        "n_gates": len(gates),
    }


def analyse(package):
    rows = [r for r in _read_jsonl(os.path.join(package, "run.jsonl")) if "failed" not in r]
    by = {}
    for r in rows:
        by.setdefault(r["policy"], {})[(r["map_id"], r["index"])] = r
    names = TEAM_POLICIES + [f"pursuit_only_{s}" for s in SINGLES]
    common = set.intersection(*(set(by.get(n, {})) for n in names))
    ks = sorted(common)
    out = {
        "scenarios_common": len(ks),
        "failed_episodes": len(_read_jsonl(os.path.join(package, "run.jsonl"))) - len(rows),
        "rates": {},
        "tests": {},
        "descriptive": {},
    }

    def rate(name, field="trapped", keys=ks):
        return bootstrap([float(by[name][k][field]) for k in keys])

    for n in names:
        out["rates"][n] = {
            "trapped": rate(n),
            "prox_5m": rate(n, "prox_5m"),
            "prox_10m": rate(n, "prox_10m"),
            "contact_capture": rate(n, "contact_capture"),
            "evader_exited": rate(n, "evader_exited"),
            "collisions": sum(by[n][k]["collided"] for k in ks),
        }
        for split, maps in (("training", TRAINING), ("development", DEVELOPMENT)):
            out["rates"][n][f"trapped_{split}"] = rate(n, keys=[k for k in ks if k[0] in maps])
    # C1: does the team beat its best single pursuer? (per scenario, max over the three singles)
    team = [float(by["pursuit"][k]["trapped"]) for k in ks]
    best = [max(float(by[f"pursuit_only_{s}"][k]["trapped"]) for s in SINGLES) for k in ks]
    mean = [sum(float(by[f"pursuit_only_{s}"][k]["trapped"]) for s in SINGLES) / 3 for k in ks]
    c1 = bootstrap([a - b for a, b in zip(team, best, strict=True)])
    out["tests"]["C1_team_minus_best_single"] = c1
    out["tests"]["C1_passes"] = c1[1] > 0
    out["descriptive"]["team_minus_mean_single"] = bootstrap(
        [a - b for a, b in zip(team, mean, strict=True)]
    )
    out["descriptive"]["best_single_rate"] = bootstrap(best)
    c2 = bootstrap(
        [float(by["pursuit"][k]["trapped"]) - float(by["cut"][k]["trapped"]) for k in ks]
    )
    out["tests"]["C2_pursuit_minus_cut"] = c2
    out["tests"]["C2_direction"] = (
        "pursuit > cut" if c2[1] > 0 else ("cut > pursuit" if c2[2] < 0 else "no difference")
    )
    # A1: inflation by the lenient proximity endpoint (pursuit team).
    a1 = bootstrap(
        [float(by["pursuit"][k]["prox_5m"]) - float(by["pursuit"][k]["trapped"]) for k in ks]
    )
    out["tests"]["A1_prox5_minus_trapped_pursuit"] = a1
    out["tests"]["A1_passes"] = a1[1] > 0
    out["descriptive"]["prox5_minus_trapped_by_policy"] = {
        n: bootstrap([float(by[n][k]["prox_5m"]) - float(by[n][k]["trapped"]) for k in ks])
        for n in names
    }
    # B3: trap decomposition (team policies).
    types = {}
    for n in names:
        t = [by[n][k]["trap_type"] for k in ks if by[n][k]["trapped"]]
        types[n] = {x: t.count(x) for x in ("SANDWICH", "DEAD_END", "FRONT_ONLY", "CONTACT_ONLY")}
    out["descriptive"]["trap_types"] = types
    # Certificates: precision / recall over team episodes.
    team_rows = [by[n][k] for n in TEAM_POLICIES for k in ks]
    for cert, key in (("junction", "cert_junction_at"), ("lane_nv", "cert_lane_nv_at")):
        fired = [r for r in team_rows if r[key] is not None]
        tr = [r for r in team_rows if r["trapped"]]
        out["descriptive"][f"{cert}_precision"] = bootstrap([float(r["trapped"]) for r in fired])
        out["descriptive"][f"{cert}_recall"] = bootstrap([float(r[key] is not None) for r in tr])
        out["descriptive"][f"{cert}_fired"] = len(fired)
    audit_path = os.path.join(package, "audit.jsonl")
    if os.path.exists(audit_path):
        raw = _read_jsonl(audit_path)
        ok = [a for a in raw if "failed" not in a and a.get("reproduced")]
        out["descriptive"]["audit_not_reproduced_or_failed"] = len(raw) - len(ok)
        for cert in ("junction", "lane_nv"):
            rs = [a for a in ok if a["cert"] == cert]
            out["descriptive"][f"audit_{cert}"] = {
                "n": len(rs),
                "escape": bootstrap([float(a["escaped"]) for a in rs]),
                "left_network": bootstrap([float(a["left_network"]) for a in rs]),
            }
        lane = out["descriptive"]["audit_lane_nv"]
        prec = out["descriptive"]["lane_nv_precision"]
        out["tests"]["B1_lane_nv_certificate"] = (
            "INSUFFICIENT_EVENTS"
            if lane["n"] < 30
            else (
                "CONFIRMED"
                if lane["escape"][2] <= 0.10 and lane["left_network"][2] <= 0.10 and prec[1] >= 0.90
                else "NOT_CONFIRMED"
            )
        )
        j = out["descriptive"]["audit_junction"]
        out["tests"]["B2_junction_failure_replicates"] = j["escape"][1] > 0.10
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--phase", choices=["run", "audit", "analyse"], required=True)
    parser.add_argument("--salt", default="PE7")
    parser.add_argument("--scenarios", type=int, default=60, help="per map")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    maps = TRAINING + DEVELOPMENT
    if args.phase == "run":
        tasks = [
            (p, None, m, i, args.salt)
            for m in maps
            for i in range(args.scenarios)
            for p in TEAM_POLICIES
        ] + [
            ("pursuit", s, m, i, args.salt)
            for m in maps
            for i in range(args.scenarios)
            for s in SINGLES
        ]
        print(json.dumps({"phase": "run", "episodes": len(tasks)}), flush=True)
        with mp.get_context("spawn").Pool(args.workers, initializer=_init_worker) as pool:
            results = pool.map(run_task, tasks, chunksize=1)
        with (
            open(os.path.join(package, "run.jsonl"), "w", encoding="utf-8") as h,
            gzip.open(os.path.join(package, "records.jsonl.gz"), "wt", encoding="utf-8") as g,
        ):
            for row, compact in results:
                h.write(json.dumps(row) + "\n")
                if compact is not None:
                    key = {k: row[k] for k in ("policy", "map_id", "index")}
                    g.write(json.dumps(key | {"records": compact}) + "\n")
    elif args.phase == "audit":
        rows = _read_jsonl(os.path.join(package, "run.jsonl"))
        tasks = []
        for r in rows:
            if "failed" in r or r["policy"] not in TEAM_POLICIES:
                continue
            for cert, key in (("junction", "cert_junction_at"), ("lane_nv", "cert_lane_nv_at")):
                if r[key] is not None:
                    tasks.append((r["policy"], r["map_id"], r["index"], args.salt, cert, r[key]))
        print(json.dumps({"phase": "audit", "episodes": len(tasks)}), flush=True)
        with mp.get_context("spawn").Pool(args.workers, initializer=_init_worker) as pool:
            results = pool.map(audit_task, tasks, chunksize=1)
        with open(os.path.join(package, "audit.jsonl"), "w", encoding="utf-8") as h:
            for row in results:
                h.write(json.dumps(row) + "\n")
    out = analyse(package)
    print(json.dumps({"phase": args.phase, "tests": out["tests"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
