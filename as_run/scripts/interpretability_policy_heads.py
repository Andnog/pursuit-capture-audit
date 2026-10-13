"""A-113 Part 2: KAN vs MLP vs conditional-logit explanations of the learned MAPPO actors.

collect: PLB teacher-mode episodes on TRAINING cities (salt PI1); every agent decision is stored
(slot tokens, agent context, teacher choice). No training of the actors (A-105 checkpoints).
analyse: for the KAN actor, the MLP actor and a conditional logit distilled from the teacher:
- top-1 agreement with the teacher (held-out 30 %);
- permutation importance: share of decisions whose greedy choice changes when a feature is shuffled;
- the KAN's native attribution (first-layer edge amplitudes weighted by second-layer amplitudes);
- ranking agreement (Kendall tau); deletion faithfulness (top-3 features set to their median);
- partial-dependence shape agreement between the KAN and MLP actors.
"""

from __future__ import annotations

import argparse
import io
import itertools
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

A99 = os.path.join(ROOT, "experiments", "20261002_ambush_optimization_r01", "summary.json")
MAPPO = os.path.join(ROOT, "experiments", "20261002_mappo_r01", "state.pkl")
CITIES = ["adelaide_cbd", "toronto_downtown", "washington_downtown", "seattle_downtown"]
PER_EPISODE = 30


def collect_one(args):
    from audit_cage_certificate import replay

    m, i, level, team = args
    with open(A99, encoding="utf-8") as h:
        c215 = json.load(h)["final_params"]
    learner = {"params": c215, "head": "mlp", "weights": None, "mode": "teacher", "seed": i}
    try:
        ep, _ = replay(
            m, i, 9500 + i, "PI1", "T", None, "policy", 300.0, kind="mappo", speed=1.0,
            level=level, team=team, learner=learner, reward_mode="certificate",
        )  # fmt: skip
    except Exception as error:  # noqa: BLE001
        return {"failed": str(error)[:100]}
    recs = [a for tick in ep.mappo_ticks for a in tick["agents"] if len(a["tokens"]) > 2]
    rng = random.Random(f"{m}{i}{level}{team}")
    recs = rng.sample(recs, min(PER_EPISODE, len(recs)))
    return {
        "episode": (m, i, level, team),
        "decisions": [(r["tokens"], r["ctx"], int(r["teacher_idx"])) for r in recs],
    }


def collect(package, workers):
    from run_ambush_optimization import _init

    tasks = [
        (m, i, lv, t)
        for m in CITIES
        for i in range(10)
        for lv in ("AVOIDANT", "RANDOM")
        for t in (3, 5, 7)
    ]
    with mp.get_context("spawn").Pool(workers, initializer=_init) as pool:
        out = pool.map(collect_one, tasks, chunksize=1)
    with open(os.path.join(package, "decisions.pkl"), "wb") as h:
        pickle.dump(out, h)
    print(json.dumps({"episodes": len(out), "failed": sum("failed" in o for o in out)}))


