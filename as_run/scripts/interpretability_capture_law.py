"""A-113 Part 1: is the KAN's explanation of the capture law special? KAN vs MLP vs logistic.

Data: A-104 episodes (TRAINING cities fit, DEVELOPMENT cities held out) and the PLB TEST episodes
(A-110 TX, AVOIDANT/RANDOM). Six features (A-104). Metrics fixed in A-113:
(a) held-out AUC; (b) Kendall tau between feature rankings; (c) faithfulness of partial-dependence
curves to observed held-out capture by feature bin; (d) ranking stability over 20 bootstrap refits;
(e) KAN symbolic extraction; (f) cost. Output: INTERPRETABILITY_CAPTURE_LAW.json.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import kan_capture_law as kl  # noqa: E402
import kan_capture_law_test as kt  # noqa: E402

REFITS = 20
GRID = 9


def data():
    import numpy as np

    by = kl.load_rows()
    feats = kl.features(sorted(by))
    X, y, city = [], [], []
    for k in sorted(by):
        for o in by[k]:
            X.append(feats[k][: len(kl.FEATURES)])
            y.append(o)
            city.append(k[1])
    tby = kt.test_rows()
    tfeats = kt.test_features(sorted(tby))
    for k in sorted(tby):
        for o in tby[k]:
            X.append(tfeats[k])
            y.append(o)
            city.append(k[1])
    return np.array(X, dtype=np.float64), np.array(y), np.array(city)


class Kan:
    name = "kan"

    def __init__(self, seed=0, package=None):
        self.seed, self.package = seed, package

    def fit(self, X, y):
        import torch
        from kan import KAN

        torch.manual_seed(self.seed)
        ds = {
            "train_input": torch.tensor(X, dtype=torch.float32),
            "train_label": torch.tensor(y[:, None], dtype=torch.float32),
            "test_input": torch.tensor(X[:2], dtype=torch.float32),
            "test_label": torch.tensor(y[:2, None], dtype=torch.float32),
        }
        bce = torch.nn.BCEWithLogitsLoss()
        self.m = KAN(
            width=[X.shape[1], 3, 1],
            grid=5,
            k=3,
            seed=self.seed,
            ckpt_path=os.path.join(self.package, f"kan_ckpt_{self.seed}"),
            auto_save=False,
        )
        self.m.fit(ds, opt="LBFGS", steps=50, lamb=0.003, loss_fn=lambda p, t: bce(p, t), log=1000)
        return self

    def predict_proba(self, X):
        import torch

        with torch.no_grad():
            return torch.sigmoid(self.m(torch.tensor(X, dtype=torch.float32))).numpy().ravel()

    def native(self):
        self.m.attribute()
        return [float(v) for v in self.m.feature_score.detach().numpy()]

    def params(self):
        return int(sum(p.numel() for p in self.m.parameters()))


class Logit:
    name = "logistic"

    def fit(self, X, y):
        from sklearn.linear_model import LogisticRegression

        self.m = LogisticRegression(max_iter=2000).fit(X, y)
        return self

    def predict_proba(self, X):
        return self.m.predict_proba(X)[:, 1]

    def native(self):
        return [abs(float(c)) for c in self.m.coef_[0]]

    def params(self):
        return int(self.m.coef_.size + 1)


class Mlp:
    name = "mlp"

    def __init__(self, hidden=(16,), alpha=1e-2, seed=0):
        self.hidden, self.alpha, self.seed = hidden, alpha, seed

    def fit(self, X, y):
        from sklearn.neural_network import MLPClassifier

        self.m = MLPClassifier(
            hidden_layer_sizes=self.hidden, alpha=self.alpha, max_iter=3000, random_state=self.seed
        ).fit(X, y)
        return self

    def predict_proba(self, X):
        return self.m.predict_proba(X)[:, 1]

    def native(self):
        return None

    def params(self):
        return int(sum(w.size for w in self.m.coefs_) + sum(b.size for b in self.m.intercepts_))


def choose_mlp(X, y, groups):
    """Size and L2 weight by grouped CV over TRAINING cities (log loss)."""
    from sklearn.metrics import log_loss

    best, scores = None, {}
    for hidden, alpha in itertools.product([(8,), (16,), (16, 16)], [1e-3, 1e-2, 1e-1, 1.0]):
        losses = []
        for g in sorted(set(groups)):
            tr, va = groups != g, groups == g
            p = Mlp(hidden, alpha).fit(X[tr], y[tr]).predict_proba(X[va])
            losses.append(log_loss(y[va], p.clip(1e-4, 1 - 1e-4), labels=[0, 1]))
        scores[f"{hidden}|{alpha}"] = round(sum(losses) / len(losses), 4)
        if best is None or scores[f"{hidden}|{alpha}"] < scores[best[2]]:
            best = (hidden, alpha, f"{hidden}|{alpha}")
    return best[0], best[1], scores


def permutation_importance(model, X, y, reps=10, seed=0):
    import numpy as np
    from sklearn.metrics import roc_auc_score

    rng = np.random.default_rng(seed)
    base = roc_auc_score(y, model.predict_proba(X))
    out = []
    for j in range(X.shape[1]):
        drops = []
        for _ in range(reps):
            Xp = X.copy()
            Xp[:, j] = rng.permutation(Xp[:, j])
            drops.append(base - roc_auc_score(y, model.predict_proba(Xp)))
        out.append(float(np.mean(drops)))
    return out


def pd_curve(model, X, j, grid):
    import numpy as np

    out = []
    for g in grid:
        Xg = X.copy()
        Xg[:, j] = g
        out.append(float(np.mean(model.predict_proba(Xg))))
    return out


def kendall(a, b):
    from scipy.stats import kendalltau

    return round(float(kendalltau(a, b).statistic), 3)


def pearson(a, b):
    import numpy as np

    if np.std(a) < 1e-9 or np.std(b) < 1e-9:
        return None
    return round(float(np.corrcoef(a, b)[0, 1]), 3)


def main() -> int:
    import numpy as np
    from sklearn.metrics import roc_auc_score

    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    X, y, city = data()
    tr, dev, te = np.isin(city, kl.TRAIN), np.isin(city, kl.TEST), np.isin(city, kt_cities())
    lo, hi = X[tr].min(0), X[tr].max(0)
    span = np.where(hi - lo > 1e-9, hi - lo, 1.0)
    Xs = np.clip(2 * (X - lo) / span - 1, -1.5, 1.5)
    hold = dev | te
    res = {"features": kl.FEATURES, "n": {"train": int(tr.sum()), "dev": int(dev.sum())}}
    res["n"]["test"] = int(te.sum())
    hidden, alpha, cv = choose_mlp(Xs[tr], y[tr], city[tr])
    res["mlp_selection"] = {"hidden": list(hidden), "alpha": alpha, "cv_logloss": cv}

    makers = {
        "kan": lambda s: Kan(s, package),
        "logistic": lambda s: Logit(),
        "mlp": lambda s: Mlp(hidden, alpha, s),
    }
    grids = [
        np.linspace(np.percentile(Xs[tr][:, j], 2), np.percentile(Xs[tr][:, j], 98), GRID)
        for j in range(X.shape[1])
    ]
    # Observed held-out capture by grid bin (nearest grid point), bins with >= 30 rows.
    observed = []
    for j, g in enumerate(grids):
        idx = np.abs(Xs[hold][:, j][:, None] - g[None, :]).argmin(1)
        observed.append(
            [
                float(y[hold][idx == b].mean()) if (idx == b).sum() >= 30 else None
                for b in range(GRID)
            ]
        )
    res["models"] = {}
    for name, make in makers.items():
        t0 = time.time()
        m = make(0).fit(Xs[tr], y[tr])
        fit_s = round(time.time() - t0, 2)
        entry = {
            "auc_dev": round(float(roc_auc_score(y[dev], m.predict_proba(Xs[dev]))), 4),
            "auc_test": round(float(roc_auc_score(y[te], m.predict_proba(Xs[te]))), 4),
            "auc_train": round(float(roc_auc_score(y[tr], m.predict_proba(Xs[tr]))), 4),
            "params": m.params(),
            "fit_s": fit_s,
            "native_importance": m.native(),
            "perm_importance_heldout": permutation_importance(m, Xs[hold], y[hold]),
            "pd": {},
            "pd_faithfulness_r": {},
        }
        for j, f in enumerate(kl.FEATURES):
            curve = pd_curve(m, Xs[hold], j, grids[j])
            pairs = [(c, o) for c, o in zip(curve, observed[j], strict=True) if o is not None]
            entry["pd"][f] = {
                "x": [round(float(lo[j] + (g + 1) / 2 * span[j]), 3) for g in grids[j]],
                "p": [round(c, 4) for c in curve],
            }
            entry["pd_faithfulness_r"][f] = (
                pearson([a for a, _ in pairs], [b for _, b in pairs]) if len(pairs) >= 4 else None
            )
        # Stability over bootstrap refits (rankings of held-out permutation importance; native too).
        rng = np.random.default_rng(1)
        perm_ranks, native_ranks = [], []
        idx_tr = np.where(tr)[0]
        for s in range(REFITS):
            b = rng.choice(idx_tr, size=len(idx_tr), replace=True)
            mb = make(s + 1).fit(Xs[b], y[b])
            perm_ranks.append(permutation_importance(mb, Xs[hold], y[hold], reps=3, seed=s))
            if mb.native() is not None:
                native_ranks.append(mb.native())

        def mean_tau(rs):
            ts = [kendall(a, b) for a, b in itertools.combinations(rs, 2)]
            return round(float(np.nanmean(ts)), 3) if ts else None

        entry["stability_tau_perm"] = mean_tau(perm_ranks)
        entry["stability_tau_native"] = mean_tau(native_ranks) if native_ranks else None
        res["models"][name] = entry
        if name == "kan":
            kan_model = m
        print(name, {k: entry[k] for k in ("auc_dev", "auc_test", "params", "fit_s")}, flush=True)
    # (b) agreement between rankings.
    vec = {
        "kan_native": res["models"]["kan"]["native_importance"],
        "kan_perm": res["models"]["kan"]["perm_importance_heldout"],
        "logistic_coef": res["models"]["logistic"]["native_importance"],
        "logistic_perm": res["models"]["logistic"]["perm_importance_heldout"],
        "mlp_perm": res["models"]["mlp"]["perm_importance_heldout"],
    }
    res["ranking_agreement_tau"] = {
        f"{a}~{b}": kendall(vec[a], vec[b]) for a, b in itertools.combinations(vec, 2)
    }
    res["top_feature"] = {k: kl.FEATURES[int(np.argmax(v))] for k, v in vec.items()}
    res["observed_heldout_by_bin"] = {f: observed[j] for j, f in enumerate(kl.FEATURES)}
    # (e) symbolic extraction on the pruned KAN.
    try:
        pruned = kan_model.m.prune()
        pruned.auto_symbolic(lib=["x", "x^2", "exp", "log", "tanh", "sin", "abs"])
        formula = pruned.symbolic_formula()[0][0]
        res["kan_symbolic"] = {"ok": True, "formula": str(formula)[:600]}
    except Exception as error:  # noqa: BLE001
        res["kan_symbolic"] = {"ok": False, "error": f"{type(error).__name__}: {str(error)[:200]}"}
    with open(
        os.path.join(package, "INTERPRETABILITY_CAPTURE_LAW.json"), "w", encoding="utf-8"
    ) as h:
        json.dump(res, h, indent=2)
    print(
        json.dumps(
            {k: res[k] for k in ("ranking_agreement_tau", "top_feature", "kan_symbolic")}, indent=1
        )
    )
    return 0


def kt_cities():
    return ["chicago_loop", "melbourne_cbd", "salt_lake_city", "minneapolis_downtown"]


if __name__ == "__main__":
    raise SystemExit(main())
