"""First training batch of every MAPPO-v3 run, reconstructed with a ledger (A-139, F5-1/F5-6).

The weights of each training iteration of MAPPO-v3 were not stored, so its training episodes cannot
be replayed, with one exception: the first batch of a run was sampled with the stored imitation
start (the critic warm-up of arm W changes the critic only), from scenarios, SUMO seeds and
sampling seeds that the script defines. This script replays those 8 x 64 episodes and passes each
one through the corrected measurement (`train_mappo_v4.measure`), which also records what the
earlier contract did with it. Nothing is trained.

Reproduction is checked against the sealed log: the success, OC and proximity rates of iteration 1
of every run, as logged by `train_mappo_v3.py`, must be matched exactly.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import pickle
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import train_mappo_v2 as v2  # noqa: E402
import train_mappo_v3 as v3  # noqa: E402
import train_mappo_v4 as v4  # noqa: E402
from run_ambush_optimization import Store  # noqa: E402

V3 = os.path.join(ROOT, "experiments", "20261005_mappo_v3_r01")
BATCH = 64


def tasks():
    with open(os.path.join(V3, "state.pkl"), "rb") as h:
        starts = pickle.load(h)["starts"]
    out = []
    for name in v3.ORDER:
        _, head, seed = v3.parse(name)
        # keep=False: the tensors are not needed, only the ledger fields
        for t in v3.train_tasks(name, starts[f"{head}_s{seed}"], 0, BATCH):
            out.append(t[:12] + (False, t[13]))
    return out


def sealed_rates():
    out = {}
    with open(os.path.join(V3, "train_log.jsonl"), encoding="utf-8") as h:
        for x in h:
            r = json.loads(x)
            if r.get("stage") == "mappo" and r["iteration"] == 1:
                out[r["run"]] = {k: r[k] for k in ("success", "oc", "prox")}
    return out


def summarise(rows):
    sealed = sealed_rates()
    out = {"runs": {}, "reproduced_runs": 0}
    total = []
    for name in v3.ORDER:
        mine = [r for k, r in rows.items() if k.startswith(name + "|")]
        counts = v4.batch_counts(mine)
        got = {
            "success": round(v4.frac(v4.rate(mine)), 3),
            "oc": round(v4.frac(v4.rate(mine, "d06")), 3),
            "prox": round(v4.frac(v4.rate(mine, "prox_5m")), 3),
        }
        same = got == sealed[name]
        out["reproduced_runs"] += same
        valid = [r for r in mine if "failed" not in r]
        total += valid
        out["runs"][name] = {
            "sealed_log_iteration_1": sealed[name],
            "reconstructed": got,
            "matches_the_sealed_log": same,
            "attempted": counts["attempted"],
            "failed": counts["failed"],
            "valid": counts["valid"],
            "end_reasons": counts["end_reasons"],
            "decisions_trained_by_the_earlier_contract": sum(r["legacy"]["ticks"] for r in valid),
            "of_which_without_a_future": counts["legacy_trained_decisions_without_future"],
            "episodes_with_such_a_decision": counts["legacy_episodes_with_such_a_decision"],
            "captures_on_a_decision_tick": counts["legacy_capture_on_a_tick"],
            "episodes_with_a_collision": counts["collided"],
            "collision_inside_the_trained_interval": counts["collision_in_interval"],
            "penalised_for_a_collision_outside": counts["legacy_penalised_collision_outside"],
            "capture_instant_differs_from_corrected": counts["legacy_capture_instant_differs"],
            "inner_gap_frames": counts["inner_gap_frames"],
        }
    keys = [
        k for k, v in out["runs"][v3.ORDER[0]].items() if isinstance(v, int) and k != "attempted"
    ]
    out["all_runs"] = {
        "attempted": len(rows),
        **{k: sum(out["runs"][n][k] for n in v3.ORDER) for k in keys},
        "episodes_ending_at_the_horizon": sum(r["end_reason"] == "horizon" for r in total),
        "episodes_ending_by_evader_exit": sum(r["end_reason"] == "evader_exit" for r in total),
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    todo = tasks()
    store = Store(package)
    with mp.get_context("spawn").Pool(args.workers, initializer=v2._init) as pool:
        complete = store.run(pool, todo, time.time() + 60 * args.budget_min, v4.episode)
    print(json.dumps({"done": len(store.rows), "of": len(todo), "complete": complete}), flush=True)
    if complete:
        out = summarise(store.rows)
        with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
            json.dump(out, h, indent=2)
        print(json.dumps(out["all_runs"]), flush=True)
        print(json.dumps({"reproduced_runs": out["reproduced_runs"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
