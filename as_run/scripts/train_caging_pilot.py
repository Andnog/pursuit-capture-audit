"""MARL pilot for certified coordinated caging (A-78, docs/MARL_DESIGN_EN.md). SUMO only.

Per arm (T: gate tokens; U: nearest-junction tokens) and training seed: initial network ->
BC from the cut heuristic -> BC + PPO. Reserved-scenario evaluation (greedy) of every checkpoint
and of the baselines (cut, individual, random over gates). Writes checkpoints, logs, eval rows and
a summary with the pre-registered acquisition test.
"""

from __future__ import annotations

import argparse
import io
import json
import multiprocessing as mp
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
SUMO = "/Library/Frameworks/Python.framework/Versions/3.10/bin/sumo"
MAPS = ["adelaide_cbd", "toronto_downtown", "washington_downtown"]
TEAM = 3
SPEED = 1.5


def _init_worker():
    import torch

    torch.set_num_threads(1)


def _paths():
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as h:
        out = {x["map_id"]: x["path"] for x in json.load(h)["maps"]}
    # A-92: controlled grids (assets/controlled, A-65) for the literature-like regime.
    controlled = os.path.join(ROOT, "assets", "controlled")
    if os.path.isdir(controlled):
        for name in os.listdir(controlled):
            if name.endswith(".net.xml"):
                out.setdefault(name[: -len(".net.xml")], os.path.join(controlled, name))
    # A-138: networks of the second held-out set (assets/osm_b). `setdefault` keeps every
    # existing identifier: a new file cannot replace an existing map.
    held_out_b = os.path.join(ROOT, "assets", "osm_b")
    if os.path.isdir(held_out_b):
        for name in sorted(os.listdir(held_out_b)):
            if name.endswith(".net.xml"):
                out.setdefault(name[: -len(".net.xml")], os.path.join(held_out_b, name))
    return out


_CACHE: dict = {}


def _net(map_id):
    from joint_interception.world.network import GraphNetwork

    if map_id not in _CACHE:
        _CACHE[map_id] = GraphNetwork.from_sumo(_paths()[map_id])
    return _CACHE[map_id]


def episode(args):
    """One SUMO episode, or {"failed": ...} if the simulation raised (counted, not fatal)."""
    try:
        return _episode(args)
    except Exception as error:  # noqa: BLE001 - one bad episode must not kill the pilot
        return {
            "failed": f"{type(error).__name__}: {str(error)[:160]}",
            "args": [str(a)[:40] for a in args if not isinstance(a, bytes)],
        }


