"""Development check (A-80): can the token policy reproduce the cut heuristic? BC then DAgger.

Labels come from the stateless cut (`rl.rollout.cut_label`) mapped to each arm's tokens. Reports
per-pursuer imitation accuracy on held-out decisions and greedy P(physical cage) on the reserved
scenarios after BC and after each DAgger round, next to the heuristic itself.
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

from train_caging_pilot import MAPS, _bytes, _init_worker, _ok, episode, evaluate  # noqa: E402


def train(model, data, epochs, lr=1e-3):
    import torch

    from joint_interception.rl.policy import joint_logp_entropy

    opt = torch.optim.Adam(model.parameters(), lr=lr)
    for _ in range(epochs):
        random.shuffle(data)
        for i in range(0, len(data), 64):
            batch = data[i : i + 64]
            loss = -sum(joint_logp_entropy(model, r)[0] for r in batch) / len(batch)
            opt.zero_grad()
            loss.backward()
            opt.step()


def accuracy(model, data):
    import torch

    from joint_interception.rl.policy import TokenPolicy  # noqa: F401

    hit = n = 0
    with torch.no_grad():
        for r in data:
            ctx = torch.from_numpy(r["ctx"])
            for feats, idx in r["steps"]:
                hit += int(torch.argmax(model.logits(torch.from_numpy(feats), ctx))) == idx
                n += 1
    return round(hit / max(1, n), 3)


def main() -> int:
    import torch

    from joint_interception.rl.policy import TokenPolicy

    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--arms", nargs="+", default=["T", "U"])
    parser.add_argument("--demos", type=int, default=300)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--per-round", type=int, default=150)
    parser.add_argument("--eval-scenarios", type=int, default=20)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    log_path = os.path.join(args.out, "log.jsonl")

    def log(e):
        with open(log_path, "a", encoding="utf-8") as h:
            h.write(json.dumps(e) + "\n")
        print(json.dumps(e), flush=True)

    with mp.get_context("spawn").Pool(args.workers, initializer=_init_worker) as pool:
        ref = evaluate(pool, "T", None, "cut_label", args.eval_scenarios)
        log(
            {
                "policy": "cut_label (stateless heuristic)",
                "p_cage": round(sum(r["caged"] for r in ref) / len(ref), 3),
            }
        )
        for arm in args.arms:
            torch.manual_seed(1)
            random.seed(1)
            tasks = [
                (arm, None, "label_demo", MAPS[i % len(MAPS)], "PD", i, 7000 + i)
                for i in range(args.demos)
            ]
            demos = _ok(pool.map(episode, tasks), None, "demos")
            data = [r for ep in demos for r in ep["records"]]
            random.shuffle(data)
            held, data = data[: len(data) // 10], data[len(data) // 10 :]
            model = TokenPolicy()
            train(model, data, 30)
            rows = evaluate(pool, arm, _bytes(model), "greedy", args.eval_scenarios)
            log(
                {
                    "arm": arm,
                    "stage": "bc",
                    "decisions": len(data),
                    "acc_train": accuracy(model, data[:3000]),
                    "acc_heldout": accuracy(model, held),
                    "p_cage": round(sum(r["caged"] for r in rows) / len(rows), 3),
                }
            )
            for k in range(1, args.rounds + 1):
                tasks = [
                    (arm, _bytes(model), "dagger", MAPS[i % len(MAPS)], f"PG{k}", i, 20000 * k + i)
                    for i in range(args.per_round)
                ]
                eps = _ok(pool.map(episode, tasks), None, "dagger")
                new = [r for ep in eps for r in ep["records"]]
                acc_on_own = accuracy(model, new)
                data += new
                train(model, data, 15)
                rows = evaluate(pool, arm, _bytes(model), "greedy", args.eval_scenarios)
                log(
                    {
                        "arm": arm,
                        "stage": f"dagger{k}",
                        "decisions": len(data),
                        "acc_on_learner_states": acc_on_own,
                        "acc_heldout": accuracy(model, held),
                        "p_cage": round(sum(r["caged"] for r in rows) / len(rows), 3),
                        "learner_p_cage_during_round": round(
                            sum(e["caged"] for e in eps) / max(1, len(eps)), 3
                        ),
                    }
                )
            with open(os.path.join(args.out, f"{arm}_dagger.pt"), "wb") as h:
                h.write(_bytes(model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
