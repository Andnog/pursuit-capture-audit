"""Learned ambush selection (A-96): BC from the ambush rule, then PPO; MLP vs KAN heads.

Resumable: every invocation works for at most --budget-min minutes, saves its state in the package
and exits (the session's background tasks are limited to 30 min). Phases: demos -> runs (BC + PPO
with validation and circuit breaker, per head x seed) -> test -> summary. Pre-registered rules are
in the package PROTOCOL_EN.md.
"""

from __future__ import annotations

import argparse
import io
import json
import multiprocessing as mp
import os
import pickle
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from run_endpoint_validation import DEVELOPMENT, TRAINING  # noqa: E402
from run_robustness_study import bootstrap  # noqa: E402

SETTINGS = [("AVOIDANT", 3), ("AVOIDANT", 5), ("RANDOM", 3), ("RANDOM", 5)]
HEADS = ["mlp", "kan"]
SEEDS = [1, 2, 3]
GAMMA = 0.98
STEP_COST = 0.005
CFG = {
    "demo_episodes": 400,
    "bc_epochs": 20,
    "max_episodes": 4096,
    "batch": 64,
    "val_every": 8,
    "val_per_city_setting": 12,
    "min_episodes": 1536,
    "patience": 4,
    "min_delta": 0.02,
    "lr": 3e-4,
    "ent_coef": 0.01,
    "test_scenarios": 20,
    "test_reps": 2,
}


def _init():
    import torch

    torch.set_num_threads(1)


def _bytes(model):
    import torch

    b = io.BytesIO()
    torch.save(model.state_dict(), b)
    return b.getvalue()


def episode(args):
    """args: map, index, seed, salt, level, team, kind, head, weights, mode, rseed, full."""
    from audit_cage_certificate import replay

    m, i, seed, salt, level, team, kind, head, weights, mode, rseed, full = args
    learner = None
    if kind == "learned_ambush":
        learner = {"head": head, "weights": weights, "mode": mode, "seed": rseed}
    try:
        ep, _ = replay(
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
            reward_mode="certificate" if full else "trap",
        )
    except Exception as error:  # noqa: BLE001
        return {
            "failed": f"{type(error).__name__}: {str(error)[:120]}",
            "map_id": m,
            "index": i,
            "seed": seed,
            "level": level,
            "team": team,
        }
    success = ep.contact_capture if full else (ep.trapped_at is not None or ep.contact_capture)
    return {
        "map_id": m,
        "index": i,
        "seed": seed,
        "level": level,
        "team": team,
        "success": bool(success),
        "d06": bool(ep.contact_capture),
        "records": getattr(ep, "learner_records", []),
        "choices": getattr(ep, "choice_counts", {}),
        "collided": ep.collided,
    }


def returns_of(ep):
    recs = ep["records"]
    rewards = [-STEP_COST] * len(recs)
    if recs and ep["success"]:
        rewards[-1] += 1.0
    out, g = [], 0.0
    for r in reversed(rewards):
        g = r + GAMMA * g
        out.append(g)
    return list(reversed(out))


def bc_train(model, data, epochs, rng):
    import torch

    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    for _ in range(epochs):
        rng.shuffle(data)
        for k in range(0, len(data), 64):
            batch = data[k : k + 64]
            loss = 0.0
            for r in batch:
                lg = model.logits(torch.from_numpy(r["tokens"]), torch.from_numpy(r["ctx"]))
                loss = loss - torch.log_softmax(lg, 0)[r["rule_idx"]]
            opt.zero_grad()
            (loss / len(batch)).backward()
            opt.step()


def accuracy(model, data):
    import torch

    hit = 0
    with torch.no_grad():
        for r in data:
            lg = model.logits(torch.from_numpy(r["tokens"]), torch.from_numpy(r["ctx"]))
            hit += int(torch.argmax(lg)) == r["rule_idx"]
    return round(hit / max(1, len(data)), 3)


