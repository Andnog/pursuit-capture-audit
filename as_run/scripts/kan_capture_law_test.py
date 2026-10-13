"""A-104 KAN capture law scored on the TEST cities (A-110 S7, post hoc, descriptive).

Refits the A-104 models exactly as `kan_capture_law.py` does (same data, features, seeds and
settings) and scores them on the c2_15 planner's TEST episodes (block TX, AVOIDANT / RANDOM,
pursuers 1.0x). Output: `CAPTURE_LAW_TEST.json` in the package.
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

import kan_capture_law as kl  # noqa: E402

TX = os.path.join(ROOT, "experiments", "20261003_test_confirmation_r01", "results.jsonl")


def test_rows():
    rows = {}
    with open(TX, encoding="utf-8") as h:
        for x in h:
            r = json.loads(x)
            k = r["key"].split("|")
            if k[0] != "TX" or k[1] != "plus_opt" or "failed" in r or k[5] == "OPTIMAL_ESCAPE":
                continue
            _, _, m, i, _seed, level, team = k
            rows.setdefault(("PT1", m, int(i), level, int(team), 1.0), []).append(float(r["d06"]))
    return rows


def test_features(keys):
    """The six A-104 features (city-level features are not used by the fitted models)."""
    import sumolib

    from joint_interception.native.caging import Reach
    from joint_interception.simulator.evader import EvaderLevel
    from joint_interception.world.construction import make_scenario
    from train_caging_pilot import _net, _paths

    out, cache = {}, {}
    for salt, m, i, level, team, psf in keys:
        net = _net(m)
        if m not in cache:
            cache[m] = (sumolib.net.readNet(_paths()[m]), Reach(net))
        sn, reach = cache[m]
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
        ]
    return out


def main() -> int:
    import numpy as np
    import torch
    from kan import KAN
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import brier_score_loss, roc_auc_score

    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    by = kl.load_rows()
    feats = kl.features(sorted(by))
    X, y, city = [], [], []
    for k in sorted(by):
        for outcome in by[k]:
            X.append(feats[k][: len(kl.FEATURES)])
            y.append(outcome)
            city.append(k[1])
    X, y, city = np.array(X, dtype=np.float64), np.array(y), np.array(city)
    tr = np.isin(city, kl.TRAIN)
    lo, hi = X[tr].min(0), X[tr].max(0)
    span = np.where(hi - lo > 1e-9, hi - lo, 1.0)

    def scale(a):
        return np.clip(2 * (a - lo) / span - 1, -1.5, 1.5)

    tby = test_rows()
    tfeats = test_features(sorted(tby))
    Xt, yt, ct = [], [], []
    for k in sorted(tby):
        for outcome in tby[k]:
            Xt.append(tfeats[k])
            yt.append(outcome)
            ct.append(k[1])
    Xt, yt = np.array(Xt, dtype=np.float64), np.array(yt)
    Xs, Xts = scale(X), scale(Xt)

    lr = LogisticRegression(max_iter=2000).fit(Xs[tr], y[tr])
    torch.manual_seed(0)
    ds = {
        "train_input": torch.tensor(Xs[tr], dtype=torch.float32),
        "train_label": torch.tensor(y[tr][:, None], dtype=torch.float32),
        "test_input": torch.tensor(Xts, dtype=torch.float32),
        "test_label": torch.tensor(yt[:, None], dtype=torch.float32),
    }
    bce = torch.nn.BCEWithLogitsLoss()
    model = KAN(
        width=[len(kl.FEATURES), 3, 1],
        grid=5,
        k=3,
        seed=0,
        ckpt_path=os.path.join(package, "kan_ckpt"),
    )
    model.fit(ds, opt="LBFGS", steps=50, lamb=0.003, loss_fn=lambda p, t: bce(p, t), log=1000)
    with torch.no_grad():
        p_kan = torch.sigmoid(model(ds["test_input"])).numpy().ravel()
    p_lr = lr.predict_proba(Xts)[:, 1]
    res = {
        "n_test": len(yt),
        "base_rate_test": round(float(yt.mean()), 4),
        "kan": {
            "auc_test": round(float(roc_auc_score(yt, p_kan)), 4),
            "brier_test": round(float(brier_score_loss(yt, np.clip(p_kan, 1e-4, 1 - 1e-4))), 4),
        },
        "logistic": {
            "auc_test": round(float(roc_auc_score(yt, p_lr)), 4),
            "brier_test": round(float(brier_score_loss(yt, p_lr)), 4),
        },
        "capture_by_lanes_first": {},
    }
    lanes = Xt[:, 5]
    for a, b in ((0, 4), (5, 6), (7, 100)):
        sel = (lanes >= a) & (lanes <= b)
        if sel.any():
            res["capture_by_lanes_first"][f"{a}-{b}"] = [
                round(float(yt[sel].mean()), 3),
                int(sel.sum()),
            ]
    with open(os.path.join(package, "CAPTURE_LAW_TEST.json"), "w", encoding="utf-8") as h:
        json.dump(res, h, indent=2)
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
