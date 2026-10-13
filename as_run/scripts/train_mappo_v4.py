"""MAPPO v4 (A-139, pre-registered): the learning block repeated with a transition contract.

The fifth review found three things in the training loop of every earlier learning study
(`train_mappo_v2.py`, `train_mappo_prox.py`, `train_mappo_v3.py`, all kept unchanged):

- F5-1: the decision taken at the end of an episode (at the horizon, or at the capture instant when
  it fell on a decision tick) was trained and received the terminal reward or a time cost, although
  it had no future inside the episode; and a collision anywhere in the simulated episode penalised
  the trained prefix even when it happened after the cut;
- F5-2: the capture instant came from a helper that did not reset a run when a pursuer was absent;
- F5-6: the log could not reconstruct how many attempts were valid and used, nor their events.

This script repeats the design of `train_mappo_v3.py` (same arms, heads, seeds, hyperparameters,
imitation starts, controller, training and validation scenarios) with:

- transitions built by `joint_interception.rl.transitions.build_transitions`: a decision is trained
  only if it precedes the end of the trained interval, the objective reward goes to the transition
  that led to it, the time cost is proportional to the duration, and the collision penalty is
  applied once, where the first collision inside the trained interval happened;
- the capture instant from `joint_interception.evaluation.capture_time.earliest_capture`;
- a ledger with one row per attempted episode and counts per update, and the weights of every
  iteration stored, so that any training batch can be replayed.

Every row also records what the earlier contract would have done with the same episode, which
measures the incidence of the defects on this distribution. Test on fresh scenarios. Resumable.
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
import train_mappo_v3 as v3  # noqa: E402
from run_endpoint_validation import DEVELOPMENT, TRAINING  # noqa: E402

ORDER = list(v3.ORDER)
ARM_INDEX, HEAD_INDEX, REWARD = dict(v3.ARM_INDEX), dict(v3.HEAD_INDEX), dict(v3.REWARD)
CFG = dict(v2.CFG)
PROX_BUDGET = 2048
WARM_ITERS, WARM_EPOCHS, WARM_LR = 4, 10, 1e-3
# Training and validation scenarios are those of MAPPO-v3; the test scenarios are new.
SALTS = {"train": "PT23", "val": "PV23", "test": "PE24"}
SMOKE_SALTS = {"train": "SMT24", "val": "SMV24", "test": "SME24"}
DECIDE_S = 3.0
HORIZON_S = 300.0
STEP_S = 0.1
FIELDS = v3.FIELDS
parse, sampling_seed = v3.parse, v3.sampling_seed
LEDGER_DROP = ("ticks", "rewards")


def limits(arm):
    """(max attempts, min attempts before the breaker may stop, patience) of an arm."""
    if arm == "P":
        return PROX_BUDGET, PROX_BUDGET, 10**9
    return CFG["max_episodes"], CFG["min_episodes"], CFG["patience"]


# -- pure functions (unit tested) ----------------------------------------------------------------
def measure(ep, reward, keep, team):
    """Outcome, transitions and ledger fields of one simulated episode.

    Returns {"failed": ...} when the trace cannot support a capture instant (irregular cadence,
    invalid values) or when the extractor and the engine's judge disagree: such an episode is
    unresolved evidence and is excluded from every rate and from training, and it is counted.
    """
    from joint_interception.domain.contracts import CaptureParameters
    from joint_interception.evaluation.capture_time import (
        TraceIntegrityError,
        absent_frames,
        earliest_capture,
    )
    from joint_interception.rl.transitions import TransitionError, build_transitions
    from run_test_confirmation import _capture_time
    from train_mappo_prox import first_proximity

    params = CaptureParameters.from_domain()
    try:
        cap = earliest_capture(ep.trace, "e1", params, STEP_S)
    except TraceIntegrityError as error:
        return {"failed": f"invalid_trace: {str(error)[:100]}"}
    if (cap is not None) != bool(ep.contact_capture):
        return {"failed": "judge_and_extractor_disagree"}
    t_c = None if cap is None else round(cap.time_s, 1)
    t_p, centre5 = first_proximity(ep)
    event = t_p if reward == "prox" else t_c
    if ep.evader_exited:
        end_reason = "evader_exit"
    else:
        end_reason = "horizon" if ep.end_s >= HORIZON_S - 1e-6 else "trace_end"
    ticks = list(getattr(ep, "mappo_ticks", []))
    collisions = sorted({float(c["t"]) for c in getattr(ep, "collision_events", [])})
    try:
        ts = build_transitions(
            [t["t"] for t in ticks],
            trace_end_s=ep.end_s,
            event_s=event,
            collision_times=collisions,
            trace_end_reason=end_reason,
            decide_s=DECIDE_S,
            step_cost=v2.STEP_COST,
        )
    except TransitionError as error:
        return {"failed": f"invalid_times: {str(error)[:100]}"}
    # What the earlier contract did with the same episode (diagnostics; never used to train).
    legacy_t_c = _capture_time(ep) if ep.contact_capture else None
    legacy_kept = v2.truncate_ticks(ticks, t_p if reward == "prox" else legacy_t_c)
    absent = absent_frames(ep.trace, ["e1", *[f"p{k}" for k in range(1, team + 1)]])
    out = {
        "success": event is not None,
        "d06": bool(ep.contact_capture),
        "prox_5m": t_p is not None,
        "prox_5m_centre": bool(centre5),
        "capture_s": t_c,
        "capture_pursuer": None if cap is None else cap.pursuer_id,
        "proximity_s": t_p,
        "end_s": ep.end_s,
        "end_reason": ts.end_reason,
        "collided": bool(ep.collided),
        "collision_times": collisions[:50],
        "collision_in_interval": bool(ts.collisions_in_interval),
        "collisions_outside": len(ts.collisions_outside),
        "recorded_ticks": ts.recorded_ticks,
        "transitions": len(ts.transitions),
        "terminal_observation_ticks": len(ts.terminal_observation_ticks),
        "exclusion": ts.exclusion,
        "reward_sum": round(sum(ts.rewards), 6),
        "absent_frames": {v: a["absent"] for v, a in absent.items() if a["absent"]},
        "inner_gap_frames": sum(a["inner_gap_frames"] for a in absent.values()),
        "legacy": {
            "capture_s": legacy_t_c,
            "ticks": len(legacy_kept),
            "trained_decisions_without_future": len(legacy_kept) - len(ts.transitions),
            "capture_on_a_tick": bool(
                reward != "prox"
                and legacy_t_c is not None
                and any(abs(t["t"] - legacy_t_c) < 1e-9 for t in ticks)
            ),
            "penalised_a_collision_outside_the_interval": bool(ep.collided)
            and not ts.collisions_in_interval,
        },
    }
    if keep:
        kept = []
        for k in ts.ticks:
            tick = dict(ticks[k])
            tick.pop("global_post", None)  # diagnostics only; never reaches the update
            kept.append(tick)
        out["ticks"], out["rewards"] = kept, ts.rewards
    return out


def usable(ep):
    return "failed" not in ep and bool(ep.get("ticks"))


def batch_counts(eps):
    """Denominators and events of one batch of attempts."""
    valid = [e for e in eps if "failed" not in e]
    used = [e for e in valid if usable(e)]
    excluded: dict[str, int] = {}
    for e in valid:
        if not usable(e):
            reason = e.get("exclusion") or "no_decision_recorded"
            excluded[reason] = excluded.get(reason, 0) + 1
    return {
        "attempted": len(eps),
        "failed": len(eps) - len(valid),
        "valid": len(valid),
        "used": len(used),
        "excluded": excluded,
        "transitions": sum(len(e["ticks"]) for e in used),
        "agent_decisions": sum(len(t["agents"]) for e in used for t in e["ticks"]),
        "recorded_ticks": sum(e["recorded_ticks"] for e in valid),
        "terminal_observation_ticks": sum(e["terminal_observation_ticks"] for e in valid),
        "success": sum(bool(e["success"]) for e in valid),
        "d06": sum(bool(e["d06"]) for e in valid),
        "prox_5m": sum(bool(e["prox_5m"]) for e in valid),
        "end_reasons": {
            r: sum(e["end_reason"] == r for e in valid)
            for r in sorted({e["end_reason"] for e in valid})
        },
        "collided": sum(bool(e["collided"]) for e in valid),
        "collision_in_interval": sum(bool(e["collision_in_interval"]) for e in valid),
        "inner_gap_frames": sum(e["inner_gap_frames"] for e in valid),
        "legacy_trained_decisions_without_future": sum(
            e["legacy"]["trained_decisions_without_future"] for e in valid
        ),
        "legacy_episodes_with_such_a_decision": sum(
            e["legacy"]["trained_decisions_without_future"] > 0 for e in valid
        ),
        "legacy_capture_on_a_tick": sum(e["legacy"]["capture_on_a_tick"] for e in valid),
        "legacy_penalised_collision_outside": sum(
            e["legacy"]["penalised_a_collision_outside_the_interval"] for e in valid
        ),
        "legacy_capture_instant_differs": sum(
            e["legacy"]["capture_s"] != e["capture_s"] for e in valid if e["d06"]
        ),
    }


def ledger_rows(eps, training=True, **context):
    """One ledger row per attempt: the episode row without its tensors. For training attempts,
    `included` says whether the episode entered the update."""
    out = []
    for e in eps:
        row = {k: v for k, v in e.items() if k not in LEDGER_DROP}
        row.update(context)
        row["status"] = "failed" if "failed" in e else "ok"
        if training:
            row["included"] = usable(e)
        out.append(row)
    return out


INTEGRITY_KEYS = (
    "attempted",
    "failed",
    "valid",
    "d06",
    "prox_5m",
    "end_reasons",
    "collided",
    "inner_gap_frames",
    "legacy_capture_instant_differs",
)


def critic_fit(model, eps, rng, epochs=None, lr=None):
    """Fit the critic alone to Monte Carlo returns of the given episodes; the actor is untouched."""
    import numpy as np
    import torch

    from joint_interception.rl.transitions import discounted_returns

    epochs = WARM_EPOCHS if epochs is None else epochs
    lr = WARM_LR if lr is None else lr
    pairs = []
    for ep in eps:
        if not usable(ep):
            continue
        g = discounted_returns(ep["rewards"], v2.GAMMA)
        pairs += [(tick["global"], g[t]) for t, tick in enumerate(ep["ticks"])]
    if not pairs:
        return {"transitions": 0}
    opt = torch.optim.Adam(model.critic.parameters(), lr=lr)
    total, n = 0.0, 0
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
            total, n = total + float(loss.detach()), n + 1
    return {"transitions": len(pairs), "value_loss_mean": total / n, "minibatches": n}


def mappo_update(model, opt, eps, rng, epochs=4, clip=0.2):
    """The PPO update of `train_mappo_v2.mappo_update`, on transitions.

    Differences: rewards come from the transition contract (one per trained decision), and the
    statistics are means over every minibatch of the update, not the values of the last one.
    """
    import numpy as np
    import torch

    from joint_interception.rl.transitions import gae

    samples, vsamples = [], []
    for ep in eps:
        if not usable(ep):
            continue
        ticks = ep["ticks"]
        g = torch.from_numpy(np.stack([t["global"] for t in ticks]))
        with torch.no_grad():
            vals = model.value(g).tolist()
        adv = gae(ep["rewards"], vals, v2.GAMMA, v2.LAM)
        for t, tick in enumerate(ticks):
            vsamples.append((tick["global"], adv[t] + vals[t]))
            for a in tick["agents"]:
                samples.append((a, adv[t]))
    if not samples:
        return {"minibatches": 0}
    advs = torch.tensor([s[1] for s in samples])
    mean, std = float(advs.mean()), float(advs.std()) + 1e-8
    sums, n = {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}, 0
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
                pl = pl - v2.surrogate(ratio, (ad - mean) / std, clip)
                en = en + dist.entropy()
            gb = torch.from_numpy(np.stack([v[0] for v in vb]))
            rt = torch.tensor([v[1] for v in vb], dtype=torch.float32)
            vl = ((model.value(gb) - rt) ** 2).mean()
            loss = pl / len(batch) + 0.5 * vl - CFG["ent_coef"] * en / len(batch)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 0.5)
            opt.step()
            sums["policy_loss"] += float(pl.detach()) / len(batch)
            sums["value_loss"] += float(vl.detach())
            sums["entropy"] += float(en.detach()) / len(batch)
            n += 1
    return {**{k: v / n for k, v in sums.items()}, "minibatches": n}


def rate(rows, field="success"):
    """(successes, valid episodes) of a set of attempts."""
    good = [r for r in rows if "failed" not in r]
    return sum(bool(r[field]) for r in good), len(good)


def frac(pair):
    return pair[0] / max(1, pair[1])


# -- simulation ----------------------------------------------------------------------------------
def episode(args):
    from audit_cage_certificate import replay

    key, m, i, seed, salt, level, team, kind, head, weights, mode, rseed, keep, reward = args
    row = {
        "key": key,
        "map": m,
        "scenario": i,
        "sumo_seed": seed,
        "salt": salt,
        "level": level,
        "team": team,
        "kind": kind,
        "mode": mode,
        "sampling_seed": rseed,
        "reward": reward,
    }
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
            m, i, seed, salt, "T", None, "policy", HORIZON_S, kind=kind, speed=1.0, level=level,
            team=team, learner=learner, reward_mode="certificate",
        )  # fmt: skip
    except Exception as error:  # noqa: BLE001
        row["failed"] = f"{type(error).__name__}: {str(error)[:100]}"
        return row
    row.update(measure(ep, reward, keep, team))
    return row


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


def val_tasks(head, weights, tag, reward, salts):
    n = 16 * CFG["val_per_combo"]
    return [
        task(f"{tag}|{k}", k, 9500 + k, salts["val"], head, weights, "greedy", k, False, reward)
        for k in range(n)
    ]


def train_tasks(name, weights, first, n, salts, warm=False):
    """Sampled episodes `first` .. `first + n - 1` of a run: the scenarios, SUMO seeds and
    sampling seeds of `train_mappo_v3.train_tasks`, so the first batch of a run is the same set
    of episodes that MAPPO-v3 sampled."""
    arm, head, seed = parse(name)
    salt = f"{salts['train']}{arm}{'w' if warm else ''}{seed}"
    out = []
    for j in range(n):
        k = 100000 * seed + first + j
        rseed = sampling_seed(arm, head, seed, first + j, warm)
        key = f"{name}|{'w' if warm else 't'}{first + j}"
        out.append(
            task(key, k, 300000 + k, salt, head, weights, "sample", rseed, True, REWARD[arm])
        )
    return out


def test_tasks(pols, salts):
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
                                (key, m, i, seed, salts["test"], level, team, kind, head, w)
                                + ("greedy", i, False, "oc")
                            )
    return out


def ledger_summary(package):
    """Aggregate the training ledger: denominators, exclusions, terminal events, timed collisions
    and the incidence of what the earlier contract would have done."""
    path = os.path.join(package, "train_ledger.jsonl")
    # A chunk stopped between writing a batch and saving its state repeats that batch on
    # resumption, with the same weights and seeds: keep the last copy of every attempt.
    last: dict[tuple, dict] = {}
    with open(path, encoding="utf-8") as h:
        for x in h:
            r = json.loads(x)
            last[(r["run"], r["phase"], r["key"])] = r
    by_run: dict[str, list] = {}
    for (run, phase, _), r in last.items():
        by_run.setdefault(f"{run}|{phase}", []).append(r)
    out = {}
    for key, rows in sorted(by_run.items()):
        valid = [r for r in rows if r["status"] == "ok"]
        captured = [r for r in valid if r["d06"]]
        out[key] = {
            "attempted": len(rows),
            "failed": len(rows) - len(valid),
            "failure_reasons": _count(r["failed"].split(":")[0] for r in rows if "failed" in r),
            "valid": len(valid),
            "used": sum(r["included"] for r in valid),
            "excluded": _count(
                r.get("exclusion") or "no_decision_recorded" for r in valid if not r["included"]
            ),
            "transitions_used": sum(r["transitions"] for r in valid if r["included"]),
            "recorded_ticks": sum(r["recorded_ticks"] for r in valid),
            "terminal_observation_ticks": sum(r["terminal_observation_ticks"] for r in valid),
            "end_reasons": _count(r["end_reason"] for r in valid),
            "captured_oc": len(captured),
            "proximity": sum(r["prox_5m"] for r in valid),
            "episodes_with_a_collision": sum(r["collided"] for r in valid),
            "collision_inside_the_trained_interval": sum(r["collision_in_interval"] for r in valid),
            "collision_only_outside": sum(
                r["collided"] and not r["collision_in_interval"] for r in valid
            ),
            "inner_gap_frames": sum(r["inner_gap_frames"] for r in valid),
            "legacy": {
                "episodes_with_a_trained_decision_without_future": sum(
                    r["legacy"]["trained_decisions_without_future"] > 0 for r in valid
                ),
                "trained_decisions_without_future": sum(
                    r["legacy"]["trained_decisions_without_future"] for r in valid
                ),
                "captures_on_a_decision_tick": sum(r["legacy"]["capture_on_a_tick"] for r in valid),
                "episodes_penalised_for_a_collision_outside": sum(
                    r["legacy"]["penalised_a_collision_outside_the_interval"] for r in valid
                ),
                "capture_instant_differs_from_corrected": sum(
                    r["legacy"]["capture_s"] != r["capture_s"] for r in captured
                ),
            },
        }
    return out


def _count(values):
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))


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
    salts = SALTS
    if args.smoke:
        CFG.update(
            max_episodes=32, batch=16, val_every=1, val_per_combo=1, min_episodes=16, patience=1,
            test_scenarios=1, test_reps=1, test_teams=[3],
        )  # fmt: skip
        PROX_BUDGET, WARM_ITERS = 32, 1
        salts = SMOKE_SALTS  # a smoke run never touches a registered scenario
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    deadline = time.time() + 60 * args.budget_min
    spath = os.path.join(package, "state.pkl")
    if os.path.exists(spath):
        with open(spath, "rb") as h:
            st = pickle.load(h)
        if st["salts"] != salts:
            raise SystemExit("this package was started with other salts")
    else:
        with open(v3.V2_STATE, "rb") as h:
            old = pickle.load(h)["runs"]
        starts = {}
        for name, run in old.items():
            if run["best"] != run["bc_val"]:
                raise SystemExit(f"{name}: the stored A-116 checkpoint is not its imitation start")
            starts[name] = run["best_model"]
        st = {"phase": "runs", "runs": {}, "starts": starts, "salts": dict(salts), "history": {}}

    def save():
        with open(spath + ".tmp", "wb") as h:
            pickle.dump(st, h)
        os.replace(spath + ".tmp", spath)

    def append(name, rows):
        with open(os.path.join(package, name), "a", encoding="utf-8") as h:
            for r in rows:
                h.write(json.dumps(r) + "\n")

    def log(e):
        e["wall"] = round(time.time(), 1)
        append("train_log.jsonl", [e])
        print(json.dumps(e)[:300], flush=True)

    def load(weights, head):
        model = MappoActorCritic(head)
        model.load_state_dict(torch.load(io.BytesIO(weights), weights_only=True))
        return model

    def validate(pool, name, head, weights, iteration, reward):
        rows = pool.map(
            episode, val_tasks(head, weights, f"v|{name}|{iteration}", reward, salts), chunksize=2
        )
        append(
            "validation_ledger.jsonl",
            ledger_rows(rows, training=False, run=name, iteration=iteration),
        )
        return rate(rows)

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
            history = st["history"].setdefault(name, {})
            rng = random.Random(1000 * ARM_INDEX[arm] + 10 * HEAD_INDEX[head] + seed)
            if "rng_state" in run:
                rng.setstate(run["rng_state"])
            if "model" not in run:
                w = st["starts"][f"{head}_s{seed}"]
                pair = validate(pool, name, head, w, 0, reward)
                opt = torch.optim.Adam(load(w, head).parameters(), lr=CFG["lr"])
                run.update(
                    model=w, opt=opt.state_dict(), episodes=0, iteration=0, vals=[frac(pair)],
                    val_counts=[pair], best=frac(pair), best_model=w, start_val=frac(pair),
                    stale=0, rng_state=rng.getstate(), warm=0, valid=0, used=0, transitions=0,
                )  # fmt: skip
                history[0] = w
                log({"stage": "start", "run": name, "val": pair, "reward": reward})
                save()
            model = load(run["model"], head)
            while arm == "W" and run["warm"] < WARM_ITERS and left() > 150:
                tasks = train_tasks(
                    name, run["model"], run["warm"] * CFG["batch"], CFG["batch"], salts, True
                )
                eps = pool.map(episode, tasks, chunksize=2)
                append(
                    "train_ledger.jsonl",
                    ledger_rows(eps, run=name, phase="warmup", iteration=run["warm"] + 1),
                )
                run.setdefault("warm_eps", []).extend(
                    {"ticks": e["ticks"], "rewards": e["rewards"]} for e in eps if usable(e)
                )
                run["warm"] += 1
                stats = {}
                if run["warm"] == WARM_ITERS:
                    stats = critic_fit(model, run.pop("warm_eps"), rng)
                    run["model"] = v2._bytes(model)
                    run["opt"] = torch.optim.Adam(model.parameters(), lr=CFG["lr"]).state_dict()
                    history[0] = run["model"]  # weights that sample the first batch
                run["rng_state"] = rng.getstate()
                log(
                    {
                        "stage": "warmup",
                        "run": name,
                        "iteration": run["warm"],
                        "counts": batch_counts(eps),
                        **stats,
                    }
                )
                save()
            if arm == "W" and run["warm"] < WARM_ITERS:
                break
            model = load(run["model"], head)
            opt = torch.optim.Adam(model.parameters(), lr=CFG["lr"])
            opt.load_state_dict(run["opt"])
            stop = False
            while run["episodes"] < cap and left() > 150 and not stop:
                tasks = train_tasks(name, v2._bytes(model), run["episodes"], CFG["batch"], salts)
                eps = pool.map(episode, tasks, chunksize=2)
                counts = batch_counts(eps)
                stats = mappo_update(model, opt, eps, rng)
                run["episodes"] += CFG["batch"]  # attempts; valid and used are counted beside it
                run["valid"] += counts["valid"]
                run["used"] += counts["used"]
                run["transitions"] += counts["transitions"]
                run["iteration"] += 1
                append(
                    "train_ledger.jsonl",
                    ledger_rows(eps, run=name, phase="train", iteration=run["iteration"]),
                )
                log(
                    {
                        "stage": "mappo",
                        "run": name,
                        "iteration": run["iteration"],
                        "attempts": run["episodes"],
                        "counts": counts,
                        **stats,
                    }
                )
                if run["iteration"] % CFG["val_every"] == 0:
                    pair = validate(pool, name, head, v2._bytes(model), run["iteration"], reward)
                    v = frac(pair)
                    run["vals"].append(v)
                    run["val_counts"].append(pair)
                    sm = sum(run["vals"][-2:]) / len(run["vals"][-2:])
                    if sm >= run["best"] + CFG["min_delta"]:
                        run["best"], run["best_model"], run["stale"] = sm, v2._bytes(model), 0
                    else:
                        run["stale"] += 1
                    log(
                        {
                            "stage": "validation",
                            "run": name,
                            "attempts": run["episodes"],
                            "val": pair,
                            "smoothed": sm,
                            "best": run["best"],
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
                history[run["iteration"]] = run["model"]
                save()
            if stop or run["episodes"] >= cap:
                run["done"] = True
                run.setdefault("stop_reason", "max_episodes")
                log(
                    {
                        "stage": "run_end",
                        "run": name,
                        "attempts": run["episodes"],
                        "valid": run["valid"],
                        "used": run["used"],
                        "transitions": run["transitions"],
                        "reason": run["stop_reason"],
                        "best": run["best"],
                        "start_val": run["start_val"],
                        "vals": run["val_counts"],
                    }
                )
                save()
        if st["phase"] == "test" and left() > 150:
            from run_ambush_optimization import Store

            pols, alias = v3.policies(st)
            st["alias"] = alias
            store = Store(package)
            if store.run(pool, test_tasks(pols, salts), deadline - 60, episode):
                st["phase"] = "summary"
            save()
            log({"stage": "test_chunk", "done": len(store.rows)})
        if st["phase"] == "summary":
            from run_ambush_optimization import Store

            rows = Store(package).rows
            out = v3.summarise(package, rows, st, st["alias"])
            ledger = ledger_summary(package)
            with open(os.path.join(package, "ledger_summary.json"), "w", encoding="utf-8") as h:
                json.dump(ledger, h, indent=2)
            test_rows = [r for k, r in rows.items() if k.startswith("test|")]
            with open(os.path.join(package, "test_integrity.json"), "w", encoding="utf-8") as h:
                json.dump(
                    {
                        "failure_reasons": _count(
                            r["failed"].split(":")[0] for r in test_rows if "failed" in r
                        ),
                        "counts": {
                            k: v for k, v in batch_counts(test_rows).items() if k in INTEGRITY_KEYS
                        },
                    },
                    h,
                    indent=2,
                )
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