def ppo_update(model, opt, eps, rng, epochs=4, clip=0.2):
    import torch

    samples = []
    for ep in eps:
        if "failed" in ep or not ep["records"]:
            continue
        rets = returns_of(ep)
        for r, g in zip(ep["records"], rets, strict=True):
            samples.append((r, g, g - r["value"]))
    if not samples:
        return {}
    advs = torch.tensor([s[2] for s in samples])
    mean, std = float(advs.mean()), float(advs.std()) + 1e-8
    stats = {}
    for _ in range(epochs):
        rng.shuffle(samples)
        for k in range(0, len(samples), 256):
            batch = samples[k : k + 256]
            pl = vl = en = 0.0
            for r, g, a in batch:
                c = torch.from_numpy(r["ctx"])
                dist = torch.distributions.Categorical(
                    logits=model.logits(torch.from_numpy(r["tokens"]), c)
                )
                logp = dist.log_prob(torch.tensor(r["idx"]))
                ratio = torch.exp(logp - r["logp"])
                an = (a - mean) / std
                pl = pl - torch.min(ratio * an, torch.clamp(ratio, 1 - clip, 1 + clip) * an)
                vl = vl + (model.value(c).squeeze() - g) ** 2
                en = en + dist.entropy()
            n = len(batch)
            loss = (pl + 0.5 * vl - CFG["ent_coef"] * en) / n
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 0.5)
            opt.step()
            stats = {
                "policy_loss": float(pl) / n,
                "value_loss": float(vl) / n,
                "entropy": float(en) / n,
            }
    return stats


def val_tasks(kind, head, weights, mode):
    out = []
    for m in TRAINING:
        for level, team in SETTINGS:
            for i in range(CFG["val_per_city_setting"]):
                out.append(
                    (m, i, 9500 + i, "PV9", level, team, kind, head, weights, mode, i, False)
                )
    return out


def rate(rows):
    good = [r for r in rows if "failed" not in r]
    return sum(r["success"] for r in good) / max(1, len(good))


class Session:
    def __init__(self, package, budget_min, workers):
        self.package, self.deadline = package, time.time() + 60 * budget_min
        self.workers = workers
        self.state_path = os.path.join(package, "state.pkl")
        self.log_path = os.path.join(package, "train_log.jsonl")
        if os.path.exists(self.state_path):
            with open(self.state_path, "rb") as h:
                self.s = pickle.load(h)
        else:
            self.s = {
                "phase": "demos",
                "runs": {},
                "order": [f"{h}_s{s}" for s in SEEDS for h in HEADS],
                "skip_seeds": False,
                "test_done": [],
                "cfg": CFG,
            }

    def save(self):
        tmp = self.state_path + ".tmp"
        with open(tmp, "wb") as h:
            pickle.dump(self.s, h)
        os.replace(tmp, self.state_path)

    def log(self, e):
        e["wall"] = round(time.time(), 1)
        with open(self.log_path, "a", encoding="utf-8") as h:
            h.write(json.dumps(e) + "\n")
        print(json.dumps(e), flush=True)

    def time_left(self):
        return self.deadline - time.time()