def analyse(package):
    import numpy as np
    import torch
    from scipy.stats import kendalltau

    from joint_interception.rl.mappo_policy import AGENT_CTX, SLOT_FEATURES, MappoActorCritic

    feats = list(SLOT_FEATURES) + list(AGENT_CTX)
    with open(os.path.join(package, "decisions.pkl"), "rb") as h:
        eps = [e for e in pickle.load(h) if "failed" not in e]
    rng = random.Random(0)
    rng.shuffle(eps)
    cut = int(0.7 * len(eps))
    train = [d for e in eps[:cut] for d in e["decisions"]]
    test = [d for e in eps[cut:] for d in e["decisions"]]
    with open(MAPPO, "rb") as h:
        runs = pickle.load(h)["runs"]
    actors = {}
    for name, run in runs.items():
        head = name.split("_s")[0]
        model = MappoActorCritic(head)
        model.load_state_dict(torch.load(io.BytesIO(run["best_model"]), weights_only=True))
        model.eval()
        actors[head] = model

    def actor_scores(model):
        def score(toks, ctx):
            with torch.no_grad():
                t = torch.from_numpy(np.asarray(toks, dtype=np.float32))
                c = torch.from_numpy(np.asarray(ctx, dtype=np.float32))
                return model.logits(t, c).numpy()

        return score

    # Conditional logit on the slot features (the context is shared by every token, so a linear
    # term in it cannot change a choice), fitted to the teacher on the training split.
    w = torch.zeros(len(SLOT_FEATURES), requires_grad=True)
    opt = torch.optim.LBFGS([w], max_iter=200)
    tr_t = [torch.tensor(np.asarray(t, dtype=np.float32)) for t, _, _ in train]
    tr_y = [y for _, _, y in train]

    def closure():
        opt.zero_grad()
        loss = (
            sum(-torch.log_softmax(t @ w, 0)[y] for t, y in zip(tr_t, tr_y, strict=True))
            / len(tr_t)
            + 1e-3 * (w**2).sum()
        )
        loss.backward()
        return loss

    opt.step(closure)
    wl = w.detach().numpy()

    def logit_score(toks, ctx):
        return np.asarray(toks, dtype=np.float32) @ wl

    scorers = {
        "kan": actor_scores(actors["kan"]),
        "mlp": actor_scores(actors["mlp"]),
        "logit": logit_score,
    }

    def choices(score, data):
        return np.array([int(np.argmax(score(t, c))) for t, c, _ in data])

    res = {"features": feats, "n_train": len(train), "n_test": len(test), "models": {}}
    base = {k: choices(s, test) for k, s in scorers.items()}
    teacher = np.array([y for _, _, y in test])
    allt = np.concatenate([np.asarray(t, dtype=np.float32) for t, _, _ in test])
    allc = np.stack([np.asarray(c, dtype=np.float32) for _, c, _ in test])
    med_t, med_c = np.median(allt, 0), np.median(allc, 0)
    prng = np.random.default_rng(0)

    def perturbed(j, mode):
        """The test data with feature j shuffled across the dataset, or set to its median."""
        out = []
        if j < len(SLOT_FEATURES):
            col = allt[:, j].copy()
            if mode == "shuffle":
                col = prng.permutation(col)
            else:
                col[:] = med_t[j]
            k = 0
            for t, c, y in test:
                t2 = np.asarray(t, dtype=np.float32).copy()
                t2[:, j] = col[k : k + len(t2)]
                k += len(t2)
                out.append((t2, c, y))
        else:
            jj = j - len(SLOT_FEATURES)
            col = allc[:, jj].copy()
            col = prng.permutation(col) if mode == "shuffle" else np.full_like(col, med_c[jj])
            for (t, c, y), v in zip(test, col, strict=True):
                c2 = np.asarray(c, dtype=np.float32).copy()
                c2[jj] = v
                out.append((t, c2, y))
        return out

    def multi_median(js):
        """The test data with every feature in `js` set to its median."""
        out = []
        for t, c, y in test:
            t2 = np.asarray(t, dtype=np.float32).copy()
            c2 = np.asarray(c, dtype=np.float32).copy()
            for j in js:
                if j < len(SLOT_FEATURES):
                    t2[:, j] = med_t[j]
                else:
                    c2[j - len(SLOT_FEATURES)] = med_c[j - len(SLOT_FEATURES)]
            out.append((t2, c2, y))
        return out

    for name, score in scorers.items():
        t0 = time.time()
        perm = []
        for j in range(len(feats)):
            perm.append(
                float(
                    np.mean(
                        [
                            (choices(score, perturbed(j, "shuffle")) != base[name]).mean()
                            for _ in range(3)
                        ]
                    )
                )
            )
        res["models"][name] = {
            "agreement_with_teacher": round(float((base[name] == teacher).mean()), 4),
            "perm_importance": [round(p, 4) for p in perm],
            "seconds": round(time.time() - t0, 1),
        }

    # KAN native attribution: first-layer edge amplitudes, weighted by the second layer.
    kan = actors["kan"].actor
    l1, l2 = kan[0], kan[1]
    X = np.concatenate(
        [
            np.hstack(
                [
                    np.asarray(t, dtype=np.float32),
                    np.tile(np.asarray(c, dtype=np.float32), (len(t), 1)),
                ]
            )
            for t, c, _ in test
        ]
    )
    Xt = torch.from_numpy(X)
    with torch.no_grad():
        H = l1(Xt)
        amp2 = np.array(
            [float(l2.edge_function(o, 0, H[:, o]).abs().mean()) for o in range(H.shape[1])]
        )
        amp1 = np.array(
            [
                [float(l1.edge_function(i, o, Xt[:, i]).abs().mean()) for i in range(X.shape[1])]
                for o in range(H.shape[1])
            ]
        )
    native = (amp1 * amp2[:, None]).sum(0)
    res["models"]["kan"]["native_importance"] = [round(float(v), 4) for v in native]
    res["models"]["logit"]["coef_x_std"] = [
        round(float(abs(wl[j]) * allt[:, j].std()), 4) for j in range(len(SLOT_FEATURES))
    ]

    vec = {
        "kan_native": native,
        "kan_perm": res["models"]["kan"]["perm_importance"],
        "mlp_perm": res["models"]["mlp"]["perm_importance"],
    }
    slot_vec = {k: list(v)[: len(SLOT_FEATURES)] for k, v in vec.items()}
    slot_vec["logit_coef"] = res["models"]["logit"]["coef_x_std"]
    slot_vec["logit_perm"] = res["models"]["logit"]["perm_importance"][: len(SLOT_FEATURES)]
    res["ranking_tau_all_features"] = {
        f"{a}~{b}": round(float(kendalltau(vec[a], vec[b]).statistic), 3)
        for a, b in itertools.combinations(vec, 2)
    }
    res["ranking_tau_slot_features"] = {
        f"{a}~{b}": round(float(kendalltau(slot_vec[a], slot_vec[b]).statistic), 3)
        for a, b in itertools.combinations(slot_vec, 2)
    }
    res["top3"] = {k: [feats[i] for i in np.argsort(v)[::-1][:3]] for k, v in vec.items()}
    res["top3"]["logit_coef"] = [
        SLOT_FEATURES[i] for i in np.argsort(slot_vec["logit_coef"])[::-1][:3]
    ]

    # Deletion faithfulness: set an explanation's top-3 features to their median; share of the
    # model's own choices that change. Random-3 baseline (mean of 10 draws).
    dele = {}
    for model, explanations in (("kan", ("kan_native", "kan_perm")), ("mlp", ("mlp_perm",))):
        for ex in explanations:
            top = list(np.argsort(vec[ex])[::-1][:3])
            dele[f"{model}|{ex}"] = round(
                float((choices(scorers[model], multi_median(top)) != base[model]).mean()), 4
            )
        rnd = []
        r2 = random.Random(5)
        for _ in range(10):
            js = r2.sample(range(len(feats)), 3)
            rnd.append(float((choices(scorers[model], multi_median(js)) != base[model]).mean()))
        dele[f"{model}|random3"] = round(float(np.mean(rnd)), 4)
    res["deletion_choice_change"] = dele

    # Partial-dependence shape agreement (KAN vs MLP actor) for the slot features.
    pd = {}
    for j, f in enumerate(SLOT_FEATURES):
        vals = np.unique(allt[:, j])
        grid = vals if len(vals) <= 9 else np.quantile(allt[:, j], np.linspace(0.02, 0.98, 9))
        curves = {}
        for name in ("kan", "mlp"):
            model = actors[name]
            cur = []
            for g in grid:
                Xg = X.copy()
                Xg[:, j] = g
                with torch.no_grad():
                    cur.append(float(model.actor(torch.from_numpy(Xg)).mean()))
            curves[name] = cur
        a, b = np.array(curves["kan"]), np.array(curves["mlp"])
        r = None if a.std() < 1e-9 or b.std() < 1e-9 else round(float(np.corrcoef(a, b)[0, 1]), 3)
        pd[f] = {
            "grid": [round(float(g), 3) for g in grid],
            "kan": curves["kan"],
            "mlp": curves["mlp"],
            "r": r,
        }
    res["pd_shape_agreement"] = pd
    with open(
        os.path.join(package, "INTERPRETABILITY_POLICY_HEADS.json"), "w", encoding="utf-8"
    ) as h:
        json.dump(res, h, indent=2)
    print(
        json.dumps(
            {
                k: res[k]
                for k in (
                    "ranking_tau_all_features",
                    "ranking_tau_slot_features",
                    "top3",
                    "deletion_choice_change",
                )
            },
            indent=1,
        )
    )
    print({k: v["agreement_with_teacher"] for k, v in res["models"].items()})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--phase", choices=["collect", "analyse"], required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    if args.phase == "collect":
        collect(package, args.workers)
    else:
        analyse(package)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
