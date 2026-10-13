"""Addendum r02, offline parts (A-119).

K  KAN / spline-additive / MLP / logistic capture models (the A-104 / B5 fits), evaluated
   separately on DEVELOPMENT and TEST. Families are the true scenario identities (salt, city,
   scenario, evader); all
   team-size and pursuer-speed variants of a family are resampled together. Observed estimates and
   percentile intervals are reported separately.
N  null-team (r01 B3) rates with family-clustered intervals (family = city, scenario, evader).
I  containment-indicator joint escape (r01 B2) with family-clustered intervals.
P  persistence: the 1,433 captures broken down by family and city (no i.i.d. bound).
W/S summaries of the r02 replays.
Output: ADDENDUM_R02_SUMMARY.json in the package.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

EXP = os.path.join(ROOT, "experiments")
R01 = os.path.join(EXP, "20261004_audit_addendum_r01")


def rows(path):
    with open(path, encoding="utf-8") as h:
        return [json.loads(x) for x in h]


def fam_boot_mean(values_by_family, reps=10000, seed=3):
    keys = sorted(values_by_family)
    allx = [x for k in keys for x in values_by_family[k]]
    if not allx:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(reps):
        xs = []
        for k in (rng.choice(keys) for _ in keys):
            xs += values_by_family[k]
        means.append(sum(xs) / len(xs))
    means.sort()
    return {
        "observed": round(sum(allx) / len(allx), 4),
        "family_95": [round(means[int(0.025 * reps)], 4), round(means[int(0.975 * reps) - 1], 4)],
        "families": len(keys),
        "n": len(allx),
    }


def kan_section(package):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import SplineTransformer

    import interpretability_capture_law as ic
    import kan_capture_law as kl
    import kan_capture_law_test as kt

    X, y, city = ic.data()
    # True family per row, in the exact order ic.data() builds them.
    fam = []
    by = kl.load_rows()
    for k in sorted(by):
        fam += [f"{k[0]}|{k[1]}|{k[2]}|{k[3]}"] * len(by[k])
    tby = kt.test_rows()
    for k in sorted(tby):
        fam += [f"{k[0]}|{k[1]}|{k[2]}|{k[3]}"] * len(tby[k])
    fam = np.array(fam)
    assert len(fam) == len(y)
    tr, dev, te = np.isin(city, kl.TRAIN), np.isin(city, kl.TEST), np.isin(city, ic.kt_cities())
    lo, hi = X[tr].min(0), X[tr].max(0)
    span = np.where(hi - lo > 1e-9, hi - lo, 1.0)
    Xs = np.clip(2 * (X - lo) / span - 1, -1.5, 1.5)
    with open(
        os.path.join(EXP, "20261003_interpretability_r01", "INTERPRETABILITY_CAPTURE_LAW.json")
    ) as h:
        sel = json.load(h)
    with open(os.path.join(R01, "ADDENDUM_SUMMARY.json")) as h:
        gam_c = json.load(h)["B5"]["gam_C"]
    gam = make_pipeline(
        SplineTransformer(n_knots=5, degree=3), LogisticRegression(C=gam_c, max_iter=3000)
    )
    models = {
        "kan": ic.Kan(0, package).fit(Xs[tr], y[tr]),
        "spline_gam": gam.fit(Xs[tr], y[tr]),
        "mlp": ic.Mlp(tuple(sel["mlp_selection"]["hidden"]), sel["mlp_selection"]["alpha"], 0).fit(
            Xs[tr], y[tr]
        ),
        "logistic": ic.Logit().fit(Xs[tr], y[tr]),
    }
    pred = {
        k: (m.predict_proba(Xs)[:, 1] if k == "spline_gam" else m.predict_proba(Xs))
        for k, m in models.items()
    }
    jl = kl.FEATURES.index("lanes_first")

    def bin_r(idx, k):
        xl, yy, pp = X[idx, jl], y[idx], pred[k][idx]
        o, p = [], []
        for v in np.unique(xl):
            mk = xl == v
            if mk.sum() >= 30:
                o.append(yy[mk].mean())
                p.append(pp[mk].mean())
        if len(o) < 3 or np.std(p) < 1e-9:
            return float("nan")
        return float(np.corrcoef(p, o)[0, 1])

    out = {"families_total": int(len(set(fam[dev | te]))), "splits": {}}
    for split, mask in (("DEVELOPMENT", dev), ("TEST", te)):
        idx_all = np.where(mask)[0]
        fams = {}
        for i in idx_all:
            fams.setdefault(fam[i], []).append(i)
        keys = sorted(fams)
        obs_auc = {k: float(roc_auc_score(y[idx_all], pred[k][idx_all])) for k in models}
        obs_r = {k: bin_r(idx_all, k) for k in models}
        rng = random.Random(11)
        draws = {f"auc_kan_minus_{k}": [] for k in models if k != "kan"}
        draws.update({f"binr_kan_minus_{k}": [] for k in models if k != "kan"})
        for _ in range(1000):
            ii = np.concatenate([fams[k] for k in (rng.choice(keys) for _ in keys)])
            if y[ii].min() == y[ii].max():
                continue
            a = {k: roc_auc_score(y[ii], pred[k][ii]) for k in models}
            r = {k: bin_r(ii, k) for k in models}
            for k in models:
                if k != "kan":
                    draws[f"auc_kan_minus_{k}"].append(a["kan"] - a[k])
                    draws[f"binr_kan_minus_{k}"].append(r["kan"] - r[k])
        res = {
            "rows": int(mask.sum()),
            "families": len(keys),
            "observed_auc": {k: round(v, 4) for k, v in obs_auc.items()},
            "observed_bin_r_lanes": {k: round(v, 4) for k, v in obs_r.items()},
            "differences": {},
        }
        for name, v in draws.items():
            base = name.split("_minus_")
            metric, other = base[0].split("_kan")[0], base[1]
            observed = (obs_auc if metric == "auc" else obs_r)["kan"] - (
                obs_auc if metric == "auc" else obs_r
            )[other]
            arr = np.array([x for x in v if np.isfinite(x)])
            res["differences"][name] = {
                "observed": round(float(observed), 4),
                "family_95": [
                    round(float(np.percentile(arr, 2.5)), 4),
                    round(float(np.percentile(arr, 97.5)), 4),
                ],
                "valid_draws": int(len(arr)),
            }
        out["splits"][split] = res
    return out


def null_and_indicators():
    out = {}
    b = [r for r in rows(os.path.join(R01, "results.jsonl")) if "failed" not in r]
    b3 = [r for r in b if r["key"].startswith("B3|")]
    for f in ("d06", "prox_5m", "prox_5m_centre", "prox_10m"):
        fams = {}
        for r in b3:
            _, m, i, _seed, level, _team = r["key"].split("|")
            fams.setdefault((m, i, level), []).append(float(r[f]))
        out[f"null_{f}"] = fam_boot_mean(fams)
    for blk in ("B2T", "B2F"):
        for cert in ("lane_nv", "junction"):
            fams = {}
            for r in b:
                if not r["key"].startswith(blk + "|") or not r.get("reproduced"):
                    continue
                p = r["key"].split("|")
                c = p[2] if blk == "B2T" else p[4]
                if c != cert or r.get("censored"):
                    continue
                fam = (p[3], p[4], p[6]) if blk == "B2T" else (p[2], p[3])
                fams.setdefault(fam, []).append(float(r["joint_escape_60"]))
            out[f"{blk}_{cert}_joint"] = fam_boot_mean(fams)
    return out


def persistence():
    a108 = rows(os.path.join(EXP, "20261003_d06_persistence_audit_r01", "results.jsonl"))
    fams, cities = set(), {}
    for r in a108:
        if not r.get("frozen"):
            continue
        _, method, m, i, seed, level, team = r["key"].split("|")
        fams.add((m, i, level))
        cities[m] = cities.get(m, 0) + 1
    return {
        "captures": sum(cities.values()),
        "families_scenario_evader": len(fams),
        "cities": cities,
        "escapes_observed": 0,
        "note": "captures share families across methods, teams and seeds; no i.i.d. bound",
    }


def replays(package):
    res = rows(os.path.join(package, "results.jsonl"))
    w = [r for r in res if r["key"].startswith("W|")]
    ok = [r for r in w if "failed" not in r]
    out = {
        "W": {
            "cases": len(w),
            "failed": len(w) - len(ok),
            "witness_reproduced": sum(r.get("reproduced", False) for r in ok),
            "states_equal_at_t_c": sum(r.get("states_equal_at_t_c", False) for r in ok),
            "same_finisher": sum(
                bool(r.get("natural_capture") and r.get("frozen_capture"))
                and r["natural_capture"][1] == r["frozen_capture"][1]
                for r in ok
            ),
            "follow_up_60": sum(
                (r.get("follow_up") or {}).get("follow_up_s", 0) >= 60 - 1e-6 for r in ok
            ),
            "escapes": sum(bool((r.get("follow_up") or {}).get("escape")) for r in ok),
        }
    }
    s = {r["key"]: r for r in res if r["key"].startswith("S|") and "failed" not in r}
    sealed = {}
    for r in rows(os.path.join(EXP, "20261002_ambush_optimization_r01", "results.jsonl")):
        sealed[r["key"]] = r
    per = {}
    for k, r in s.items():
        _, mode, *rest = k.split("|")
        base = "|".join(rest)
        per.setdefault(base, {})[mode] = r
    pairs = {b: v for b, v in per.items() if "legacy" in v and "checked" in v}
    by_method = {}
    for b, v in pairs.items():
        method = b.split("|")[1]
        d = by_method.setdefault(
            method,
            {"episodes": 0, "legacy_reproduces_sealed": 0, "any_non_accepted_legacy": 0,
             "any_non_accepted_checked": 0, "outcome_changed": 0, "legacy_d06": 0,
             "checked_d06": 0},
        )  # fmt: skip
        d["episodes"] += 1
        d["legacy_reproduces_sealed"] += int(v["legacy"]["d06"] == bool(sealed[b]["d06"]))
        d["any_non_accepted_legacy"] += int(bool(v["legacy"]["dispatch"]))
        d["any_non_accepted_checked"] += int(bool(v["checked"]["dispatch"]))
        d["outcome_changed"] += int(v["legacy"]["d06"] != v["checked"]["d06"])
        d["legacy_d06"] += int(v["legacy"]["d06"])
        d["checked_d06"] += int(v["checked"]["d06"])
    statuses = {}
    for v in pairs.values():
        for mode in ("legacy", "checked"):
            for st, c in v[mode]["dispatch"].items():
                statuses.setdefault(mode, {}).setdefault(st, 0)
                statuses[mode][st] += c
    out["S"] = {"by_method": by_method, "dispatch_events": statuses, "paired_episodes": len(pairs)}
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--skip-replays", action="store_true")
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    out = {"N_I": null_and_indicators(), "P": persistence(), "K": kan_section(package)}
    if not args.skip_replays:
        out["replays"] = replays(package)
    with open(os.path.join(package, "ADDENDUM_R02_SUMMARY.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    print(json.dumps(out, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