def main() -> int:
    import torch

    from joint_interception.rl.option_policy import OptionScorer

    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--smoke", action="store_true", help="tiny configuration for a pipeline test"
    )
    args = parser.parse_args()
    if args.smoke:
        CFG.update(
            demo_episodes=16,
            bc_epochs=2,
            max_episodes=64,
            batch=16,
            val_every=2,
            val_per_city_setting=1,
            min_episodes=32,
            patience=1,
            test_scenarios=1,
            test_reps=1,
        )
        HEADS[:] = ["mlp", "kan"]
        SEEDS[:] = [1]
    package = os.path.join(ROOT, args.package)
    S = Session(package, args.budget_min, args.workers)
    st = S.s
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        if st["phase"] == "demos":
            tasks = [
                (
                    TRAINING[k % 4],
                    k,
                    9500 + k,
                    "PD9",
                    *SETTINGS[k % 4],
                    "learned_ambush",
                    "mlp",
                    None,
                    "rule",
                    k,
                    False,
                )
                for k in range(CFG["demo_episodes"])
            ]
            eps = [e for e in pool.map(episode, tasks, chunksize=2) if "failed" not in e]
            st["demos"] = [r for e in eps for r in e["records"]]
            st["rule_demo_success"] = rate(eps)
            vrows = pool.map(episode, val_tasks("learned_ambush", "mlp", None, "rule"), chunksize=2)
            st["rule_val"] = rate(vrows)
            arows = pool.map(episode, val_tasks("ambush", None, None, None), chunksize=2)
            st["a95_val"] = rate(arows)
            st["phase"] = "runs"
            S.log(
                {
                    "stage": "demos",
                    "decisions": len(st["demos"]),
                    "rule_val": st["rule_val"],
                    "a95_ambush_val": st["a95_val"],
                    "rule_demo_success": st["rule_demo_success"],
                }
            )
            S.save()
        while st["phase"] == "runs" and S.time_left() > 120:
            pending = [r for r in st["order"] if not st["runs"].get(r, {}).get("done")]
            if st["skip_seeds"]:
                pending = [r for r in pending if r.endswith("_s1")]
            if not pending:
                st["phase"] = "test"
                S.save()
                break
            name = pending[0]
            head, seed = name.split("_s")[0], int(name.split("_s")[1])
            run = st["runs"].setdefault(name, {})
            model = OptionScorer(head)
            opt = torch.optim.Adam(model.parameters(), lr=CFG["lr"])
            rng = random.Random(seed)
            if "model" not in run:
                torch.manual_seed(seed)
                model = OptionScorer(head)
                data = list(st["demos"])
                rng.shuffle(data)
                held, train = data[: len(data) // 10], data[len(data) // 10 :]
                bc_train(model, train, CFG["bc_epochs"], rng)
                vrows = pool.map(
                    episode, val_tasks("learned_ambush", head, _bytes(model), "greedy"), chunksize=2
                )
                v = rate(vrows)
                run.update(
                    {
                        "model": _bytes(model),
                        "episodes": 0,
                        "iteration": 0,
                        "vals": [v],
                        "best_smoothed": v,
                        "best_model": _bytes(model),
                        "bc_model": _bytes(model),
                        "bc_val": v,
                        "bc_heldout_acc": accuracy(model, held),
                        "stale": 0,
                    }
                )
                opt = torch.optim.Adam(model.parameters(), lr=CFG["lr"])
                run["opt"] = opt.state_dict()
                S.log(
                    {
                        "stage": "bc",
                        "run": name,
                        "val": v,
                        "heldout_acc": run["bc_heldout_acc"],
                        "rule_val": st["rule_val"],
                    }
                )
                S.save()
            model.load_state_dict(torch.load(io.BytesIO(run["model"]), weights_only=True))
            opt.load_state_dict(run["opt"])
            while run["episodes"] < CFG["max_episodes"] and S.time_left() > 120:
                w = _bytes(model)
                base = 1000 * seed + run["episodes"]
                tasks = [
                    (
                        TRAINING[(base + j) % 4],
                        base + j,
                        200000 + base + j,
                        f"PT9{seed}",
                        *SETTINGS[(base + j) % 4],
                        "learned_ambush",
                        head,
                        w,
                        "sample",
                        base + j,
                        False,
                    )
                    for j in range(CFG["batch"])
                ]
                eps = pool.map(episode, tasks, chunksize=2)
                stats = ppo_update(model, opt, eps, rng)
                run["episodes"] += CFG["batch"]
                run["iteration"] += 1
                S.log(
                    {
                        "stage": "ppo",
                        "run": name,
                        "iteration": run["iteration"],
                        "episodes": run["episodes"],
                        "success": round(rate(eps), 3),
                        **{k: round(v, 4) for k, v in stats.items()},
                    }
                )
                stop = False
                if run["iteration"] % CFG["val_every"] == 0:
                    vrows = pool.map(
                        episode,
                        val_tasks("learned_ambush", head, _bytes(model), "greedy"),
                        chunksize=2,
                    )
                    v = rate(vrows)
                    run["vals"].append(v)
                    sm = sum(run["vals"][-2:]) / len(run["vals"][-2:])
                    if sm >= run["best_smoothed"] + CFG["min_delta"]:
                        run["best_smoothed"], run["best_model"], run["stale"] = sm, _bytes(model), 0
                    else:
                        run["stale"] += 1
                    S.log(
                        {
                            "stage": "validation",
                            "run": name,
                            "episodes": run["episodes"],
                            "val": v,
                            "smoothed": round(sm, 3),
                            "best_smoothed": round(run["best_smoothed"], 3),
                            "stale": run["stale"],
                            "rule_val": st["rule_val"],
                        }
                    )
                    if run["episodes"] >= CFG["min_episodes"] and run["stale"] >= CFG["patience"]:
                        run["stop_reason"] = (
                            "breaker: no smoothed gain >= min_delta for patience validations"
                        )
                        stop = True
                run["model"], run["opt"] = _bytes(model), opt.state_dict()
                S.save()
                if stop:
                    break
            if run["episodes"] >= CFG["max_episodes"] or run.get("stop_reason"):
                run["done"] = True
                run.setdefault("stop_reason", "max_episodes")
                S.log(
                    {
                        "stage": "run_end",
                        "run": name,
                        "episodes": run["episodes"],
                        "reason": run["stop_reason"],
                        "best_smoothed": run["best_smoothed"],
                        "bc_val": run["bc_val"],
                        "rule_val": st["rule_val"],
                    }
                )
                s1 = [st["runs"].get(f"{h}_s1", {}) for h in HEADS]
                if all(r.get("done") for r in s1) and not st["skip_seeds"]:
                    best = max(r["best_smoothed"] for r in s1)
                    if best < st["rule_val"] + CFG["min_delta"]:
                        st["skip_seeds"] = True
                        S.log(
                            {
                                "stage": "global_breaker",
                                "best_s1": best,
                                "rule_val": st["rule_val"],
                                "action": "seeds 2-3 skipped: no head beat the rule by min_delta",
                            }
                        )
                S.save()
        if st["phase"] == "test" and S.time_left() > 120:
            policies = [
                ("rule", "learned_ambush", "mlp", None, "rule"),
                ("ambush_a95", "ambush", None, None, None),
                ("pursuit", "pursuit", None, None, None),
                ("random_option", "learned_ambush", "mlp", None, "random"),
            ]
            for name, run in st["runs"].items():
                if run.get("done"):
                    policies.append(
                        (
                            f"{name}_best",
                            "learned_ambush",
                            name.split("_s")[0],
                            run["best_model"],
                            "greedy",
                        )
                    )
            path = os.path.join(package, "test.jsonl")
            done = set()
            if os.path.exists(path):
                with open(path, encoding="utf-8") as h:
                    for x in h:
                        r = json.loads(x)
                        if "map_id" not in r:  # failure rows written before the key fix
                            continue
                        done.add(
                            (r["policy"], r["map_id"], r["index"], r["seed"], r["level"], r["team"])
                        )
            tasks, meta = [], []
            for m in TRAINING + DEVELOPMENT:
                for i in range(CFG["test_scenarios"]):
                    for rep in range(CFG["test_reps"]):
                        seed = 9500 + i + 100000 * rep
                        for level, team in SETTINGS:
                            for pname, kind, head, w, mode in policies:
                                if (pname, m, i, seed, level, team) in done:
                                    continue
                                tasks.append(
                                    (m, i, seed, "PE9", level, team, kind, head, w, mode, i, True)
                                )
                                meta.append(pname)
            budget_tasks = int(max(0, S.time_left() - 90) * 2.0)  # ~2 episodes/s with 8 workers
            tasks, meta = tasks[:budget_tasks], meta[:budget_tasks]
            with open(path, "a", encoding="utf-8") as h:
                for pname, r in zip(meta, pool.imap(episode, tasks, chunksize=2), strict=True):
                    r = {k: v for k, v in r.items() if k != "records"} | {"policy": pname}
                    h.write(json.dumps(r) + "\n")
                    h.flush()
            S.log({"stage": "test_chunk", "episodes": len(tasks)})
            if len(tasks) == 0:
                st["phase"] = "summary"
            S.save()
        if st["phase"] == "summary":
            summary(package, st)
            st["phase"] = "done"
            S.save()
            S.log({"stage": "done"})
    return 0


def summary(package, st):
    with open(os.path.join(package, "test.jsonl"), encoding="utf-8") as h:
        rows = [json.loads(x) for x in h]
    rows = [r for r in rows if "map_id" in r]  # drop keyless failure rows (pre-fix)
    good = [r for r in rows if "failed" not in r]
    acc = {}
    for r in good:
        acc.setdefault((r["policy"], r["level"], r["team"], r["map_id"], r["index"]), []).append(
            r["d06"]
        )
    mean = {k: sum(v) / len(v) for k, v in acc.items()}

    def per(policy):
        return {k[1:]: v for k, v in mean.items() if k[0] == policy}

    out = {
        "failed": len(rows) - len(good),
        "collisions": sum(r.get("collided", False) for r in good),
        "rates": {},
        "primary": {},
        "secondary": {},
        "runs": {},
    }
    pols = sorted({r["policy"] for r in good})
    for p in pols:
        out["rates"][p] = bootstrap(list(per(p).values()))
    rule = per("rule")
    for head in HEADS:
        names = [p for p in pols if p.startswith(f"{head}_s")]
        if not names:
            continue
        maps = [per(n) for n in names]
        ks = sorted(set(rule).intersection(*maps))
        learned = {k: sum(m[k] for m in maps) / len(maps) for k in ks}
        d = bootstrap([learned[k] - rule[k] for k in ks])
        out["primary"][head] = {"learned_minus_rule": d, "passes": d[1] > 0, "runs": names}
        for ref in ("pursuit", "ambush_a95", "random_option"):
            r2 = per(ref)
            kk = [k for k in ks if k in r2]
            out["secondary"][f"{head}_minus_{ref}"] = bootstrap([learned[k] - r2[k] for k in kk])
        out["secondary"][f"{head}_by_cell"] = {
            f"{lv}_team{t}": bootstrap(
                [learned[k] - rule[k] for k in ks if k[0] == lv and k[1] == t]
            )
            for lv, t in SETTINGS
        }
    if all(h in out["primary"] for h in HEADS):
        names_m = [p for p in pols if p.startswith("mlp_s")]
        names_k = [p for p in pols if p.startswith("kan_s")]
        pm, pk = [per(n) for n in names_m], [per(n) for n in names_k]
        ks = sorted(set.intersection(*(set(x) for x in pm + pk)))
        out["secondary"]["kan_minus_mlp"] = bootstrap(
            [sum(x[k] for x in pk) / len(pk) - sum(x[k] for x in pm) / len(pm) for k in ks]
        )
    for name, run in st["runs"].items():
        out["runs"][name] = {
            k: run.get(k)
            for k in (
                "episodes",
                "stop_reason",
                "bc_val",
                "best_smoothed",
                "vals",
                "bc_heldout_acc",
            )
        }
    out["rule_val"], out["a95_val"] = st.get("rule_val"), st.get("a95_val")
    out["skip_seeds"] = st.get("skip_seeds")
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
