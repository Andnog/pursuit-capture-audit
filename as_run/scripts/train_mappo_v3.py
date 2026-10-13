"""MAPPO v3 (A-133, pre-registered): the learning block repeated with a corrected implementation.

The fourth review found that the critic of the earlier studies was fed a state built after the
actions it was meant to judge (F4-1) and that sampling was not controlled by the declared seed
(F4-2). `native/mappo_ambush_v3.py` corrects both. This script repeats the fine-tuning from the
stored imitation checkpoints of A-116 (behaviour cloning uses neither the critic nor sampling):

- arm F: as A-116 with the corrected controller (MLP and KAN heads, two seeds);
- arm W: as F, preceded by a critic warm-up of 256 episodes (MLP head, two seeds);
- arm P: reward at the first body gap <= 5 m, fixed 2,048 episodes, no early stop (MLP, two seeds).

Test on fresh scenarios: PLB, pursuit, the imitation starts, and the selected and final policy of
every run; every episode is scored under OC and under the 5 m rules. Resumable chunks.
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

import train_mappo_v2 as v2  # noqa: E402
from run_endpoint_validation import DEVELOPMENT, TRAINING  # noqa: E402

V2_STATE = os.path.join(ROOT, "experiments", "20261004_mappo_v2_r01", "state.pkl")
ORDER = [
    "W_mlp_s1",
    "W_mlp_s2",
    "P_mlp_s1",
    "P_mlp_s2",
    "F_mlp_s1",
    "F_mlp_s2",
    "F_kan_s1",
    "F_kan_s2",
]
ARM_INDEX = {"F": 1, "W": 2, "P": 3}
HEAD_INDEX = {"mlp": 1, "kan": 2}
REWARD = {"F": "oc", "W": "oc", "P": "prox"}
CFG = dict(v2.CFG)
PROX_BUDGET = 2048
WARM_ITERS, WARM_EPOCHS, WARM_LR = 4, 10, 1e-3
SALT_VAL, SALT_TRAIN, SALT_TEST = "PV23", "PT23", "PE23"
FIELDS = ("d06", "prox_5m", "prox_5m_centre")


def parse(name):
    arm, head, s = name.split("_")
    return arm, head, int(s[1:])


def limits(arm):
    """(max episodes, min episodes before the breaker may stop, patience) of an arm."""
    if arm == "P":
        return PROX_BUDGET, PROX_BUDGET, 10**9
    return CFG["max_episodes"], CFG["min_episodes"], CFG["patience"]


def sampling_seed(arm, head, seed, episode_index, warm=False):
    """A distinct generator seed for every sampled episode of every run."""
    base = ARM_INDEX[arm] * 10**8 + HEAD_INDEX[head] * 10**7 + seed * 10**6
    return base + (5 * 10**5 if warm else 0) + episode_index


def returns(rewards, gamma: float = v2.GAMMA):
    """Discounted return from every step; the return after the last step is 0."""
    out, g = [0.0] * len(rewards), 0.0
    for t in reversed(range(len(rewards))):
        g = rewards[t] + gamma * g
        out[t] = g
    return out


def critic_fit(model, eps, rng, epochs=WARM_EPOCHS, lr=WARM_LR):
    """Fit the critic alone to Monte Carlo returns of the given episodes; the actor is untouched."""
    import numpy as np
    import torch

    pairs = []
    for ep in eps:
        if "failed" in ep or not ep["ticks"]:
            continue
        g = returns(v2.episode_rewards(len(ep["ticks"]), ep["success"], ep["collided"]))
        pairs += [(tick["global"], g[t]) for t, tick in enumerate(ep["ticks"])]
    if not pairs:
        return {"ticks": 0}
    opt = torch.optim.Adam(model.critic.parameters(), lr=lr)
    loss = None
    for _ in range(epochs):
        rng.shuffle(pairs)
        for k in range(0, len(pairs), 256):
            batch = pairs[k : k + 256]
            x = torch.from_numpy(np.stack([p[0] for p in batch]))
            y = torch.tensor([p[1] for p in batch], dtype=torch.float32)
            loss = ((model.value(x) - y) ** 2).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
    return {"ticks": len(pairs), "value_loss": float(loss.detach())}


# -- simulation ----------------------------------------------------------------------------------
def episode(args):
    from audit_cage_certificate import replay
    from run_test_confirmation import _capture_time
    from train_mappo_prox import first_proximity

    key, m, i, seed, salt, level, team, kind, head, weights, mode, rseed, keep, reward = args
    learner = None
    if kind == "mappo_v3":
        learner = {
            "params": v2._params(),
            "head": head,
            "weights": weights,
            "mode": mode,
            "seed": rseed,
        }
    elif kind == "ambush_plus":
        learner = {"params": v2._params()}
    try:
        ep, _ = replay(
            m, i, seed, salt, "T", None, "policy", 300.0, kind=kind, speed=1.0, level=level,
            team=team, learner=learner, reward_mode="certificate",
        )  # fmt: skip
    except Exception as error:  # noqa: BLE001
        return {"key": key, "failed": f"{type(error).__name__}: {str(error)[:100]}"}
    t_c = _capture_time(ep) if ep.contact_capture else None
    t_p, centre5 = first_proximity(ep)
    end = t_p if reward == "prox" else t_c
    ticks = v2.truncate_ticks(getattr(ep, "mappo_ticks", []), end) if keep else []
    for tick in ticks:
        tick.pop("global_post", None)  # diagnostics only; never reaches the update
    return {
        "key": key,
        "success": (t_p is not None) if reward == "prox" else bool(ep.contact_capture),
        "d06": bool(ep.contact_capture),
        "prox_5m": t_p is not None,
        "prox_5m_centre": bool(centre5),
        "collided": ep.collided,
        "ticks": ticks,
    }


def task(key, k, seed, salt, head, weights, mode, rseed, keep, reward):
    m, (level, team) = v2.combo(k)
    return (
        key,
        m,
        k,
        seed,
        salt,
        level,
        team,
        "mappo_v3",
        head,
        weights,
        mode,
        rseed,
        keep,
        reward,
    )


def val_tasks(head, weights, tag, reward):
    n = 16 * CFG["val_per_combo"]
    return [
        task(f"{tag}|{k}", k, 9500 + k, SALT_VAL, head, weights, "greedy", k, False, reward)
        for k in range(n)
    ]


def train_tasks(name, weights, first, n, warm=False):
    """Sampled episodes `first` .. `first + n - 1` of a run; each has its own sampling seed."""
    arm, head, seed = parse(name)
    salt = f"{SALT_TRAIN}{arm}{'w' if warm else ''}{seed}"
    out = []
    for j in range(n):
        k = 100000 * seed + first + j
        rseed = sampling_seed(arm, head, seed, first + j, warm)
        key = f"{name}|{'w' if warm else 't'}{first + j}"
        out.append(
            task(key, k, 300000 + k, salt, head, weights, "sample", rseed, True, REWARD[arm])
        )
    return out


def test_tasks(pols):
    out = []
    for m in TRAINING + DEVELOPMENT:
        for i in range(CFG["test_scenarios"]):
            for rep in range(CFG["test_reps"]):
                seed = 9500 + i + 100000 * rep
                for level in ("AVOIDANT", "RANDOM"):
                    for team in CFG["test_teams"]:
                        for pname, kind, head, w in pols:
                            key = f"test|{pname}|{m}|{i}|{seed}|{level}|{team}"
                            out.append(
                                (key, m, i, seed, SALT_TEST, level, team, kind, head, w)
                                + ("greedy", i, False, "oc")
                            )
    return out


def rate(rows, field="success"):
    good = [r for r in rows if "failed" not in r]
    return sum(r[field] for r in good) / max(1, len(good))


def policies(st):
    """Test policies and aliases. A selected checkpoint equal to its start is not run twice."""
    pols = [("planner_c215", "ambush_plus", None, None), ("pursuit", "pursuit", None, None)]
    alias = {}
    for name, w in sorted(st["starts"].items()):
        pols.append((f"start_{name}", "mappo_v3", name.split("_")[0], w))
    for name in ORDER:
        run = st["runs"][name]
        arm, head, seed = parse(name)
        start = f"start_{head}_s{seed}"
        if arm != "P":
            if run["best_model"] == st["starts"][f"{head}_s{seed}"]:
                alias[f"sel_{name}"] = start
            else:
                pols.append((f"sel_{name}", "mappo_v3", head, run["best_model"]))
        pols.append((f"final_{name}", "mappo_v3", head, run["model"]))
    return pols, alias


def summarise(package, rows, st, alias):
    cell = {}
    for k, r in rows.items():
        if not k.startswith("test|") or "failed" in r:
            continue
        _, p, m, i, _seed, level, team = k.split("|")
        for f in FIELDS:
            cell.setdefault((f, p, m, int(i), level, int(team)), []).append(float(r[f]))
    mean = {k: sum(v) / len(v) for k, v in cell.items()}
    for new, old in alias.items():
        for k in [k for k in mean if k[1] == old]:
            mean[(k[0], new) + k[2:]] = mean[k]

    def average(new, members):
        for k in [k for k in mean if k[1] == members[0]]:
            vals = [mean.get((k[0], mname) + k[2:]) for mname in members]
            if all(v is not None for v in vals):
                mean[(k[0], new) + k[2:]] = sum(vals) / len(vals)

    seeds = (1, 2)
    for head in ("mlp", "kan"):
        average(f"start_{head}", [f"start_{head}_s{s}" for s in seeds])
    for arm, head in (("W", "mlp"), ("F", "mlp"), ("F", "kan")):
        average(f"sel_{arm}_{head}", [f"sel_{arm}_{head}_s{s}" for s in seeds])
        average(f"final_{arm}_{head}", [f"final_{arm}_{head}_s{s}" for s in seeds])
    average("final_P_mlp", [f"final_P_mlp_s{s}" for s in seeds])
    names = sorted({k[1] for k in mean})

    def rate_of(f, p):
        xs = [v for k, v in mean.items() if k[0] == f and k[1] == p]
        return round(sum(xs) / len(xs), 4) if xs else None

    def fam(fn):
        out = {}
        for k in {k[2:] for k in mean}:
            v = fn(k)
            if v is not None:
                out.setdefault(k[:3], []).append(v)
        return out

    def diff(f, a, b):
        def fn(k):
            x, y = mean.get((f, a) + k), mean.get((f, b) + k)
            return None if x is None or y is None else x - y

        return v2.family_bootstrap(fam(fn))

    def gap_diff(a, b):
        def fn(k):
            vals = [mean.get((f, p) + k) for p in (a, b) for f in ("prox_5m", "d06")]
            if any(v is None for v in vals):
                return None
            return (vals[0] - vals[1]) - (vals[2] - vals[3])

        return v2.family_bootstrap(fam(fn))

    out = {
        "rates": {p: {f: rate_of(f, p) for f in FIELDS} for p in names},
        "selected_is_start": sorted(alias),
        "runs": {
            n: {
                k: r.get(k)
                for k in ("episodes", "stop_reason", "vals", "best", "start_val", "warm")
            }
            for n, r in st["runs"].items()
        },
        "failed": sum(1 for k, r in rows.items() if k.startswith("test|") and "failed" in r),
        "episodes": sum(1 for k in rows if k.startswith("test|")),
        "collisions": sum(
            bool(r.get("collided")) for k, r in rows.items() if k.startswith("test|")
        ),
    }
    p1 = diff("d06", "sel_W_mlp", "start_mlp")
    p2 = gap_diff("final_P_mlp", "start_mlp")
    out["primary_1_W_selected_minus_start_oc"] = {"family_95": p1, "passes": bool(p1 and p1[1] > 0)}
    out["primary_2_gap_P_final_minus_start"] = {"family_95": p2, "passes": bool(p2 and p2[1] > 0)}
    sec = {}
    for arm, head in (("W", "mlp"), ("F", "mlp"), ("F", "kan")):
        tag = f"{arm}_{head}"
        sec[f"d06:sel_{tag}_minus_start"] = diff("d06", f"sel_{tag}", f"start_{head}")
        sec[f"d06:final_{tag}_minus_start"] = diff("d06", f"final_{tag}", f"start_{head}")
        sec[f"d06:sel_{tag}_minus_plb"] = diff("d06", f"sel_{tag}", "planner_c215")
        sec[f"d06:final_{tag}_minus_plb"] = diff("d06", f"final_{tag}", "planner_c215")
    for name in ORDER:
        arm, head, seed = parse(name)
        sec[f"d06:final_{name}_minus_start"] = diff("d06", f"final_{name}", f"start_{head}_s{seed}")
    sec["d06:sel_W_mlp_minus_sel_F_mlp"] = diff("d06", "sel_W_mlp", "sel_F_mlp")
    sec["d06:final_W_mlp_minus_final_F_mlp"] = diff("d06", "final_W_mlp", "final_F_mlp")
    for head in ("mlp", "kan"):
        sec[f"d06:start_{head}_minus_plb"] = diff("d06", f"start_{head}", "planner_c215")
    for f in FIELDS:
        sec[f"{f}:final_P_mlp_minus_start"] = diff(f, "final_P_mlp", "start_mlp")
        sec[f"{f}:plb_minus_pursuit"] = diff(f, "planner_c215", "pursuit")
    sec["d06:final_P_mlp_minus_pursuit"] = diff("d06", "final_P_mlp", "pursuit")
    out["secondary"] = sec
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
    global PROX_BUDGET, WARM_ITERS  # noqa: PLW0603 - smoke configuration only
    if args.smoke:
        CFG.update(
            max_episodes=32, batch=16, val_every=1, val_per_combo=1, min_episodes=16, patience=1,
            test_scenarios=1, test_reps=1, test_teams=[3],
        )  # fmt: skip
        PROX_BUDGET, WARM_ITERS = 32, 1
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    deadline = time.time() + 60 * args.budget_min
    spath = os.path.join(package, "state.pkl")
    if os.path.exists(spath):
        with open(spath, "rb") as h:
            st = pickle.load(h)
    else:
        with open(V2_STATE, "rb") as h:
            old = pickle.load(h)["runs"]
        starts = {}
        for name, run in old.items():
            if run["best"] != run["bc_val"]:
                raise SystemExit(f"{name}: the stored A-116 checkpoint is not its imitation start")
            starts[name] = run["best_model"]
        st = {"phase": "runs", "runs": {}, "starts": starts}

    def save():
        with open(spath + ".tmp", "wb") as h:
            pickle.dump(st, h)
        os.replace(spath + ".tmp", spath)

    def log(e):
        e["wall"] = round(time.time(), 1)
        with open(os.path.join(package, "train_log.jsonl"), "a", encoding="utf-8") as h:
            h.write(json.dumps(e) + "\n")
        print(json.dumps(e)[:300], flush=True)

    def load(weights, head):
        model = MappoActorCritic(head)
        model.load_state_dict(torch.load(io.BytesIO(weights), weights_only=True))
        return model

    left = lambda: deadline - time.time()  # noqa: E731
    with mp.get_context("spawn").Pool(args.workers, initializer=v2._init) as pool:
        while st["phase"] == "runs" and left() > 150:
            pending = [r for r in ORDER if not st["runs"].get(r, {}).get("done")]
            if not pending:
                st["phase"] = "test"
                log({"stage": "runs_done"})
                save()
                break
            name = pending[0]
            arm, head, seed = parse(name)
            reward = REWARD[arm]
            cap, floor, patience = limits(arm)
            run = st["runs"].setdefault(name, {})
            rng = random.Random(1000 * ARM_INDEX[arm] + 10 * HEAD_INDEX[head] + seed)
            if "rng_state" in run:
                rng.setstate(run["rng_state"])
            if "model" not in run:
                w = st["starts"][f"{head}_s{seed}"]
                v = rate(pool.map(episode, val_tasks(head, w, f"v|{name}|0", reward), chunksize=2))
                opt = torch.optim.Adam(load(w, head).parameters(), lr=CFG["lr"])
                run.update(
                    model=w, opt=opt.state_dict(), episodes=0, iteration=0, vals=[v], best=v,
                    best_model=w, start_val=v, stale=0, rng_state=rng.getstate(), warm=0,
                )  # fmt: skip
                log({"stage": "start", "run": name, "val": v, "reward": reward})
                save()
            model = load(run["model"], head)
            while arm == "W" and run["warm"] < WARM_ITERS and left() > 150:
                tasks = train_tasks(
                    name, run["model"], run["warm"] * CFG["batch"], CFG["batch"], True
                )
                eps = pool.map(episode, tasks, chunksize=2)
                run.setdefault("warm_eps", []).extend(
                    {"ticks": e["ticks"], "success": e["success"], "collided": e["collided"]}
                    for e in eps
                    if "failed" not in e
                )
                run["warm"] += 1
                stats = {}
                if run["warm"] == WARM_ITERS:
                    stats = critic_fit(model, run.pop("warm_eps"), rng)
                    run["model"] = v2._bytes(model)
                    run["opt"] = torch.optim.Adam(model.parameters(), lr=CFG["lr"]).state_dict()
                run["rng_state"] = rng.getstate()
                log({"stage": "warmup", "run": name, "iteration": run["warm"], **stats})
                save()
            if arm == "W" and run["warm"] < WARM_ITERS:
                break
            model = load(run["model"], head)
            opt = torch.optim.Adam(model.parameters(), lr=CFG["lr"])
            opt.load_state_dict(run["opt"])
            stop = False
            while run["episodes"] < cap and left() > 150 and not stop:
                tasks = train_tasks(name, v2._bytes(model), run["episodes"], CFG["batch"])
                eps = pool.map(episode, tasks, chunksize=2)
                stats = v2.mappo_update(model, opt, eps, rng)
                run["episodes"] += CFG["batch"]
                run["iteration"] += 1
                log(
                    {
                        "stage": "mappo",
                        "run": name,
                        "iteration": run["iteration"],
                        "episodes": run["episodes"],
                        "success": round(rate(eps), 3),
                        "oc": round(rate(eps, "d06"), 3),
                        "prox": round(rate(eps, "prox_5m"), 3),
                        **{k: round(v, 4) for k, v in stats.items()},
                    }
                )
                if run["iteration"] % CFG["val_every"] == 0:
                    tag = f"v|{name}|{run['iteration']}"
                    v = rate(
                        pool.map(
                            episode, val_tasks(head, v2._bytes(model), tag, reward), chunksize=2
                        )
                    )
                    run["vals"].append(v)
                    sm = sum(run["vals"][-2:]) / len(run["vals"][-2:])
                    if sm >= run["best"] + CFG["min_delta"]:
                        run["best"], run["best_model"], run["stale"] = sm, v2._bytes(model), 0
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
                        }
                    )
                    if run["episodes"] >= floor and run["stale"] >= patience:
                        run["stop_reason"] = "breaker"
                        stop = True
                run["model"], run["opt"], run["rng_state"] = (
                    v2._bytes(model),
                    opt.state_dict(),
                    rng.getstate(),
                )
                save()
            if stop or run["episodes"] >= cap:
                run["done"] = True
                run.setdefault("stop_reason", "max_episodes")
                log(
                    {
                        "stage": "run_end",
                        "run": name,
                        "episodes": run["episodes"],
                        "reason": run["stop_reason"],
                        "best": run["best"],
                        "start_val": run["start_val"],
                        "vals": [round(x, 3) for x in run["vals"]],
                    }
                )
                save()
        if st["phase"] == "test" and left() > 150:
            from run_ambush_optimization import Store

            pols, alias = policies(st)
            st["alias"] = alias
            store = Store(package)
            if store.run(pool, test_tasks(pols), deadline - 60, episode):
                st["phase"] = "summary"
            save()
            log({"stage": "test_chunk", "done": len(store.rows)})
        if st["phase"] == "summary":
            from run_ambush_optimization import Store

            out = summarise(package, Store(package).rows, st, st["alias"])
            st["phase"] = "done"
            save()
            log(
                {
                    "stage": "done",
                    "p1": out["primary_1_W_selected_minus_start_oc"],
                    "p2": out["primary_2_gap_P_final_minus_start"],
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