def _episode(args):
    """One SUMO episode. mode: sample | greedy | cut | individual | random | demo."""
    import torch

    from joint_interception.domain.contracts import load_domain
    from joint_interception.rl.policy import TokenPolicy, decide, to_index
    from joint_interception.rl.rollout import CHASE, HOLD, cut_label, cut_policy, run_episode
    from joint_interception.simulator.evader import EvaderLevel
    from joint_interception.world.construction import make_scenario

    arm, weights, mode, map_id, salt, index, seed = args[:7]
    reward_mode = args[7] if len(args) > 7 else "certificate"  # A-86: "trap" for r04
    domain = load_domain()
    net = _net(map_id)
    sc = make_scenario(
        net, map_id, EvaderLevel.AVOIDANT, domain["team"]["pursuer_ids"][:TEAM], f"{salt}s{index}"
    )
    if len(sc.pursuer_starts) != TEAM:
        return None
    records: list[dict] = []
    model = None
    if weights is not None:
        model = TokenPolicy()
        model.load_state_dict(torch.load(io.BytesIO(weights), weights_only=True))
        model.eval()
    rng = random.Random(seed)
    cut = cut_policy()

    def policy(obs):
        if mode in ("sample", "greedy"):
            actions, rec = decide(model, obs, greedy=(mode == "greedy"))
            records.append(rec)
            return actions
        if mode == "demo":
            actions = cut(obs)
            recs = {}
            recs["T"] = decide(
                _DUMMY, obs, forced={v: to_index(obs[v], a) for v, a in actions.items()}
            )[1]
            u = dict(obs["_U"])
            u["_state"] = obs["_state"]
            forced_u = {}
            for v, a in actions.items():
                if a in (CHASE, HOLD):
                    forced_u[v] = to_index(u[v], a)
                else:
                    g = obs[v][a][0]
                    names = [x for x, _ in u[v]]
                    forced_u[v] = names.index(g) if g in names else to_index(u[v], CHASE)
            recs["U"] = decide(_DUMMY, u, forced=forced_u)[1]
            records.append(recs)
            return actions
        if mode == "cut":
            return cut(obs)
        if mode == "cut_label":
            return cut_label(obs)
        if mode in ("label_demo", "dagger"):
            # Labels from the stateless cut on the gate tokens, mapped to this arm's tokens.
            t_obs = obs if arm == "T" else obs["_T"]
            label = cut_label(t_obs)
            forced = {}
            for v, a in label.items():
                if a == CHASE:
                    forced[v] = to_index(obs[v], CHASE)
                else:
                    g = t_obs[v][a][0]
                    names = [x for x, _ in obs[v]]
                    forced[v] = names.index(g) if g in names else to_index(obs[v], CHASE)
            records.append(decide(_DUMMY, obs, forced=forced)[1])
            if mode == "label_demo":
                return {v: (forced[v] if forced[v] < len(obs[v]) else CHASE) for v in forced}
            return decide(model, obs, greedy=True)[0]
        pursuers = sorted(k for k in obs if not k.startswith("_"))
        if mode == "individual":
            return {
                v: (max(range(len(obs[v])), key=lambda i: obs[v][i][1][3]) if obs[v] else CHASE)
                for v in pursuers
            }
        return {
            v: (rng.randrange(len(obs[v])) if obs[v] and rng.random() < 0.8 else CHASE)
            for v in pursuers
        }

    global _DUMMY
    if mode in ("demo", "label_demo", "dagger") and _DUMMY is None:
        _DUMMY = TokenPolicy()
    run_arm = "T" if mode in ("demo", "cut", "cut_label", "individual", "random") else arm
    ep = run_episode(
        net,
        _paths()[map_id],
        sc,
        domain,
        SUMO,
        policy,
        speed_factor=SPEED,
        seed=seed,
        label=f"p{arm}{mode[:2]}{map_id[:3]}{index}_{seed}",
        arm=run_arm,
        extra_u=(mode == "demo"),
        extra_t=(mode in ("label_demo", "dagger") and arm != "T"),
        reward_mode=reward_mode,
    )
    rewards = [tr.reward for tr in ep.transitions]
    return {
        "map_id": map_id,
        "index": index,
        "seed": seed,
        "mode": mode,
        "arm": arm,
        "caged": ep.caged_at is not None,
        "caged_at": ep.caged_at,
        "trapped": ep.trapped_at is not None or ep.contact_capture,
        "trapped_at": ep.trapped_at,
        "reward": sum(rewards),
        "emergencies": ep.emergencies,
        "collided": ep.collided,
        "exited": ep.evader_exited,
        "contact": ep.contact_capture,
        "records": records,
        "rewards": rewards,
    }


_DUMMY = None
FAILURES: list = []


def _ok(results, log, stage):
    good = []
    for r in results:
        if r is None:
            continue
        if "failed" in r:
            FAILURES.append({"stage": stage, **r})
            if log:
                log({"stage": "episode_failed", "in": stage, **r})
            continue
        good.append(r)
    return good


def _bytes(model):
    import torch

    buf = io.BytesIO()
    torch.save(model.state_dict(), buf)
    return buf.getvalue()


def bc_train(model, demos, arm, epochs, log):
    import torch

    from joint_interception.rl.policy import joint_logp_entropy

    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    data = [rec for ep in demos for rec in ep["records"]]
    for e in range(epochs):
        random.shuffle(data)
        total = 0.0
        for i in range(0, len(data), 64):
            batch = data[i : i + 64]
            loss = -sum(joint_logp_entropy(model, r)[0] for r in batch) / len(batch)
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += loss.item() * len(batch)
        log({"stage": "bc", "arm": arm, "epoch": e, "nll": round(total / max(1, len(data)), 4)})


