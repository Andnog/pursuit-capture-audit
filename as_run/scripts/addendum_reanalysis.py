"""Audit addendum, offline parts (A-115): B4 clustered uncertainty, B5 KAN with matched estimands,
and the summary of the replay blocks B1/B2/B3/B6 (`scripts/audit_addendum.py`).

B4: every pooled contrast is re-estimated with a family bootstrap (family = city x scenario x
evader; all team-size cells of a family move together) and a two-stage city -> family bootstrap.
B5: KAN, MLP, logistic and a spline-additive logistic (GAM-like) are compared on the same estimand:
observed held-out capture per feature bin vs the mean predicted probability of the same rows;
first-order ALE curves; family-grouped bootstrap of AUC and correlation differences; the symbolic
KAN expression in scaled and raw units. Output: ADDENDUM_SUMMARY.json in the addendum package.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

EXP = os.path.join(ROOT, "experiments")
REPS = 10000


def rows(path):
    with open(path, encoding="utf-8") as h:
        return [json.loads(x) for x in h]


def fam_boot(fams, reps=REPS, seed=11, alpha=0.05, two_stage=False):
    """fams: {(city, scenario, evader): [cell differences]}. Percentile interval."""
    keys = sorted(fams)
    allx = [x for k in keys for x in fams[k]]
    if not allx:
        return None
    rng = random.Random(seed)
    by_city = {}
    for k in keys:
        by_city.setdefault(k[0], []).append(k)
    cities = sorted(by_city)
    means = []
    for _ in range(reps):
        xs = []
        if two_stage:
            for c in (rng.choice(cities) for _ in cities):
                ks = by_city[c]
                for k in (rng.choice(ks) for _ in ks):
                    xs += fams[k]
        else:
            for k in (rng.choice(keys) for _ in keys):
                xs += fams[k]
        means.append(sum(xs) / len(xs))
    means.sort()
    lo, hi = int(alpha / 2 * reps), int((1 - alpha / 2) * reps) - 1
    return [round(sum(allx) / len(allx), 4), round(means[lo], 4), round(means[hi], 4)]


def seed_means(path, prefix, field="d06"):
    """{(method, city, scenario, evader, team): seed-averaged value}.

    Keys are 'prefix|method|m|i|seed|level|team'."""
    acc = {}
    for r in rows(path):
        p = r["key"].split("|")
        if p[0] != prefix or "failed" in r or field not in r:
            continue
        _, method, m, i, _seed, level, team = p[:7]
        acc.setdefault((method, m, int(i), level, int(team)), []).append(float(r[field]))
    return {k: sum(v) / len(v) for k, v in acc.items()}


def contrast(tab, a, b, levels, field_b=None):
    fams = {}
    other = field_b or tab
    for k, v in tab.items():
        if k[0] != a or k[3] not in levels:
            continue
        kb = (b,) + k[1:]
        if kb in other:
            fams.setdefault((k[1], k[2], k[3]), []).append(v - other[kb])
    return fams


def b4():
    out = {}
    a99 = seed_means(os.path.join(EXP, "20261002_ambush_optimization_r01", "results.jsonl"), "test")
    tx = seed_means(os.path.join(EXP, "20261003_test_confirmation_r01", "results.jsonl"), "TX")
    tx5 = seed_means(
        os.path.join(EXP, "20261003_test_confirmation_r01", "results.jsonl"), "TX", "prox_5m"
    )
    ox = seed_means(os.path.join(EXP, "20261003_test_confirmation_r01", "results.jsonl"), "OX")
    gd = {}
    for r in rows(os.path.join(EXP, "20261003_goal_evader_r01", "results.jsonl")):
        p = r["key"].split("|")
        if p[0] == "GD" and "failed" not in r:
            _, method, m, i, _s, team = p
            gd.setdefault((method, m, int(i), "GOAL_DIRECTED", int(team)), []).append(
                float(r["d06"])
            )
    gd = {k: sum(v) / len(v) for k, v in gd.items()}
    ar = ("AVOIDANT", "RANDOM")
    specs = {
        "A99_plb_minus_pursuit": (a99, "plus_opt", "pursuit", ar, None),
        "A99_plb_minus_a95 (A-99 primary)": (a99, "plus_opt", "ambush_a95", ar, None),
        "TEST_H1_plb_minus_pursuit": (tx, "plus_opt", "pursuit", ar, None),
        "TEST_S1_plb_minus_a95": (tx, "plus_opt", "ambush_a95", ar, None),
        "TEST_S2_optimal_plb_minus_pursuit": (tx, "plus_opt", "pursuit", ("OPTIMAL_ESCAPE",), None),
        "TEST_S4_mappo_kan_minus_plb": (tx, "mappo_kan", "plus_opt", ar, None),
        "TEST_S4_mappo_mlp_minus_plb": (tx, "mappo_mlp", "plus_opt", ar, None),
        "OX_optimal_plb_minus_pursuit": (ox, "plus_opt", "pursuit", ("OPTIMAL_ESCAPE",), None),
        "GOAL_plb_minus_pursuit": (gd, "plus_opt", "pursuit", ("GOAL_DIRECTED",), None),
    }
    for name, (tab, a, b, levels, _) in specs.items():
        fams = contrast(tab, a, b, levels)
        out[name] = {
            "families": len(fams),
            "cells": sum(len(v) for v in fams.values()),
            "family_95": fam_boot(fams),
            "family_97.5": fam_boot(fams, alpha=0.025),
            "city_family_95": fam_boot(fams, two_stage=True),
        }
    # H2: pursuit body-gap <= 5 m minus PC, all evaders and teams.
    fams = {}
    for k, v in tx5.items():
        if k[0] == "pursuit" and k in tx:
            fams.setdefault((k[1], k[2], k[3]), []).append(v - tx[k])
    out["TEST_H2_prox5_minus_pc_pursuit"] = {
        "families": len(fams),
        "family_97.5": fam_boot(fams, alpha=0.025),
        "city_family_95": fam_boot(fams, two_stage=True),
        "ratio_prox5_over_pc": round(
            sum(v for k, v in tx5.items() if k[0] == "pursuit")
            / max(1e-9, sum(v for k, v in tx.items() if k[0] == "pursuit" and k in tx5)),
            3,
        ),
    }
    return out


def replay_blocks(package):
    import itertools

    res = rows(os.path.join(package, "results.jsonl"))
    by = {}
    for r in res:
        by.setdefault(r["key"].split("|")[0], []).append(r)
    out = {}
    # B1 + the 1,245 complete A-108 replays.
    a108 = rows(os.path.join(EXP, "20261003_d06_persistence_audit_r01", "results.jsonl"))
    complete = [r for r in a108 if r.get("frozen") and r["frozen"]["window_s"] >= 60 - 1e-6]
    b1 = [r for r in by.get("B1", []) if "failed" not in r and r.get("frozen")]
    out["B1"] = {
        "complete_in_A108": len(complete),
        "escapes_in_complete_A108": sum(r["frozen"]["escape_60s"] for r in complete),
        "censored_replayed": len(b1),
        "failed": sum("failed" in r for r in by.get("B1", [])),
        "follow_up_now_complete": sum(r["frozen"]["follow_up_s"] >= 60 - 1e-6 for r in b1),
        "escapes_in_censored": sum(r["frozen"]["escape"] for r in b1),
        "total_with_60s": len(complete) + sum(r["frozen"]["follow_up_s"] >= 60 - 1e-6 for r in b1),
        "total_escapes": sum(r["frozen"]["escape_60s"] for r in complete)
        + sum(r["frozen"]["escape"] for r in b1),
    }
    n, e = out["B1"]["total_with_60s"], out["B1"]["total_escapes"]
    out["B1"]["escape_rate_wilson95"] = wilson(e, n)
    # B2: certificates with complete follow-up and joint escape.
    for blk in ("B2T", "B2F"):
        rs = [r for r in by.get(blk, []) if "failed" not in r and r.get("reproduced")]
        for cert in ("lane_nv", "junction"):
            sel = [r for r in rs if r["key"].split("|")[2 if blk == "B2T" else 4] == cert]
            if not sel:
                continue
            comp = [r for r in sel if not r["censored"]]
            fams = {}
            for r in comp:
                p = r["key"].split("|")
                fam = (p[3], p[4], p[6]) if blk == "B2T" else (p[2], p[3], p[1])
                fams.setdefault(fam, []).append(float(r["joint_escape_60"]))
            out[f"{blk}_{cert}"] = {
                "audited": len(sel),
                "not_reproduced_or_failed": len(by.get(blk, [])) - len(rs),
                "censored_after_extension": len(sel) - len(comp),
                "gate_escape_60": sum(r["gate_escape_60"] for r in comp),
                "exit_60": sum(r["exit_60"] and not r["gate_escape_60"] for r in comp),
                "joint_escape_60": sum(r["joint_escape_60"] for r in comp),
                "joint_rate_wilson95": wilson(sum(r["joint_escape_60"] for r in comp), len(comp)),
                "joint_rate_family95": fam_boot(fams),
                "precision_pc_among_audited": round(sum(r["d06"] for r in sel) / len(sel), 4),
            }
    # B3: null team.
    b3 = [r for r in by.get("B3", []) if "failed" not in r]
    out["B3_null_team"] = {
        "episodes": len(b3),
        "failed": sum("failed" in r for r in by.get("B3", [])),
        **{
            f: wilson(sum(r[f] for r in b3), len(b3))
            for f in ("d06", "prox_5m", "prox_5m_centre", "prox_10m")
        },
        "collisions": sum(r.get("collided", False) for r in b3),
    }
    # B6: no-route prevalence.
    b6 = [r for r in by.get("B6", []) if "failed" not in r]
    out["B6_no_route"] = {}
    for method, group in itertools.groupby(
        sorted(b6, key=lambda r: r["key"].split("|")[2]), key=lambda r: r["key"].split("|")[2]
    ):
        g = list(group)
        out["B6_no_route"][method] = {
            "episodes": len(g),
            "episodes_with_no_route": sum(r["no_route"] > 0 for r in g),
            "mean_no_route_events": round(sum(r["no_route"] for r in g) / len(g), 3),
            "d06_with_no_route": sum(r["d06"] for r in g if r["no_route"] > 0),
        }
    return out


def wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [k, n, round(p, 4), round(max(0.0, c - h), 4), round(c + h, 4)]


def b5(package):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import SplineTransformer

    import interpretability_capture_law as ic
    import kan_capture_law as kl

    X, y, city = ic.data()
    tr, dev, te = np.isin(city, kl.TRAIN), np.isin(city, kl.TEST), np.isin(city, ic.kt_cities())
    hold = dev | te
    lo, hi = X[tr].min(0), X[tr].max(0)
    span = np.where(hi - lo > 1e-9, hi - lo, 1.0)
    Xs = np.clip(2 * (X - lo) / span - 1, -1.5, 1.5)
    # Families for grouped uncertainty: rows are episodes; group by (city, start state) using the
    # first two continuous features as a proxy for the scenario identity within a city.
    fam = np.array(
        [
            f"{c}|{round(a, 3)}|{round(b, 3)}|{int(t)}"
            for c, a, b, t in zip(city, X[:, 3], X[:, 4], X[:, 0], strict=True)
        ]
    )
    sel = json.load(
        open(  # noqa: SIM115
            os.path.join(EXP, "20261003_interpretability_r01", "INTERPRETABILITY_CAPTURE_LAW.json")
        )
    )
    hidden, alpha = tuple(sel["mlp_selection"]["hidden"]), sel["mlp_selection"]["alpha"]
    gam_c, gam_scores = None, {}
    for c in (0.01, 0.1, 1.0, 10.0):
        losses = []
        for g in sorted(set(city[tr])):
            a, b = tr & (city != g), tr & (city == g)
            m = make_pipeline(
                SplineTransformer(n_knots=5, degree=3), LogisticRegression(C=c, max_iter=3000)
            ).fit(Xs[a], y[a])
            p = m.predict_proba(Xs[b])[:, 1].clip(1e-4, 1 - 1e-4)
            losses.append(float(-(y[b] * np.log(p) + (1 - y[b]) * np.log(1 - p)).mean()))
        gam_scores[c] = round(sum(losses) / len(losses), 4)
        if gam_c is None or gam_scores[c] < gam_scores[gam_c]:
            gam_c = c

    class Gam:
        def fit(self, A, b):
            self.m = make_pipeline(
                SplineTransformer(n_knots=5, degree=3), LogisticRegression(C=gam_c, max_iter=3000)
            ).fit(A, b)
            return self

        def predict_proba(self, A):
            return self.m.predict_proba(A)[:, 1]

    models = {
        "kan": ic.Kan(0, package).fit(Xs[tr], y[tr]),
        "mlp": ic.Mlp(hidden, alpha, 0).fit(Xs[tr], y[tr]),
        "logistic": ic.Logit().fit(Xs[tr], y[tr]),
        "spline_gam": Gam().fit(Xs[tr], y[tr]),
    }
    pred = {k: m.predict_proba(Xs) for k, m in models.items()}
    res = {
        "gam_C": gam_c,
        "gam_cv_logloss": gam_scores,
        "auc": {},
        "matched_estimand": {},
        "ale": {},
    }
    for k in models:
        res["auc"][k] = {
            "dev": round(float(roc_auc_score(y[dev], pred[k][dev])), 4),
            "test": round(float(roc_auc_score(y[te], pred[k][te])), 4),
        }
    # Matched estimand: per bin of feature j (held-out rows), observed mean vs mean prediction.
    for j, f in enumerate(kl.FEATURES):
        vals = np.unique(X[hold][:, j])
        edges = vals if len(vals) <= 12 else np.quantile(X[hold][:, j], np.linspace(0, 1, 10))
        idx = (
            np.digitize(X[hold][:, j], edges[1:-1], right=True)
            if len(vals) > 12
            else np.searchsorted(vals, X[hold][:, j])
        )
        bins = [b for b in np.unique(idx) if (idx == b).sum() >= 30]
        if len(bins) < 3:
            continue
        obs = [float(y[hold][idx == b].mean()) for b in bins]
        entry = {"bins": len(bins), "observed": [round(o, 4) for o in obs], "models": {}}
        for k in models:
            pm = [float(pred[k][hold][idx == b].mean()) for b in bins]
            r = float(np.corrcoef(pm, obs)[0, 1]) if np.std(pm) > 1e-9 else None
            mae = float(np.mean(np.abs(np.array(pm) - np.array(obs))))
            entry["models"][k] = {
                "pred": [round(p, 4) for p in pm],
                "r": None if r is None else round(r, 3),
                "mae": round(mae, 4),
            }
        res["matched_estimand"][f] = entry
    # ALE (first order) on held-out rows.
    for j in (5, 4):
        f = kl.FEATURES[j]
        z = np.unique(np.quantile(Xs[hold][:, j], np.linspace(0, 1, 9)))
        curves = {}
        for k, m in models.items():
            eff = [0.0]
            for a, b in zip(z[:-1], z[1:], strict=True):
                inb = hold & (Xs[:, j] >= a) & (Xs[:, j] <= b)
                if inb.sum() == 0:
                    eff.append(eff[-1])
                    continue
                A, B = Xs[inb].copy(), Xs[inb].copy()
                A[:, j], B[:, j] = a, b
                eff.append(eff[-1] + float(np.mean(m.predict_proba(B) - m.predict_proba(A))))
            c = np.array(eff) - np.mean(eff)
            curves[k] = [round(float(v), 4) for v in c]
        res["ale"][f] = {
            "x_raw": [round(float(lo[j] + (v + 1) / 2 * span[j]), 3) for v in z],
            "curves": curves,
        }
    # Family-grouped bootstrap of differences (held-out rows).
    H = np.where(hold)[0]
    fams = {}
    for i in H:
        fams.setdefault(fam[i], []).append(i)
    keys = sorted(fams)
    rng = random.Random(5)
    j_l = kl.FEATURES.index("lanes_first")
    vals_l = np.unique(X[hold][:, j_l])
    draws = {
        "auc_kan_minus_logistic": [],
        "auc_kan_minus_mlp": [],
        "auc_kan_minus_gam": [],
        "r_lanes_kan_minus_logistic": [],
        "r_lanes_kan_minus_gam": [],
    }
    for _ in range(500):
        ii = np.concatenate([fams[k] for k in (rng.choice(keys) for _ in keys)])
        yy = y[ii]
        if yy.min() == yy.max():
            continue
        auc = {k: roc_auc_score(yy, pred[k][ii]) for k in models}
        draws["auc_kan_minus_logistic"].append(auc["kan"] - auc["logistic"])
        draws["auc_kan_minus_mlp"].append(auc["kan"] - auc["mlp"])
        draws["auc_kan_minus_gam"].append(auc["kan"] - auc["spline_gam"])
        xl = X[ii, j_l]
        rr = {}
        for k in ("kan", "logistic", "spline_gam"):
            o, p = [], []
            for v in vals_l:
                mk = xl == v
                if mk.sum() >= 30:
                    o.append(yy[mk].mean())
                    p.append(pred[k][ii][mk].mean())
            rr[k] = np.corrcoef(p, o)[0, 1] if len(o) >= 3 and np.std(p) > 1e-9 else np.nan
        draws["r_lanes_kan_minus_logistic"].append(rr["kan"] - rr["logistic"])
        draws["r_lanes_kan_minus_gam"].append(rr["kan"] - rr["spline_gam"])
    res["family_bootstrap_95"] = {
        k: [
            round(float(np.nanmean(v)), 4),
            round(float(np.nanpercentile(v, 2.5)), 4),
            round(float(np.nanpercentile(v, 97.5)), 4),
        ]
        for k, v in draws.items()
    }
    res["families_heldout"] = len(keys)
    sym = json.load(open(os.path.join(EXP, "20261003_interpretability_r01", "KAN_SYMBOLIC.json")))  # noqa: SIM115
    j = kl.FEATURES.index("lanes_first")
    res["symbolic"] = {
        "scaled_formula": sym.get("formula"),
        "scaling": {
            f: {"min": float(lo[i]), "span": float(span[i])} for i, f in enumerate(kl.FEATURES)
        },
        "note": "x_scaled = 2 (x - min) / span - 1, clipped to [-1.5, 1.5]",
        "lanes_coefficient_per_raw_lane": round(-0.744125823218616 * 2 / float(span[j]), 4),
    }
    return res


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    out = {"B4": b4(), "replays": replay_blocks(package), "B5": b5(package)}
    with open(os.path.join(package, "ADDENDUM_SUMMARY.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    print(json.dumps({"B4": out["B4"], "replays": out["replays"]}, indent=1))
    print(
        json.dumps({k: out["B5"][k] for k in ("auc", "family_bootstrap_95", "symbolic")}, indent=1)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
