"""MAPPO v2 for the multi-agent ambush (A-116): corrected design, pre-registered test.

Changes from `train_mappo.py` (A-103/105, kept unchanged):
1. demonstrations, training and validation cover all 16 TRAINING city x setting pairs (`combo`);
2. reward, validation and checkpoint selection use PC capture (the evaluation endpoint); training
   episodes are truncated at the PC capture time (`truncate_ticks`), with +1 there;
3. faithful teacher (`native/mappo_ambush_v2.py`): planner blocks outside the slot list are executed
   and excluded from imitation; slot cap 40;
4. -1 on collision;
5. the python RNG state is saved across chunks;
6. pure functions (`combo`, `episode_rewards`, `compute_gae`, `truncate_ticks`, `surrogate`) are
   unit tested in `tests/test_mappo_v2.py`.
Finite-horizon convention: the value after the last kept tick is 0 (episode end or capture); time is
part of the global state. Two seeds per head, no global breaker; run breaker as in A-103.
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
SEEDS = [1, 2]
GAMMA, LAM, STEP_COST = 0.99, 0.95, 0.005
CFG = {
    "demo_episodes": 320,
    "bc_epochs": 15,
    "max_episodes": 4096,
    "batch": 64,
    "val_every": 8,
    "val_per_combo": 12,
    "min_episodes": 1536,
    "patience": 4,
    "min_delta": 0.02,
    "lr": 3e-4,
    "ent_coef": 0.01,
    "test_scenarios": 20,
    "test_reps": 2,
    "test_teams": [3, 5, 7],
}
A99 = os.path.join(ROOT, "experiments", "20261002_ambush_optimization_r01", "summary.json")
OLD = os.path.join(ROOT, "experiments", "20261002_mappo_r01", "state.pkl")


# -- pure functions (unit tested) ----------------------------------------------------------------
def combo(k: int):
    """(city, (level, team)) for task k; 16 consecutive k cover every pair once."""
    return TRAINING[k % 4], SETTINGS[(k // 4) % 4]


def truncate_ticks(ticks, t_capture):
    """Decision ticks up to and including the PC capture time (all ticks if no capture)."""
    if t_capture is None:
        return list(ticks)
    return [t for t in ticks if t["t"] <= t_capture + 1e-9]


def episode_rewards(n_ticks: int, success: bool, collided: bool, step_cost: float = STEP_COST):
    rewards = [-step_cost] * n_ticks
    if n_ticks:
        rewards[-1] += (1.0 if success else 0.0) - (1.0 if collided else 0.0)
    return rewards


def compute_gae(rewards, values, gamma: float = GAMMA, lam: float = LAM):
    """Generalised advantage estimates; the value after the last tick is 0 (terminal)."""
    adv, last = [0.0] * len(rewards), 0.0
    for t in reversed(range(len(rewards))):
        nxt = values[t + 1] if t + 1 < len(rewards) else 0.0
        delta = rewards[t] + gamma * nxt - values[t]
        last = delta + gamma * lam * last
        adv[t] = last
    return adv


def surrogate(ratio, adv_norm, clip: float = 0.2):
    """PPO clipped surrogate (to be maximised) for one sample, as a torch scalar."""
    import torch

    return torch.min(ratio * adv_norm, torch.clamp(ratio, 1 - clip, 1 + clip) * adv_norm)


def family_bootstrap(diffs_by_family, reps=10000, seed=7, alpha=0.05):
    """Mean of all cell differences; percentile interval resampling families (lists of cells)."""
    fams = sorted(diffs_by_family)
    allx = [x for f in fams for x in diffs_by_family[f]]
    if not allx:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(reps):
        xs = []
        for f in (rng.choice(fams) for _ in fams):
            xs += diffs_by_family[f]
        means.append(sum(xs) / len(xs))
    means.sort()
    lo, hi = int(alpha / 2 * reps), int((1 - alpha / 2) * reps) - 1
    return [round(sum(allx) / len(allx), 3), round(means[lo], 3), round(means[hi], 3)]


# -- simulation ----------------------------------------------------------------------------------
def _init():
    import torch

    torch.set_num_threads(1)


def _bytes(model):
    import torch

    b = io.BytesIO()
    torch.save(model.state_dict(), b)
    return b.getvalue()


def _params():
    with open(A99, encoding="utf-8") as h:
        return json.load(h)["final_params"]


def episode(args):
    from audit_cage_certificate import replay
    from run_test_confirmation import _capture_time

    key, m, i, seed, salt, level, team, kind, head, weights, mode, rseed, keep_ticks = args
    learner = None
    if kind in ("mappo", "mappo_v2"):
        learner = {
            "params": _params(),
            "head": head,
            "weights": weights,
            "mode": mode,
            "seed": rseed,
        }
    elif kind == "ambush_plus":
        learner = {"params": _params()}
    try:
        ep, _ = replay(
            m, i, seed, salt, "T", None, "policy", 300.0, kind=kind, speed=1.0, level=level,
            team=team, learner=learner, reward_mode="certificate",
        )  # fmt: skip
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    t_c = _capture_time(ep) if ep.contact_capture else None
    ticks = truncate_ticks(getattr(ep, "mappo_ticks", []), t_c) if keep_ticks else []
    return {
        "key": key,
        "success": bool(ep.contact_capture),
        "d06": bool(ep.contact_capture),
        "capture_t": t_c,
        "collided": ep.collided,
        "ticks": ticks,
        "represented": getattr(ep, "teacher_represented", None),
        "unrepresentable": getattr(ep, "teacher_unrepresentable", None),
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
    import numpy as np
    import torch

    samples, vsamples = [], []
    for ep in eps:
        if "failed" in ep or not ep["ticks"]:
            continue
        ticks = ep["ticks"]
        g = torch.from_numpy(np.stack([t["global"] for t in ticks]))
        with torch.no_grad():
            vals = model.value(g).tolist()
        rewards = episode_rewards(len(ticks), ep["success"], ep["collided"])
        adv = compute_gae(rewards, vals)
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
                pl = pl - surrogate(ratio, (ad - mean) / std, clip)
                en = en + dist.entropy()
            gb = torch.from_numpy(np.stack([v[0] for v in vb]))
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


def task(key, k, seed, salt, kind, head, weights, mode, keep):
    m, (level, team) = combo(k)
    return (key, m, k, seed, salt, level, team, kind, head, weights, mode, k, keep)


def val_tasks(kind, head, weights, mode, tag):
    n = 16 * CFG["val_per_combo"]
    return [
        task(f"{tag}|{k}", k, 9500 + k, "PV17", kind, head, weights, mode, False) for k in range(n)
    ]


def test_tasks(pols):
    out = []
    for m in TRAINING + DEVELOPMENT:
        for i in range(CFG["test_scenarios"]):
            for rep in range(CFG["test_reps"]):
                seed = 9500 + i + 100000 * rep
                for level in ("AVOIDANT", "RANDOM"):
                    for team in CFG["test_teams"]:
                        for pname, kind, head, w, mode in pols:
                            out.append(
                                (f"test|{pname}|{m}|{i}|{seed}|{level}|{team}", m, i, seed, "PE17")
                                + (level, team, kind, head, w, mode, i, False)
                            )
    return out


def summarise(package, store, st):
    rows = [r for k, r in store.rows.items() if k.startswith("test|") and "failed" not in r]
    by = {}
    for r in rows:
        _, p, m, i, seed, level, team = r["key"].split("|")
        by.setdefault((p, m, int(i), level, int(team)), []).append(float(r["d06"]))
    mean = {k: sum(v) / len(v) for k, v in by.items()}
    names = sorted({k[0] for k in mean})

    def diffs(a, b):
        fam = {}
        for k, v in mean.items():
            if k[0] == a and (b,) + k[1:] in mean:
                fam.setdefault(k[1:4], []).append(v - mean[(b,) + k[1:]])
        return fam

    out = {
        "rates": {n: bootstrap([v for k, v in mean.items() if k[0] == n]) for n in names},
        "selected": st.get("selected"),
        "runs": {
            n: {
                k: r.get(k) for k in ("best", "bc_val", "episodes", "stop_reason", "vals", "bc_acc")
            }
            for n, r in st["runs"].items()
        },
        "teacher": {k: st.get(k) for k in ("teacher_val", "planner_val", "teacher_fidelity")},
        "failed": sum(1 for k, r in store.rows.items() if k.startswith("test|") and "failed" in r),
        "collisions": sum(r.get("collided", False) for r in rows),
        "primary": {},
        "secondary": {},
    }
    for head in HEADS:
        sel = f"v2_{st['selected'][head]}"
        d = family_bootstrap(diffs(sel, "planner_c215"), alpha=0.025)
        out["primary"][head] = {
            "checkpoint": sel,
            "minus_planner_97.5": d,
            "passes": bool(d and d[1] > 0),
        }
        out["secondary"][f"{head}_minus_old"] = family_bootstrap(diffs(sel, f"old_{head}"))
        out["secondary"][f"{head}_minus_teacher"] = family_bootstrap(diffs(sel, "teacher_v2"))
        out["secondary"][f"{head}_minus_pursuit"] = family_bootstrap(diffs(sel, "pursuit"))
        for s in SEEDS:
            out["secondary"][f"{head}_s{s}_minus_planner"] = family_bootstrap(
                diffs(f"v2_{head}_s{s}", "planner_c215")
            )
    out["secondary"]["kan_minus_mlp"] = family_bootstrap(
        diffs(f"v2_{st['selected']['kan']}", f"v2_{st['selected']['mlp']}")
    )
    out["secondary"]["teacher_minus_planner"] = family_bootstrap(
        diffs("teacher_v2", "planner_c215")
    )
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
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
            demo_episodes=16, bc_epochs=1, max_episodes=32, batch=16, val_every=1, val_per_combo=1,
            min_episodes=16, patience=1, test_scenarios=1, test_reps=1, test_teams=[3],
        )  # fmt: skip
        SEEDS[:] = [1]
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    deadline = time.time() + 60 * args.budget_min
    spath = os.path.join(package, "state.pkl")
    if os.path.exists(spath):
        with open(spath, "rb") as h:
            st = pickle.load(h)
    else:
        st = {"phase": "demos", "runs": {}, "order": [f"{h}_s{s}" for s in SEEDS for h in HEADS]}

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
                task(f"d{k}", k, 9500 + k, "PD17", "mappo_v2", "mlp", None, "teacher", True)
                for k in range(CFG["demo_episodes"])
            ]
            eps = [e for e in pool.map(episode, tasks, chunksize=2) if "failed" not in e]
            recs = [a for e in eps for t in e["ticks"] for a in t["agents"]]
            st["demos"] = [a for a in recs if a["teacher_idx"] >= 0]
            rep = sum(e["represented"] or 0 for e in eps)
            unrep = sum(e["unrepresentable"] or 0 for e in eps)
            st["teacher_fidelity"] = {
                "represented_blocks": rep,
                "unrepresentable_blocks": unrep,
                "unrepresentable_share": round(unrep / max(1, rep + unrep), 4),
                "chase_label_share": round(
                    sum(a["teacher_idx"] == 0 for a in st["demos"]) / max(1, len(st["demos"])), 4
                ),
            }
            st["teacher_val"] = rate(
                pool.map(episode, val_tasks("mappo_v2", "mlp", None, "teacher", "vt"), chunksize=2)
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
                    **st["teacher_fidelity"],
                }
            )
            save()
        ref = max(st["teacher_val"], st["planner_val"])
        while st["phase"] == "runs" and left() > 150:
            pending = [r for r in st["order"] if not st["runs"].get(r, {}).get("done")]
            if not pending:
                st["selected"] = {
                    h: max(
                        (n for n in st["runs"] if n.startswith(h)),
                        key=lambda n: (st["runs"][n]["best"], n),
                    )
                    for h in HEADS
                }
                st["phase"] = "test"
                log({"stage": "selected", **st["selected"]})
                save()
                break
            name = pending[0]
            head, seed = name.split("_s")[0], int(name.split("_s")[1])
            run = st["runs"].setdefault(name, {})
            rng = random.Random(seed)
            if "rng_state" in run:
                rng.setstate(run["rng_state"])
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
                        val_tasks("mappo_v2", head, _bytes(model), "greedy", f"v{name}0"),
                        chunksize=2,
                    )
                )
                opt = torch.optim.Adam(model.parameters(), lr=CFG["lr"])
                run.update(
                    model=_bytes(model), opt=opt.state_dict(), episodes=0, iteration=0, vals=[v],
                    best=v, best_model=_bytes(model), bc_val=v, stale=0,
                    bc_acc=accuracy(model, held), rng_state=rng.getstate(),
                )  # fmt: skip
                log(
                    {"stage": "bc", "run": name, "val": v, "heldout_acc": run["bc_acc"], "ref": ref}
                )
                save()
            model = MappoActorCritic(head)
            model.load_state_dict(torch.load(io.BytesIO(run["model"]), weights_only=True))
            opt = torch.optim.Adam(model.parameters(), lr=CFG["lr"])
            opt.load_state_dict(run["opt"])
            stop = False
            while run["episodes"] < CFG["max_episodes"] and left() > 150 and not stop:
                base = 100000 * seed + run["episodes"]
                w = _bytes(model)
                tasks = [
                    task(
                        f"t{base + j}",
                        base + j,
                        300000 + base + j,
                        f"PT17{seed}",
                        "mappo_v2",
                        head,
                        w,
                        "sample",
                        True,
                    )  # fmt: skip
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
                                "mappo_v2",
                                head,
                                _bytes(model),
                                "greedy",
                                f"v{name}{run['iteration']}",
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
                            "ref": ref,
                        }  # fmt: skip
                    )
                    if run["episodes"] >= CFG["min_episodes"] and run["stale"] >= CFG["patience"]:
                        run["stop_reason"] = "breaker"
                        stop = True
                run["model"], run["opt"], run["rng_state"] = (
                    _bytes(model),
                    opt.state_dict(),
                    rng.getstate(),
                )
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
                        "ref": ref,
                    }  # fmt: skip
                )
                save()
        if st["phase"] == "test" and left() > 150:
            from run_ambush_optimization import Store

            with open(OLD, "rb") as h:
                old = pickle.load(h)["runs"]
            pols = [
                ("planner_c215", "ambush_plus", None, None, None),
                ("teacher_v2", "mappo_v2", "mlp", None, "teacher"),
                ("pursuit", "pursuit", None, None, None),
                ("old_mlp", "mappo", "mlp", old["mlp_s1"]["best_model"], "greedy"),
                ("old_kan", "mappo", "kan", old["kan_s1"]["best_model"], "greedy"),
            ]
            for name, run in sorted(st["runs"].items()):
                pols.append(
                    (f"v2_{name}", "mappo_v2", name.split("_s")[0], run["best_model"], "greedy")
                )
            store = Store(package)
            if store.run(pool, test_tasks(pols), deadline - 60, episode):
                st["phase"] = "summary"
            save()
            log({"stage": "test_chunk", "done": len(store.rows)})
        if st["phase"] == "summary":
            from run_ambush_optimization import Store

            out = summarise(package, Store(package), st)
            st["phase"] = "done"
            save()
            log({"stage": "done", "primary": out["primary"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