def ppo_update(model, opt, episodes, epochs=4, clip=0.2, vf=0.5, ent_coef=0.001):
    import torch

    from joint_interception.rl.policy import gae, joint_logp_entropy

    samples = []
    for ep in episodes:
        recs, rews = ep["records"], ep["rewards"]
        n = min(len(recs), len(rews))
        if n == 0:
            continue
        adv, ret = gae(rews[:n], [r["value"] for r in recs[:n]])
        for r, a, g in zip(recs[:n], adv, ret, strict=False):
            samples.append((r, a, g))
    if not samples:
        return {}
    advs = torch.tensor([s[1] for s in samples])
    mean, std = float(advs.mean()), float(advs.std()) + 1e-8
    stats = {}
    for _ in range(epochs):
        random.shuffle(samples)
        for i in range(0, len(samples), 256):
            batch = samples[i : i + 256]
            pl, vl, en = 0.0, 0.0, 0.0
            for r, a, g in batch:
                logp, ent = joint_logp_entropy(model, r)
                ratio = torch.exp(logp - r["logp"])
                an = (a - mean) / std
                pl = pl - torch.min(ratio * an, torch.clamp(ratio, 1 - clip, 1 + clip) * an)
                v = model.value(torch.from_numpy(r["ctx"])).squeeze()
                vl = vl + (v - g) ** 2
                en = en + ent
            k = len(batch)
            loss = (pl + vf * vl - ent_coef * en) / k
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 0.5)
            opt.step()
            stats = {
                "policy_loss": float(pl) / k,
                "value_loss": float(vl) / k,
                "entropy": float(en) / k,
            }
    return stats


def evaluate(pool, arm, weights, mode, scenarios, salt="PE"):
    tasks = [(arm, weights, mode, m, salt, i, 9500 + i) for m in MAPS for i in range(scenarios)]
    return _ok(pool.map(episode, tasks), None, "eval")


def bootstrap(xs, reps=10000, seed=7):
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(reps))
    return (
        round(sum(xs) / len(xs), 3),
        round(means[int(0.025 * reps)], 3),
        round(means[int(0.975 * reps) - 1], 3),
    )


