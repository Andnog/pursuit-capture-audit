"""MARL pilot r04 (A-86): learn to TRAP the evader, with a patience circuit breaker.

Same environment, network, BC and PPO as r03 (`train_caging_pilot.py`), but the terminal reward is
the A-84 trapping event (evader immobilised behind a pursuer, not at a red light) instead of the
certificate. Every `val_every` PPO iterations the greedy policy is validated on a reserved
validation set (salt `PV`); the best-validation checkpoint is kept.

Circuit breaker (pre-registered): after `min_episodes`, a run stops early only if validation has
not improved by at least `min_delta` for `patience` consecutive validations AND its best
validation P(trapped) is not above the cut heuristic's on the same set. A run that is above the
cut keeps training to `max_episodes`.

Test: best-validation and last checkpoints, cut, individual and random on fresh scenarios (salt
`PE5`), full episodes, endpoint P(trapped) = immobilised or D06 contact capture.
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

from train_caging_pilot import (  # noqa: E402
    FAILURES,
    MAPS,
    _bytes,
    _init_worker,
    _ok,
    bc_train,
    bootstrap,
    episode,
    ppo_update,
)

REWARD = "trap"


def run_set(pool, arm, weights, mode, salt, per_map):
    tasks = [
        (arm, weights, mode, m, salt, i, 9500 + i, REWARD) for m in MAPS for i in range(per_map)
    ]
    return _ok(pool.map(episode, tasks), None, f"eval:{salt}")


def rate(rows):
    return round(sum(r["trapped"] for r in rows) / max(1, len(rows)), 4)


def main() -> int:
    import torch

    from joint_interception.rl.policy import TokenPolicy

    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--arms", nargs="+", default=["T", "U"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[1, 2])
    parser.add_argument("--demo-episodes", type=int, default=300)
    parser.add_argument("--bc-epochs", type=int, default=30)
    parser.add_argument("--max-episodes", type=int, default=8000)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--val-salt", default="PV")
    parser.add_argument("--val-per-map", type=int, default=30)
    parser.add_argument("--val-every", type=int, default=8, help="PPO iterations")
    parser.add_argument("--patience", type=int, default=6, help="validations")
    parser.add_argument("--min-episodes", type=int, default=2048)
    parser.add_argument("--min-delta", type=float, default=0.011)
    parser.add_argument("--test-salt", default="PE5")
    parser.add_argument("--test-per-map", type=int, default=60)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(os.path.join(package, "checkpoints"), exist_ok=True)
    logf = open(os.path.join(package, "train_log.jsonl"), "a", encoding="utf-8")  # noqa: SIM115

    def log(entry):
        entry["wall"] = round(time.time(), 1)
        logf.write(json.dumps(entry) + "\n")
        logf.flush()
        print(json.dumps(entry), flush=True)

    evals = []

    def record(rows, name, salt):
        evals.extend(
            {k: v for k, v in r.items() if k not in ("records", "rewards")}
            | {"checkpoint": name, "set": salt}
            for r in rows
        )

    with mp.get_context("spawn").Pool(args.workers, initializer=_init_worker) as pool:
        val_rows = run_set(pool, "T", None, "cut", args.val_salt, args.val_per_map)
        cut_val = rate(val_rows)
        record(val_rows, "cut", args.val_salt)
        log({"stage": "validation_reference", "policy": "cut", "p_trapped": cut_val})
        demos = {}
        for arm in args.arms:
            tasks = [
                (arm, None, "label_demo", MAPS[i % len(MAPS)], "PD", i, 7000 + i, REWARD)
                for i in range(args.demo_episodes)
            ]
            demos[arm] = _ok(pool.map(episode, tasks), log, "demos")
            log(
                {
                    "stage": "demos",
                    "arm": arm,
                    "episodes": len(demos[arm]),
                    "decisions": sum(len(d["records"]) for d in demos[arm]),
                    "cut_p_trapped": rate(demos[arm]),
                }
            )
        test_ckpts = {}
        for arm in args.arms:
            for seed in args.seeds:
                torch.manual_seed(seed)
                random.seed(seed)
                model = TokenPolicy()
                bc_train(model, demos[arm], arm, args.bc_epochs, log)
                base = f"{arm}_seed{seed}"
                test_ckpts[f"{base}_bc"] = _bytes(model)
                bc_val = rate(
                    run_set(pool, arm, _bytes(model), "greedy", args.val_salt, args.val_per_map)
                )
                best, best_blob, stale = bc_val, _bytes(model), 0
                log(
                    {
                        "stage": "validation",
                        "run": base,
                        "episodes": 0,
                        "p_trapped": bc_val,
                        "best": best,
                        "cut": cut_val,
                    }
                )
                opt = torch.optim.Adam(model.parameters(), lr=args.lr)
                done, it, stop_reason = 0, 0, "max_episodes"
                while done < args.max_episodes:
                    w = _bytes(model)
                    tasks = [
                        (
                            arm,
                            w,
                            "sample",
                            MAPS[(done + j) % len(MAPS)],
                            f"PT{seed}",
                            done + j,
                            100000 * seed + done + j,
                            REWARD,
                        )
                        for j in range(args.batch)
                    ]
                    eps = _ok(pool.map(episode, tasks), log, "ppo")
                    stats = ppo_update(model, opt, eps)
                    done += args.batch
                    it += 1
                    log(
                        {
                            "stage": "ppo",
                            "run": base,
                            "iteration": it,
                            "episodes": done,
                            "p_trapped": rate(eps),
                            "mean_reward": round(
                                sum(e["reward"] for e in eps) / max(1, len(eps)), 3
                            ),
                            **{k: round(v, 4) for k, v in stats.items()},
                        }
                    )
                    if it % args.val_every:
                        continue
                    val = rate(
                        run_set(pool, arm, _bytes(model), "greedy", args.val_salt, args.val_per_map)
                    )
                    if val >= best + args.min_delta:
                        best, best_blob, stale = val, _bytes(model), 0
                    else:
                        stale += 1
                    log(
                        {
                            "stage": "validation",
                            "run": base,
                            "episodes": done,
                            "p_trapped": val,
                            "best": best,
                            "cut": cut_val,
                            "stale": stale,
                        }
                    )
                    if done >= args.min_episodes and stale >= args.patience and best <= cut_val:
                        stop_reason = "breaker: no improvement and not above cut"
                        break
                log(
                    {
                        "stage": "run_end",
                        "run": base,
                        "episodes": done,
                        "reason": stop_reason,
                        "best_validation": best,
                        "cut_validation": cut_val,
                    }
                )
                test_ckpts[f"{base}_best"] = best_blob
                test_ckpts[f"{base}_last"] = _bytes(model)
                for name in ("bc", "best", "last"):
                    with open(os.path.join(package, "checkpoints", f"{base}_{name}.pt"), "wb") as h:
                        h.write(test_ckpts[f"{base}_{name}"])
        for mode in ("cut", "individual", "random"):
            rows = run_set(pool, "T", None, mode, args.test_salt, args.test_per_map)
            record(rows, mode, args.test_salt)
            log({"stage": "test", "policy": mode, "p_trapped": rate(rows)})
        for name, blob in test_ckpts.items():
            rows = run_set(pool, name[0], blob, "greedy", args.test_salt, args.test_per_map)
            record(rows, name, args.test_salt)
            log({"stage": "test", "policy": name, "p_trapped": rate(rows)})
    with open(os.path.join(package, "eval.jsonl"), "w", encoding="utf-8") as h:
        for r in evals:
            h.write(json.dumps(r) + "\n")

    test = [r for r in evals if r["set"] == args.test_salt]

    def per_scenario(names):
        out = {}
        for r in test:
            if r["checkpoint"] in names:
                out.setdefault((r["map_id"], r["index"]), []).append(float(r["trapped"]))
        return {k: sum(v) / len(v) for k, v in out.items() if len(v) == len(names)}

    def paired(a_names, b_names):
        a, b = per_scenario(a_names), per_scenario(b_names)
        diffs = [a[k] - b[k] for k in a if k in b]
        return bootstrap(diffs) if diffs else None

    summary = {"p_trapped": {}, "primary": {}, "secondary": {}, "failed_episodes": len(FAILURES)}
    for c in sorted({r["checkpoint"] for r in test}):
        summary["p_trapped"][c] = rate([r for r in test if r["checkpoint"] == c])
    for arm in args.arms:
        best = [f"{arm}_seed{s}_best" for s in args.seeds]
        d = paired(best, ["cut"])
        summary["primary"][arm] = {"best_minus_cut_pooled": d, "passes": d is not None and d[1] > 0}
        summary["secondary"][arm] = {
            "best_minus_individual": paired(best, ["individual"]),
            "best_minus_bc": paired(best, [f"{arm}_seed{s}_bc" for s in args.seeds]),
            "last_minus_cut": paired([f"{arm}_seed{s}_last" for s in args.seeds], ["cut"]),
        }
    if {"T", "U"} <= set(args.arms):
        summary["secondary"]["T_minus_U_best"] = paired(
            [f"T_seed{s}_best" for s in args.seeds], [f"U_seed{s}_best" for s in args.seeds]
        )
    summary["secondary"]["cut_minus_individual"] = paired(["cut"], ["individual"])
    summary["marl_line_continues"] = any(v["passes"] for v in summary["primary"].values())
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(summary, h, indent=2)
    log({"stage": "summary", **summary})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
