"""Interpretable capture law with a reference KAN (pykan) (A-104, descriptive, post hoc).

Data: per-scenario D06 capture rate (mean over SUMO seeds) of the optimised ambush planner `c2_15`
from the sealed A-99 test (teams 3/5/7, pursuers 1.0x) and the A-101 r02 test (teams 3/5,
pursuers 1.0/1.1/1.2x; team 7 at 1.0x). Features per scenario come from the frozen scenario
generator and the networks:
- team size, evader avoidant (1) or random (0), pursuer speed factor;
- free-flow time of the nearest and of the mean pursuer to the evader's start (s);
- lanes to close at the evader's first junction;
- the city's median lanes to close, share of junctions closable by 3, multi-lane share, size.

Split by city: fit on the TRAINING cities, test on the DEVELOPMENT cities. Models: pykan KAN
(pruned, then symbolic), linear regression, sklearn MLP, gradient boosting. Outputs
`CAPTURE_LAW.json` and `capture_law_kan.png` in the package.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

FEATURES_ALL = [
    "team",
    "evader_avoidant",
    "pursuer_speed",
    "t_nearest",
    "t_mean",
    "lanes_first",
    "city_median_lanes",
    "city_closable3",
    "city_multilane",
    "city_junctions",
]
# r02: city-level features are constant within a city (4 training cities): excluded.
FEATURES = FEATURES_ALL[:6]
TRAIN = ["adelaide_cbd", "toronto_downtown", "washington_downtown", "seattle_downtown"]
TEST = ["phoenix_downtown", "portland_downtown", "sapporo_grid"]


def load_rows():
    """Episode-level rows: (salt, map, index, level, team, pursuer speed) -> D06 outcomes."""
    rows = {}
    a99 = os.path.join(ROOT, "experiments", "20261002_ambush_optimization_r01", "results.jsonl")
    with open(a99, encoding="utf-8") as h:
        for x in h:
            r = json.loads(x)
            k = r["key"].split("|")
            if k[0] != "test" or k[1] != "plus_opt" or "failed" in r:
                continue
            _, _, m, i, seed, level, team = k
            rows.setdefault(("PE11", m, int(i), level, int(team), 1.0), []).append(float(r["d06"]))
    sens = os.path.join(ROOT, "experiments", "20261002_sensitivity_r02", "results.jsonl")
    with open(sens, encoding="utf-8") as h:
        for x in h:
            r = json.loads(x)
            k = r["key"].split("|")
            if k[0] not in ("SP", "T7") or k[1] != "c215" or "failed" in r:
                continue
            _, _, m, i, seed, level, team, psf = k
            rows.setdefault(("PE12", m, int(i), level, int(team), float(psf)), []).append(
                float(r["d06"])
            )
    return rows


def features(keys):
    import sumolib

    from joint_interception.domain.contracts import load_domain  # noqa: F401
    from joint_interception.native.caging import Reach
    from joint_interception.simulator.evader import EvaderLevel
    from joint_interception.world.construction import make_scenario
    from train_caging_pilot import _net, _paths

    with open(
        os.path.join(ROOT, "docs", "manuscript", "junction_blockability.json"), encoding="utf-8"
    ) as h:
        block = json.load(h)
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as h:
        status = {x["map_id"]: x for x in json.load(h)["maps"]}
    out, lanes_cache = {}, {}
    for salt, m, i, level, team, psf in keys:
        net = _net(m)
        if m not in lanes_cache:
            sn = sumolib.net.readNet(_paths()[m])
            lanes_cache[m] = (sn, Reach(net))
        sn, reach = lanes_cache[m]
        sc = make_scenario(
            net, m, EvaderLevel[level], [f"p{k}" for k in range(1, team + 1)], f"{salt}s{i}"
        )
        e_edge = sc.evader_start[0]
        times = []
        for edge, offset, _speed in sc.pursuer_starts.values():
            dist, _ = reach.from_edge(edge, offset, speed_factor=psf)
            times.append(dist.get(e_edge, math.inf))
        times = [t for t in times if math.isfinite(t)] or [300.0]
        lanes_first = sum(
            sum(1 for ln in sn.getEdge(s).getLanes() if ln.allows("passenger"))
            for s in net.successors(e_edge)
        )
        out[(salt, m, i, level, team, psf)] = [
            team,
            float(level == "AVOIDANT"),
            psf,
            min(times),
            sum(times) / len(times),
            lanes_first,
            block[m]["median_lanes_to_close"],
            block[m]["closable_by_3"],
            status[m].get("multi_lane_fraction", 0.5),
            status[m].get("parsed_junctions", 400) / 100.0,
        ]
    return out


def main() -> int:
    import numpy as np
    import torch
    from kan import KAN
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
    from sklearn.neural_network import MLPClassifier

    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    by = load_rows()
    feats = features(sorted(by))
    X, y, city = [], [], []
    for k in sorted(by):
        for outcome in by[k]:  # one row per episode (seed)
            X.append(feats[k][: len(FEATURES)])
            y.append(outcome)
            city.append(k[1])
    X, y, city = np.array(X, dtype=np.float64), np.array(y), np.array(city)
    tr, te = np.isin(city, TRAIN), np.isin(city, TEST)
    lo, hi = X[tr].min(0), X[tr].max(0)
    span = np.where(hi - lo > 1e-9, hi - lo, 1.0)
    Xs = np.clip(2 * (X - lo) / span - 1, -1.5, 1.5)
    res = {
        "n_train": int(tr.sum()),
        "n_test": int(te.sum()),
        "features": FEATURES,
        "base_rate_train": round(float(y[tr].mean()), 4),
        "base_rate_test": round(float(y[te].mean()), 4),
        "split": {"train": TRAIN, "test": TEST},
        "models": {},
    }

    def score(name, p_te, p_tr):
        p_te, p_tr = np.clip(p_te, 1e-4, 1 - 1e-4), np.clip(p_tr, 1e-4, 1 - 1e-4)
        res["models"][name] = {
            "auc_train": round(float(roc_auc_score(y[tr], p_tr)), 4),
            "auc_test": round(float(roc_auc_score(y[te], p_te)), 4),
            "logloss_test": round(float(log_loss(y[te], p_te)), 4),
            "brier_test": round(float(brier_score_loss(y[te], p_te)), 4),
        }
        print(name, res["models"][name], flush=True)

    base = np.full(te.sum(), y[tr].mean())
    score("base_rate", base, np.full(tr.sum(), y[tr].mean()))
    lr = LogisticRegression(max_iter=2000).fit(Xs[tr], y[tr])
    score("logistic", lr.predict_proba(Xs[te])[:, 1], lr.predict_proba(Xs[tr])[:, 1])
    res["models"]["logistic"]["coefficients"] = {
        f: round(float(c), 4) for f, c in zip(FEATURES, lr.coef_[0], strict=True)
    }
    gb = GradientBoostingClassifier(random_state=0).fit(Xs[tr], y[tr])
    score("gradient_boosting", gb.predict_proba(Xs[te])[:, 1], gb.predict_proba(Xs[tr])[:, 1])
    mlp = MLPClassifier(
        hidden_layer_sizes=(32, 32), max_iter=2000, random_state=0, early_stopping=True
    ).fit(Xs[tr], y[tr])
    score("mlp", mlp.predict_proba(Xs[te])[:, 1], mlp.predict_proba(Xs[tr])[:, 1])

    torch.manual_seed(0)
    ds = {
        "train_input": torch.tensor(Xs[tr], dtype=torch.float32),
        "train_label": torch.tensor(y[tr][:, None], dtype=torch.float32),
        "test_input": torch.tensor(Xs[te], dtype=torch.float32),
        "test_label": torch.tensor(y[te][:, None], dtype=torch.float32),
    }
    bce = torch.nn.BCEWithLogitsLoss()

    def loss_fn(pred, target):
        return bce(pred, target)

    model = KAN(
        width=[len(FEATURES), 3, 1],
        grid=5,
        k=3,
        seed=0,
        ckpt_path=os.path.join(package, "kan_ckpt"),
    )
    model.fit(ds, opt="LBFGS", steps=50, lamb=0.003, loss_fn=loss_fn, log=1000)

    def prob(mdl, x):
        with torch.no_grad():
            return torch.sigmoid(mdl(x)).numpy().ravel()

    score("kan", prob(model, ds["test_input"]), prob(model, ds["train_input"]))
    model.attribute()
    res["models"]["kan"]["feature_score"] = {
        f: round(float(v), 4)
        for f, v in zip(FEATURES, model.feature_score.detach().numpy(), strict=True)
    }
    # Univariate effect curves of the KAN (others at the training median), probability scale.
    med = torch.tensor(np.median(Xs[tr], axis=0), dtype=torch.float32)
    curves = {}
    for j, f in enumerate(FEATURES):
        grid = np.linspace(
            float(np.percentile(Xs[tr][:, j], 2)), float(np.percentile(Xs[tr][:, j], 98)), 9
        )
        xx = med.repeat(len(grid), 1)
        xx[:, j] = torch.tensor(grid, dtype=torch.float32)
        p = prob(model, xx)
        raw = lo[j] + (grid + 1) / 2 * span[j]
        curves[f] = {"x": [round(float(v), 3) for v in raw], "p": [round(float(v), 4) for v in p]}
    res["models"]["kan"]["effect_curves"] = curves
    try:
        model.plot(folder=os.path.join(package, "kan_figures"))
        import matplotlib.pyplot as plt

        plt.savefig(os.path.join(package, "capture_law_kan.png"), dpi=200, bbox_inches="tight")
    except Exception as error:  # noqa: BLE001
        res["plot_error"] = str(error)[:200]
    with open(os.path.join(package, "CAPTURE_LAW.json"), "w", encoding="utf-8") as h:
        json.dump(res, h, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