def main() -> int:
    import torch

    from joint_interception.rl.policy import TokenPolicy

    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--arms", nargs="+", default=["T", "U"])
    parser.add_argument("--seeds", nargs="+", type=int, default=[1, 2])
    parser.add_argument("--demo-episodes", type=int, default=300)
    parser.add_argument("--bc-epochs", type=int, default=15)
    parser.add_argument("--ppo-episodes", type=int, default=8000)
    parser.add_argument("--batch", type=int, default=64)
    parser.add_argument("--eval-scenarios", type=int, default=20, help="per map")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument(
        "--eval-salt",
        default="PE",
        help="reserved evaluation scenarios; r03 uses fresh ones (PE was seen in A-80 checks)",
    )
    parser.add_argument("--skip-ppo", action="store_true", help="BC reproduction check only")
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(os.path.join(package, "checkpoints"), exist_ok=True)
    logf = open(os.path.join(package, "train_log.jsonl"), "a", encoding="utf-8")  # noqa: SIM115

    def log(entry):
        entry["wall"] = round(time.time(), 1)
        logf.write(json.dumps(entry) + "\n")
        logf.flush()
        print(json.dumps(entry), flush=True)

    ctx = mp.get_context("spawn")
    evals = []
    with ctx.Pool(args.workers, initializer=_init_worker) as pool:
        # A-80: demonstrations from the STATELESS cut, labelled in each arm's own tokens.
        demos = {}
        for arm in args.arms:
            demo_tasks = [
                (arm, None, "label_demo", MAPS[i % len(MAPS)], "PD", i, 7000 + i)
                for i in range(args.demo_episodes)
            ]
            demos[arm] = _ok(pool.map(episode, demo_tasks), log, "demos")
            log(
                {
                    "stage": "demos",
                    "arm": arm,
                    "episodes": len(demos[arm]),
                    "decisions": sum(len(d["records"]) for d in demos[arm]),
                    "cut_p_cage": round(
                        sum(d["caged"] for d in demos[arm]) / max(1, len(demos[arm])), 3
                    ),
                }
            )
        for mode in ("cut", "cut_label", "individual", "random"):
            rows = evaluate(pool, "T", None, mode, args.eval_scenarios, args.eval_salt)
            evals += [
                {k: v for k, v in r.items() if k not in ("records", "rewards")}
                | {"checkpoint": mode}
                for r in rows
            ]
            log(
                {
                    "stage": "eval",
                    "policy": mode,
                    "p_cage": round(sum(r["caged"] for r in rows) / len(rows), 3),
                }
            )
        for arm in args.arms:
            for seed in args.seeds:
                torch.manual_seed(seed)
                random.seed(seed)
                model = TokenPolicy()
                ckpts = {"initial": _bytes(model)}
                bc_train(model, demos[arm], arm, args.bc_epochs, log)
                ckpts["bc"] = _bytes(model)
                opt = torch.optim.Adam(model.parameters(), lr=args.lr)
                done, it = 0, 0
                while done < args.ppo_episodes and not args.skip_ppo:
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
                            "arm": arm,
                            "seed": seed,
                            "iteration": it,
                            "episodes": done,
                            "p_cage": round(sum(e["caged"] for e in eps) / max(1, len(eps)), 3),
                            "mean_reward": round(
                                sum(e["reward"] for e in eps) / max(1, len(eps)), 3
                            ),
                            **{k: round(v, 4) for k, v in stats.items()},
                        }
                    )
                ckpts["final"] = _bytes(model)
                for name, blob in ckpts.items():
                    with open(
                        os.path.join(package, "checkpoints", f"{arm}_seed{seed}_{name}.pt"), "wb"
                    ) as h:
                        h.write(blob)
                    rows = evaluate(pool, arm, blob, "greedy", args.eval_scenarios, args.eval_salt)
                    evals += [
                        {k: v for k, v in r.items() if k not in ("records", "rewards")}
                        | {"checkpoint": f"{arm}_seed{seed}_{name}"}
                        for r in rows
                    ]
                    log(
                        {
                            "stage": "eval",
                            "policy": f"{arm}_seed{seed}_{name}",
                            "p_cage": round(sum(r["caged"] for r in rows) / len(rows), 3),
                        }
                    )
    with open(os.path.join(package, "eval.jsonl"), "w", encoding="utf-8") as h:
        for r in evals:
            h.write(json.dumps(r) + "\n")

    def paired(a, b):
        ka = {(r["map_id"], r["index"]): r["caged"] for r in evals if r["checkpoint"] == a}
        kb = {(r["map_id"], r["index"]): r["caged"] for r in evals if r["checkpoint"] == b}
        diffs = [float(ka[k]) - float(kb[k]) for k in ka if k in kb]
        return bootstrap(diffs) if diffs else None

    summary = {"p_cage": {}, "acquisition": {}, "descriptive": {}}
    for c in sorted({r["checkpoint"] for r in evals}):
        rs = [r for r in evals if r["checkpoint"] == c]
        summary["p_cage"][c] = round(sum(r["caged"] for r in rs) / len(rs), 3)
    for arm in args.arms:
        for seed in args.seeds:
            base = f"{arm}_seed{seed}"
            d = paired(f"{base}_final", f"{base}_initial")
            summary["acquisition"][base] = {
                "final_minus_initial": d,
                "passes": d is not None and d[1] > 0,
                "final_minus_bc": paired(f"{base}_final", f"{base}_bc"),
                "final_minus_cut": paired(f"{base}_final", "cut"),
            }
    if {"T", "U"} <= set(args.arms):
        for seed in args.seeds:
            summary["descriptive"][f"T_minus_U_seed{seed}"] = paired(
                f"T_seed{seed}_final", f"U_seed{seed}_final"
            )
    summary["pilot_passes"] = all(v["passes"] for v in summary["acquisition"].values())
    summary["failed_episodes"] = len(FAILURES)
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(summary, h, indent=2)
    log({"stage": "summary", **summary})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
