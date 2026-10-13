"""Endpoint validation study (A-88): stronger baselines, a lane-level certificate, threshold
sensitivity, and replication on the DEVELOPMENT cities. Pre-registered in the package protocol.

Phase `endpoint`: every non-learning policy plays full 300 s episodes on every map; per 1 s step
the evader's speed, leader, next signal and both certificates (junction-level A-72, lane-level
A-88) are recorded (`records.jsonl.gz`).
Phase `audit`: every episode in which a certificate fired is re-simulated with the pursuers frozen
from that certificate's certification time (hold condition, A-83) and escape is measured.
Phase `analyse`: pre-registered tests and the threshold-sensitivity grid (`summary.json`).
"""

from __future__ import annotations

import argparse
import gzip
import json
import multiprocessing as mp
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from audit_cage_certificate import PURSUERS, replay  # noqa: E402
from train_caging_pilot import _init_worker, _net  # noqa: E402

TRAINING = ["adelaide_cbd", "toronto_downtown", "washington_downtown", "seattle_downtown"]
DEVELOPMENT = ["phoenix_downtown", "portland_downtown", "sapporo_grid"]
POLICIES = ["cut", "individual", "nearest", "pursuit", "random"]
BASELINES = ["individual", "nearest", "pursuit"]
PERSIST_S = 10.0
AUDIT_WINDOW_S = 60.0
PRIMARY = {"duration": 10.0, "gap": 15.0, "signal": 30.0}
GRID = [
    {"duration": d, "gap": g, "signal": s}
    for d in (5.0, 10.0, 20.0)
    for g in (10.0, 15.0, 25.0)
    for s in (0.0, 30.0, 60.0)
]


def immobilised_at(records, duration, gap, signal):
    """First start of a run of >= duration s with the evader <= 0.5 m/s behind a pursuer leader
    within `gap` m and (if signal > 0) no red/yellow light within `signal` m."""
    start = None
    for r in records:
        ok = (
            r["v"] <= 0.5
            and r["leader"] is not None
            and r["leader"][0] in PURSUERS
            and r["leader"][1] <= gap
            and not (
                signal > 0
                and r["signal"] is not None
                and r["signal"][1] <= signal
                and r["signal"][2] in "rRyYu"
            )
        )
        if ok:
            start = r["t"] if start is None else start
            if r["t"] - start >= duration - 1e-6:
                return start
        else:
            start = None
    return None


def certified_at(records, key):
    since = None
    for r in records:
        if r[key]:
            since = r["t"] if since is None else since
            if r["t"] - since >= PERSIST_S - 1e-6:
                return r["t"]
        else:
            since = None
    return None


def endpoint_task(args):
    policy, map_id, index, salt = args
    key = {"policy": policy, "map_id": map_id, "index": index}
    try:
        ep, recs = replay(
            map_id, index, 9500 + index, salt, "T", None, "policy", 300.0, kind=policy
        )
    except Exception as error:  # noqa: BLE001
        return key | {"failed": f"{type(error).__name__}: {str(error)[:160]}"}, None
    compact = [
        {
            "t": r["t"],
            "v": r["v_e"],
            "leader": r["leader"],
            "signal": r["signal"],
            "cj": r["caged_now"],
            "cl": r["caged_lane_now"],
        }
        for r in recs
    ]
    t_imm = immobilised_at(compact, **PRIMARY)
    row = key | {
        "trapped": t_imm is not None or ep.contact_capture,
        "immobilised_at": t_imm,
        "contact_capture": ep.contact_capture,
        "cert_junction_at": certified_at(compact, "cj"),
        "cert_lane_at": certified_at(compact, "cl"),
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
            map_id, index, 9500 + index, salt, "T", None, "hold", 300.0, kind=policy, hold_on=cert
        )
    except Exception as error:  # noqa: BLE001
        return key | {"failed": f"{type(error).__name__}: {str(error)[:160]}"}
    flag = "caged_lane_now" if cert == "lane" else "caged_now"
    t_cert = certified_at([{"t": r["t"], "c": r[flag]} for r in recs], "c")
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
    blocked = immobilised_at(
        [{"t": r["t"], "v": r["v_e"], "leader": r["leader"], "signal": None} for r in window],
        2.0,
        15.0,
        0.0,
    )
    return key | {
        "reproduced": abs(t_cert - expected) < 1e-6,
        "t_cert": t_cert,
        "window_s": round(window[-1]["t"] - t_cert, 1) if window else 0.0,
        "escaped": escape is not None,
        "escape_after_s": escape,
        "left_network": ep.evader_exited and escape is None,
        "blocked": blocked is not None,
        "contact_capture": ep.contact_capture,
        "n_gates": len(gates),
        "v_e_at_cert": at["v_e"],
    }


