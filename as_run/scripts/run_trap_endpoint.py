"""Direct trapping endpoint (A-84): does the evader end up physically trapped?

Every policy plays full 300 s episodes in SUMO (no early stop at the certificate). Per controller
step (1 s) the evader's speed, leader and next signal are recorded. Endpoints, defined in the
package PROTOCOL_EN.md:

- immobilised: evader ≤ 0.5 m/s for ≥ 10 s with a pursuer as immediate leader within 15 m and no
  red/yellow signal within 30 m ahead, throughout;
- contact capture: the D06 predicate (A-57 alignment) anywhere in the trace;
- trapped = immobilised or contact capture (primary).
The A-72 certificate is recorded alongside, to measure how well it predicts trapping.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from audit_cage_certificate import PURSUERS, replay  # noqa: E402
from train_caging_pilot import MAPS, _init_worker  # noqa: E402

STOP_MPS = 0.5
GAP_M = 15.0
SIGNAL_M = 30.0
IMMOBILE_S = 10.0
HORIZON_S = 300.0


def immobile(r) -> bool:
    if r["v_e"] > STOP_MPS or r["leader"] is None:
        return False
    if r["leader"][0] not in PURSUERS or r["leader"][1] > GAP_M:
        return False
    sig = r["signal"]
    return not (sig is not None and sig[1] <= SIGNAL_M and sig[2] in "rRyYu")


def first_immobilisation(records):
    start = None
    for r in records:
        if immobile(r):
            start = r["t"] if start is None else start
            if r["t"] - start >= IMMOBILE_S - 1e-6:
                return start
        else:
            start = None
    return None


def task(args):
    name, weights, arm, kind, map_id, index, seed, salt = args
    try:
        ep, records = replay(
            map_id, index, seed, salt, arm, weights, "policy", HORIZON_S, kind=kind
        )
        t_imm = first_immobilisation(records)
        row = {
            "immobilised": t_imm is not None,
            "immobilised_at": t_imm,
            "contact_capture": ep.contact_capture,
            "trapped": t_imm is not None or ep.contact_capture,
            "certified": ep.caged_at is not None,
            "certified_at": None if ep.caged_at is None else ep.caged_at + 10.0,
            "evader_exited": ep.evader_exited,
            "collided": ep.collided,
            "emergencies": ep.emergencies,
            "end_s": ep.end_s,
        }
    except Exception as error:  # noqa: BLE001
        row = {"failed": f"{type(error).__name__}: {str(error)[:160]}"}
    return {"policy": name, "map_id": map_id, "index": index, "seed": seed, **row}


def bootstrap(xs, reps=10000, seed=7):
    if not xs:
        return None
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(reps))
    return [round(sum(xs) / len(xs), 3), round(means[250], 3), round(means[9749], 3)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--pilot", default="experiments/20260930_marl_pilot_r03")
    parser.add_argument("--salt", default="PE4")
    parser.add_argument("--scenarios", type=int, default=60, help="per map")
    parser.add_argument(
        "--learned",
        nargs="+",
        default=["T_seed1_final", "T_seed2_final", "U_seed1_final", "U_seed2_final"],
    )
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    policies = [("cut", None, "T", "cut"), ("individual", None, "T", "individual")]
    policies.append(("random", None, "T", "random"))
    for c in args.learned:
        with open(os.path.join(ROOT, args.pilot, "checkpoints", f"{c}.pt"), "rb") as h:
            policies.append((c, h.read(), c[0], None))
    tasks = [
        (name, w, arm, kind, m, i, 9500 + i, args.salt)
        for name, w, arm, kind in policies
        for m in MAPS
        for i in range(args.scenarios)
    ]
    print(json.dumps({"stage": "start", "episodes": len(tasks)}), flush=True)
    with mp.get_context("spawn").Pool(args.workers, initializer=_init_worker) as pool:
        rows = pool.map(task, tasks, chunksize=1)
    with open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as h:
        for r in rows:
            h.write(json.dumps(r) + "\n")
    good = [r for r in rows if "failed" not in r]
    by = {}
    for r in good:
        by.setdefault(r["policy"], {})[(r["map_id"], r["index"])] = r

    def paired(a, b, key="trapped"):
        ks = [k for k in by.get(a, {}) if k in by.get(b, {})]
        return bootstrap([float(by[a][k][key]) - float(by[b][k][key]) for k in ks])

    summary = {"failed": len(rows) - len(good), "rates": {}, "contrasts": {}}
    for name in by:
        rs = list(by[name].values())
        cert = [r for r in rs if r["certified"]]
        nocert = [r for r in rs if not r["certified"]]
        summary["rates"][name] = {
            "n": len(rs),
            "trapped": bootstrap([float(r["trapped"]) for r in rs]),
            "immobilised": round(sum(r["immobilised"] for r in rs) / len(rs), 3),
            "contact_capture": round(sum(r["contact_capture"] for r in rs) / len(rs), 3),
            "certified": round(len(cert) / len(rs), 3),
            "trapped_given_certified": round(
                sum(r["trapped"] for r in cert) / max(1, len(cert)), 3
            ),
            "trapped_given_not_certified": round(
                sum(r["trapped"] for r in nocert) / max(1, len(nocert)), 3
            ),
            "evader_exited": round(sum(r["evader_exited"] for r in rs) / len(rs), 3),
            "collisions": sum(r["collided"] for r in rs),
        }
    d = paired("cut", "individual")
    summary["contrasts"]["PRIMARY_cut_minus_individual"] = d
    summary["primary_passes"] = d is not None and d[1] > 0
    for name in by:
        if name not in ("cut", "individual"):
            summary["contrasts"][f"{name}_minus_cut"] = paired(name, "cut")
            summary["contrasts"][f"{name}_minus_individual"] = paired(name, "individual")
    summary["contrasts"]["cut_minus_individual_contact_capture"] = paired(
        "cut", "individual", "contact_capture"
    )
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(summary, h, indent=2)
    print(json.dumps({"stage": "summary", **summary}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
