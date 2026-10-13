"""MAPPO for the multi-agent ambush (A-103): BC from the optimised planner, then MAPPO;
MLP vs KAN actors; run and global circuit breakers; pre-registered test. Resumable in chunks.

Each pursuer is an agent with a shared actor over its own tokens (blocking slots, CHASE, STAY) and a
centralised critic over a global state. Shared team reward: +1 on trapping, -0.005 per tick.
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
GAMMA, LAM, STEP_COST = 0.99, 0.95, 0.005
CFG = {
    "demo_episodes": 300,
    "bc_epochs": 15,
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
    "test_teams": [3, 5, 7],
}


def _init():
    import torch

    torch.set_num_threads(1)


def _bytes(model):
    import torch

    b = io.BytesIO()
    torch.save(model.state_dict(), b)
    return b.getvalue()


def params():
    with open(
        os.path.join(ROOT, "experiments", "20261002_ambush_optimization_r01", "summary.json"),
        encoding="utf-8",
    ) as h:
        return json.load(h)["final_params"]


def episode(args):
    from audit_cage_certificate import replay

    key, m, i, seed, salt, level, team, kind, head, weights, mode, rseed, full = args
    learner = None
    if kind == "mappo":
        learner = {
            "params": params(),
            "head": head,
            "weights": weights,
            "mode": mode,
            "seed": rseed,
        }
    elif kind == "ambush_plus":
        learner = {"params": params()}
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
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    ok = ep.contact_capture if full else (ep.trapped_at is not None or ep.contact_capture)
    return {
        "key": key,
        "success": bool(ok),
        "d06": bool(ep.contact_capture),
        "collided": ep.collided,
        "ticks": getattr(ep, "mappo_ticks", []) if not full else [],
    }


def rate(rows):
    good = [r for r in rows if "failed" not in r]
    return sum(r["success"] for r in good) / max(1, len(good))


def bc_train(model, data, epochs, rng):
    import torch

    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    for _ in range(epochs):
        rng.shuffle(data)
        for k in range(0, len(data), 128):
            batch = data[k : k + 128]
            loss = 0.0
            for r in batch:
                lg = model.logits(torch.from_numpy(r["tokens"]), torch.from_numpy(r["ctx"]))
                loss = loss - torch.log_softmax(lg, 0)[r["teacher_idx"]]
            opt.zero_grad()
            (loss / len(batch)).backward()
            opt.step()


def accuracy(model, data):
    import torch

    hit = 0
    with torch.no_grad():
        for r in data:
            lg = model.logits(torch.from_numpy(r["tokens"]), torch.from_numpy(r["ctx"]))
            hit += int(torch.argmax(lg)) == r["teacher_idx"]
    return round(hit / max(1, len(data)), 4)


def mappo_update(model, opt, eps, rng, epochs=4, clip=0.2):
    import torch

    samples, vsamples = [], []
    for ep in eps:
        if "failed" in ep or not ep["ticks"]:
            continue
        ticks = ep["ticks"]
        g = torch.from_numpy(__import__("numpy").stack([t["global"] for t in ticks]))
        with torch.no_grad():
            vals = model.value(g).tolist()
        rewards = [-STEP_COST] * len(ticks)
        if ep["success"]:
            rewards[-1] += 1.0
        adv, last = [0.0] * len(ticks), 0.0
        for t in reversed(range(len(ticks))):
            nxt = vals[t + 1] if t + 1 < len(ticks) else 0.0
            delta = rewards[t] + GAMMA * nxt - vals[t]
            last = delta + GAMMA * LAM * last
            adv[t] = last
        for t, tick in enumerate(ticks):
            vsamples.append((tick["global"], adv[t] + vals[t]))
            for a in tick["agents"]:
                samples.append((a, adv[t]))
    if not samples:
        return {}
    advs = torch.tensor([s[1] for s in samples])
    mean, std = float(advs.mean()), float(advs.std()) + 1e-8
    stats = {}
    for _ in range(epochs):
        rng.shuffle(samples)
        rng.shuffle(vsamples)
        nb = max(1, len(samples) // 512)
        for b in range(nb):
            batch = samples[b * 512 : (b + 1) * 512]
            vb = vsamples[b * len(vsamples) // nb : (b + 1) * len(vsamples) // nb]
            pl = en = 0.0
            for a, ad in batch:
                dist = torch.distributions.Categorical(
                    logits=model.logits(torch.from_numpy(a["tokens"]), torch.from_numpy(a["ctx"]))
                )
                ratio = torch.exp(dist.log_prob(torch.tensor(a["idx"])) - a["logp"])
                an = (ad - mean) / std
                pl = pl - torch.min(ratio * an, torch.clamp(ratio, 1 - clip, 1 + clip) * an)
                en = en + dist.entropy()
            gb = torch.from_numpy(__import__("numpy").stack([v[0] for v in vb]))
            rt = torch.tensor([v[1] for v in vb], dtype=torch.float32)
            vl = ((model.value(gb) - rt) ** 2).mean()
            loss = pl / len(batch) + 0.5 * vl - CFG["ent_coef"] * en / len(batch)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 0.5)
            opt.step()
            stats = {
                "policy_loss": float(pl) / len(batch),
                "value_loss": float(vl),
                "entropy": float(en) / len(batch),
            }
    return stats


def val_tasks(kind, head, weights, mode, tag):
    out = []
    for m in TRAINING:
        for level, team in SETTINGS:
            for i in range(CFG["val_per_city_setting"]):
                out.append(
                    (
                        f"{tag}|{m}|{level}|{team}|{i}",
                        m,
                        i,
                        9500 + i,
                        "PV13",
                        level,
                        team,
                        kind,
                        head,
                        weights,
                        mode,
                        i,
                        False,
                    )
                )
    return out


def main() -> int:
    import torch

    from joint_interception.rl.mappo_policy import MappoActorCritic

    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        CFG.update(
            demo_episodes=16,
            bc_epochs=1,
            max_episodes=32,
            batch=16,
            val_every=1,
            val_per_city_setting=1,
            min_episodes=16,
            patience=1,
            test_scenarios=1,
            test_reps=1,
            test_teams=[3],
        )
        SEEDS[:] = [1]
    package = os.path.join(ROOT, args.package)
    deadline = time.time() + 60 * args.budget_min
    spath = os.path.join(package, "state.pkl")
    if os.path.exists(spath):
        with open(spath, "rb") as h:
            st = pickle.load(h)
    else:
        st = {
            "phase": "demos",
            "runs": {},
            "skip": False,
            "order": [f"{h}_s{s}" for s in SEEDS for h in HEADS],
        }

    def save():
        with open(spath + ".tmp", "wb") as h:
            pickle.dump(st, h)
        os.replace(spath + ".tmp", spath)

    def log(e):
        e["wall"] = round(time.time(), 1)
        with open(os.path.join(package, "train_log.jsonl"), "a", encoding="utf-8") as h:
            h.write(json.dumps(e) + "\n")
        print(json.dumps(e), flush=True)

    left = lambda: deadline - time.time()  # noqa: E731
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        if st["phase"] == "demos":
            tasks = [
                (
                    f"d{k}",
                    TRAINING[k % 4],
                    k,
                    9500 + k,
                    "PD13",
                    *SETTINGS[k % 4],
                    "mappo",
                    "mlp",
                    None,
                    "teacher",
                    k,
                    False,
                )
                for k in range(CFG["demo_episodes"])
            ]
            eps = [e for e in pool.map(episode, tasks, chunksize=2) if "failed" not in e]
            st["demos"] = [a for e in eps for t in e["ticks"] for a in t["agents"]]
            st["teacher_val"] = rate(
                pool.map(episode, val_tasks("mappo", "mlp", None, "teacher", "vt"), chunksize=2)
            )
            st["planner_val"] = rate(
                pool.map(episode, val_tasks("ambush_plus", None, None, None, "vp"), chunksize=2)
            )
            st["phase"] = "runs"
            log(
                {
                    "stage": "demos",
                    "agent_decisions": len(st["demos"]),
                    "teacher_val": st["teacher_val"],
                    "planner_val": st["planner_val"],
                    "label_chase_share": round(
                        sum(a["teacher_idx"] == 0 for a in st["demos"]) / max(1, len(st["demos"])),
                        3,
                    ),
                }
            )
            save()
        ref = max(st["teacher_val"], st["planner_val"])
        while st["phase"] == "runs" and left() > 150:
            pending = [r for r in st["order"] if not st["runs"].get(r, {}).get("done")]
            if st["skip"]:
                pending = [r for r in pending if r.endswith("_s1")]
            if not pending:
                st["phase"] = "test"
                save()
                break
            name = pending[0]
            head, seed = name.split("_s")[0], int(name.split("_s")[1])
            run = st["runs"].setdefault(name, {})
            rng = random.Random(seed)
            if "model" not in run:
                torch.manual_seed(seed)
                model = MappoActorCritic(head)
                data = list(st["demos"])
                rng.shuffle(data)
                held, train = data[: len(data) // 10], data[len(data) // 10 :]
                bc_train(model, train, CFG["bc_epochs"], rng)
                v = rate(
                    pool.map(
                        episode,
                        val_tasks("mappo", head, _bytes(model), "greedy", f"v{name}0"),
                        chunksize=2,
                    )
                )
                opt = torch.optim.Adam(model.parameters(), lr=CFG["lr"])
                run.update(
                    model=_bytes(model),
                    opt=opt.state_dict(),
                    episodes=0,
                    iteration=0,
                    vals=[v],
                    best=v,
                    best_model=_bytes(model),
                    bc_val=v,
                    stale=0,
                    bc_acc=accuracy(model, held),
                )
                log(
                    {
                        "stage": "bc",
                        "run": name,
                        "val": v,
                        "heldout_acc": run["bc_acc"],
                        "ref_val": ref,
                    }
                )
                save()
            model = MappoActorCritic(head)
            model.load_state_dict(torch.load(io.BytesIO(run["model"]), weights_only=True))
            opt = torch.optim.Adam(model.parameters(), lr=CFG["lr"])
            opt.load_state_dict(run["opt"])
            stop = False
            while run["episodes"] < CFG["max_episodes"] and left() > 150 and not stop:
                base = 1000 * seed + run["episodes"]
                w = _bytes(model)
                tasks = [
                    (
                        f"t{base + j}",
                        TRAINING[(base + j) % 4],
                        base + j,
                        300000 + base + j,
                        f"PT13{seed}",
                        *SETTINGS[(base + j) % 4],
                        "mappo",
                        head,
                        w,
                        "sample",
                        base + j,
                        False,
                    )
                    for j in range(CFG["batch"])
                ]
                eps = pool.map(episode, tasks, chunksize=2)
                stats = mappo_update(model, opt, eps, rng)
                run["episodes"] += CFG["batch"]
                run["iteration"] += 1
                log(
                    {
                        "stage": "mappo",
                        "run": name,
                        "iteration": run["iteration"],
                        "episodes": run["episodes"],
                        "success": round(rate(eps), 3),
                        **{k: round(v, 4) for k, v in stats.items()},
                    }
                )
                if run["iteration"] % CFG["val_every"] == 0:
                    v = rate(
                        pool.map(
                            episode,
                            val_tasks(
                                "mappo", head, _bytes(model), "greedy", f"v{name}{run['iteration']}"
                            ),
                            chunksize=2,
                        )
                    )
                    run["vals"].append(v)
                    sm = sum(run["vals"][-2:]) / len(run["vals"][-2:])
                    if sm >= run["best"] + CFG["min_delta"]:
                        run["best"], run["best_model"], run["stale"] = sm, _bytes(model), 0
                    else:
                        run["stale"] += 1
                    log(
                        {
                            "stage": "validation",
                            "run": name,
                            "episodes": run["episodes"],
                            "val": v,
                            "smoothed": round(sm, 3),
                            "best": round(run["best"], 3),
                            "stale": run["stale"],
                            "ref_val": ref,
                        }
                    )
                    if run["episodes"] >= CFG["min_episodes"] and run["stale"] >= CFG["patience"]:
                        run["stop_reason"] = "breaker"
                        stop = True
                run["model"], run["opt"] = _bytes(model), opt.state_dict()
                save()
            if stop or run["episodes"] >= CFG["max_episodes"]:
                run["done"] = True
                run.setdefault("stop_reason", "max_episodes")
                log(
                    {
                        "stage": "run_end",
                        "run": name,
                        "episodes": run["episodes"],
                        "reason": run["stop_reason"],
                        "best": run["best"],
                        "bc_val": run["bc_val"],
                        "ref_val": ref,
                    }
                )
                s1 = [st["runs"].get(f"{h}_s1", {}) for h in HEADS]
                if all(r.get("done") for r in s1) and not st["skip"]:
                    if max(r["best"] for r in s1) < ref + CFG["min_delta"]:
                        st["skip"] = True
                        log(
                            {
                                "stage": "global_breaker",
                                "best_s1": max(r["best"] for r in s1),
                                "ref_val": ref,
                                "action": "seeds 2-3 skipped",
                            }
                        )
                save()
        if st["phase"] == "test" and left() > 150:
            from run_ambush_optimization import Store

            store = Store(package)
            pols = [
                ("planner_c215", "ambush_plus", None, None, None),
                ("teacher_mode", "mappo", "mlp", None, "teacher"),
                ("pursuit", "pursuit", None, None, None),
                ("random_slot", "mappo", "mlp", None, "random"),
            ]
            for name, run in st["runs"].items():
                if run.get("done"):
                    pols.append(
                        (f"mappo_{name}", "mappo", name.split("_s")[0], run["best_model"], "greedy")
                    )
            tasks = []
            for m in TRAINING + DEVELOPMENT:
                for i in range(CFG["test_scenarios"]):
                    for rep in range(CFG["test_reps"]):
                        seed = 9500 + i + 100000 * rep
                        for level in ("AVOIDANT", "RANDOM"):
                            for team in CFG["test_teams"]:
                                for pname, kind, head, w, mode in pols:
                                    tasks.append(
                                        (
                                            f"test|{pname}|{m}|{i}|{seed}|{level}|{team}",
                                            m,
                                            i,
                                            seed,
                                            "PE13",
                                            level,
                                            team,
                                            kind,
                                            head,
                                            w,
                                            mode,
                                            i,
                                            True,
                                        )
                                    )
            if store.run(pool, tasks, deadline - 60, episode):
                st["phase"] = "summary"
            save()
            log(
                {
                    "stage": "test_chunk",
                    "done": sum(1 for t in tasks if t[0] in store.rows),
                    "of": len(tasks),
                }
            )
        if st["phase"] == "summary":
            from run_ambush_optimization import Store

            summarise(package, Store(package), st)
            st["phase"] = "done"
            save()
            log({"stage": "done"})
    return 0


def summarise(package, store, st):
    by = {}
    for k, r in store.rows.items():
        if not k.startswith("test|") or "failed" in r:
            continue
        _, p, m, i, seed, level, team = k.split("|")
        by.setdefault((p, level, int(team), m, int(i)), []).append(float(r["d06"]))
    mean = {k: sum(v) / len(v) for k, v in by.items()}
    pols = sorted({k[0] for k in mean})

    def per(p):
        return {k[1:]: v for k, v in mean.items() if k[0] == p}

    out = {
        "rates": {p: bootstrap(list(per(p).values())) for p in pols},
        "primary": {},
        "cells": {},
        "runs": {
            n: {
                k: r.get(k) for k in ("episodes", "stop_reason", "bc_val", "best", "vals", "bc_acc")
            }
            for n, r in st["runs"].items()
        },
        "teacher_val": st.get("teacher_val"),
        "planner_val": st.get("planner_val"),
        "skip": st.get("skip"),
        "failed": sum(1 for k, r in store.rows.items() if k.startswith("test|") and "failed" in r),
    }
    plan = per("planner_c215")
    for head in HEADS:
        names = [p for p in pols if p.startswith(f"mappo_{head}_s")]
        if not names:
            continue
        maps = [per(n) for n in names]
        ks = sorted(set(plan).intersection(*maps))
        learned = {k: sum(x[k] for x in maps) / len(maps) for k in ks}
        d = bootstrap([learned[k] - plan[k] for k in ks])
        out["primary"][head] = {"mappo_minus_planner": d, "passes": d[1] > 0, "runs": names}
        for ref in ("pursuit", "teacher_mode", "random_slot"):
            r2 = per(ref)
            kk = [k for k in ks if k in r2]
            out["primary"][head][f"minus_{ref}"] = bootstrap([learned[k] - r2[k] for k in kk])
        out["cells"][head] = {
            f"{lv}_team{t}": {
                "mappo": bootstrap([learned[k] for k in ks if k[0] == lv and k[1] == t]),
                "planner": bootstrap([plan[k] for k in ks if k[0] == lv and k[1] == t]),
                "diff": bootstrap([learned[k] - plan[k] for k in ks if k[0] == lv and k[1] == t]),
            }
            for lv in ("AVOIDANT", "RANDOM")
            for t in CFG["test_teams"]
        }
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