def _read_jsonl(path):
    with open(path, encoding="utf-8") as h:
        return [json.loads(x) for x in h]


def bootstrap(xs, reps=10000, seed=7):
    if not xs:
        return None
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(reps))
    return [round(sum(xs) / len(xs), 3), round(means[250], 3), round(means[9749], 3)]


def analyse(package):
    rows = _read_jsonl(os.path.join(package, "endpoint.jsonl"))
    good = [r for r in rows if "failed" not in r]
    by = {}
    for r in good:
        by.setdefault(r["policy"], {})[(r["map_id"], r["index"])] = r
    # Paired analyses use scenarios every policy completed.
    common = set.intersection(*(set(by[p]) for p in POLICIES if p in by))
    recs = {}
    with gzip.open(os.path.join(package, "records.jsonl.gz"), "rt", encoding="utf-8") as h:
        for line in h:
            d = json.loads(line)
            recs[(d["policy"], d["map_id"], d["index"])] = d["records"]

    def trapped(policy, k, th=None):
        if th is None:
            return float(by[policy][k]["trapped"])
        imm = immobilised_at(recs[(policy, *k)], **th)
        return float(imm is not None or by[policy][k]["contact_capture"])

    def delta(a, b, maps, th=None):
        ks = sorted(k for k in common if k[0] in maps)
        return bootstrap([trapped(a, k, th) - trapped(b, k, th) for k in ks])

    all_maps = TRAINING + DEVELOPMENT
    out = {
        "failed_episodes": len(rows) - len(good),
        "scenarios_common": {
            "all": len(common),
            "development": sum(k[0] in DEVELOPMENT for k in common),
        },
        "rates": {},
        "primary": {},
        "secondary": {},
        "sensitivity": [],
    }
    for p in POLICIES:
        for split, maps in (("training", TRAINING), ("development", DEVELOPMENT)):
            ks = [k for k in common if k[0] in maps]
            out["rates"][f"{p}_{split}"] = bootstrap([trapped(p, k) for k in ks])
    p1 = {b: delta("cut", b, all_maps) for b in BASELINES}
    out["primary"]["P1_cut_minus_baselines_all_maps"] = p1
    out["primary"]["P1_passes"] = all(v is not None and v[1] > 0 for v in p1.values())
    p2 = delta("cut", "individual", DEVELOPMENT)
    out["primary"]["P2_cut_minus_individual_development"] = p2
    out["primary"]["P2_passes"] = p2 is not None and p2[1] > 0
    out["secondary"]["random_minus_cut_all"] = delta("random", "cut", all_maps)
    out["secondary"]["per_map_cut_minus_individual"] = {
        m: delta("cut", "individual", [m]) for m in all_maps
    }
    for cert, key in (("junction", "cert_junction_at"), ("lane", "cert_lane_at")):
        fired = [by[p][k] for p in POLICIES for k in common if by[p][k][key] is not None]
        trapped_rows = [by[p][k] for p in POLICIES for k in common if by[p][k]["trapped"]]
        out["secondary"][f"{cert}_certificate"] = {
            "fired": len(fired),
            "precision_P_trapped_given_fired": bootstrap([float(r["trapped"]) for r in fired]),
            "recall_P_fired_given_trapped": bootstrap(
                [float(r[key] is not None) for r in trapped_rows]
            ),
        }
    for th in GRID:
        out["sensitivity"].append(
            th
            | {
                "cut_minus_individual": delta("cut", "individual", all_maps, th),
                "cut_minus_best_baseline": min(
                    (delta("cut", b, all_maps, th) for b in BASELINES), key=lambda d: d[0]
                ),
                "cut_rate": bootstrap([trapped("cut", k, th) for k in common]),
            }
        )
    out["sensitivity_sign_stable"] = all(
        s["cut_minus_individual"][0] > 0 for s in out["sensitivity"]
    )
    audit_path = os.path.join(package, "audit.jsonl")
    if os.path.exists(audit_path):
        raw = _read_jsonl(audit_path)
        aud = [a for a in raw if "failed" not in a and a.get("reproduced")]
        for cert in ("junction", "lane"):
            for split, maps in (("all", all_maps), ("development", DEVELOPMENT)):
                rs = [a for a in aud if a["cert"] == cert and a["map_id"] in maps]
                out["secondary"][f"audit_{cert}_{split}"] = {
                    "n": len(rs),
                    "escape": bootstrap([float(a["escaped"]) for a in rs]),
                    "left_network": bootstrap([float(a["left_network"]) for a in rs]),
                    "blocked": bootstrap([float(a["blocked"]) for a in rs]),
                    "contact": bootstrap([float(a["contact_capture"]) for a in rs]),
                }
        j = out["secondary"]["audit_junction_development"]
        out["primary"]["P3a_junction_failure_replicates_on_development"] = (
            j["escape"] is not None and j["escape"][1] > 0.10
        )
        lane = out["secondary"]["audit_lane_all"]
        out["primary"]["P3b_lane_certificate"] = (
            "INSUFFICIENT_EVENTS"
            if lane["n"] < 30
            else ("ADEQUATE" if lane["escape"][2] <= 0.10 else "NOT_ADEQUATE")
        )
        out["primary"]["audit_not_reproduced_or_failed"] = sum(
            1 for a in raw if "failed" in a or not a.get("reproduced")
        )
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--phase", choices=["endpoint", "audit", "analyse"], required=True)
    parser.add_argument("--salt", default="PE6")
    parser.add_argument("--scenarios", type=int, default=60, help="per map")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    maps = TRAINING + DEVELOPMENT
    if args.phase == "endpoint":
        tasks = [
            (p, m, i, args.salt) for m in maps for i in range(args.scenarios) for p in POLICIES
        ]
        print(json.dumps({"phase": "endpoint", "episodes": len(tasks)}), flush=True)
        with mp.get_context("spawn").Pool(args.workers, initializer=_init_worker) as pool:
            results = pool.map(endpoint_task, tasks, chunksize=1)
        with (
            open(os.path.join(package, "endpoint.jsonl"), "w", encoding="utf-8") as h,
            gzip.open(os.path.join(package, "records.jsonl.gz"), "wt", encoding="utf-8") as g,
        ):
            for row, compact in results:
                h.write(json.dumps(row) + "\n")
                if compact is not None:
                    key = {k: row[k] for k in ("policy", "map_id", "index")}
                    g.write(json.dumps(key | {"records": compact}) + "\n")
        print(json.dumps({"phase": "endpoint", "done": len(results)}), flush=True)
    elif args.phase == "audit":
        rows = _read_jsonl(os.path.join(package, "endpoint.jsonl"))
        tasks = []
        for r in rows:
            if "failed" in r:
                continue
            for cert, key in (("junction", "cert_junction_at"), ("lane", "cert_lane_at")):
                if r[key] is not None:
                    tasks.append((r["policy"], r["map_id"], r["index"], args.salt, cert, r[key]))
        print(json.dumps({"phase": "audit", "episodes": len(tasks)}), flush=True)
        with mp.get_context("spawn").Pool(args.workers, initializer=_init_worker) as pool:
            results = pool.map(audit_task, tasks, chunksize=1)
        with open(os.path.join(package, "audit.jsonl"), "w", encoding="utf-8") as h:
            for row in results:
                h.write(json.dumps(row) + "\n")
        print(json.dumps({"phase": "audit", "done": len(results)}), flush=True)
    out = analyse(package)
    print(json.dumps({"phase": "analyse", "primary": out["primary"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
