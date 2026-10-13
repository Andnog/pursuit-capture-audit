"""Post hoc comparison of the two held-out evaluations (TEST, A-110; HELD-OUT B, A-138).

Written after both results were read. Descriptive: it asks whether the two estimates differ by more
than sampling error, and lists the eight cities. It does not pool the two sets and runs no episode.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from addendum_reanalysis import fam_boot  # noqa: E402
from run_heldout_b import PRIMARY_LEVELS, cell_means, paired  # noqa: E402

SETS = {
    "TEST": ("experiments/20261003_test_confirmation_r01", "TX"),
    "HELDOUT_B": ("experiments/20261005_heldout_b_r01", "HB"),
}
CONTRASTS = {
    "plb_minus_pursuit_oc": ("d06", "plus_opt", "d06", "pursuit"),
    "plb_minus_ambush_oc": ("d06", "plus_opt", "d06", "ambush_a95"),
    "body_gap_5m_minus_oc_pursuit": ("prox_5m", "pursuit", "d06", "pursuit"),
    "plb_minus_pursuit_body_gap_5m": ("prox_5m", "plus_opt", "prox_5m", "pursuit"),
}
REPS = 10000


def load(package, block):
    rows = {}
    with open(os.path.join(ROOT, package, "results.jsonl"), encoding="utf-8") as h:
        for line in h:
            r = json.loads(line)
            if r["key"].startswith(block + "|"):
                rows[r["key"]] = r
    return rows


def families(rows, block, spec, levels=PRIMARY_LEVELS, city=None):
    fa, ma, fb, mb = spec
    ta, tb = cell_means(rows, fa), cell_means(rows, fb)
    a = {k[2:]: v for k, v in ta.items() if k[:2] == (block, ma)}
    b = {k[2:]: v for k, v in tb.items() if k[:2] == (block, mb)}
    return paired(a, b, levels=levels, city=city)


def _draws(fams, rng, reps):
    keys = sorted(fams)
    out = []
    for _ in range(reps):
        xs = []
        for k in (rng.choice(keys) for _ in keys):
            xs += fams[k]
        out.append(sum(xs) / len(xs))
    return out


def difference(fa, fb, seed=17, reps=REPS):
    """Independent family bootstraps of two sets; percentile interval of mean(a) - mean(b)."""
    rng = random.Random(seed)
    d = sorted(x - y for x, y in zip(_draws(fa, rng, reps), _draws(fb, rng, reps), strict=True))
    obs = sum(x for v in fa.values() for x in v) / sum(len(v) for v in fa.values()) - sum(
        x for v in fb.values() for x in v
    ) / sum(len(v) for v in fb.values())
    return [round(obs, 4), round(d[int(0.025 * reps)], 4), round(d[int(0.975 * reps) - 1], 4)]


def rate(rows, block, method, field, city=None):
    t = cell_means(rows, field)
    v = [
        x
        for k, x in t.items()
        if k[:2] == (block, method) and city in (None, k[2]) and k[4] in PRIMARY_LEVELS
    ]
    return round(sum(v) / len(v), 4) if v else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    args = ap.parse_args()
    data = {name: load(*spec) for name, spec in SETS.items()}
    out = {"post_hoc": True, "reps": REPS, "rates": {}, "contrasts": {}, "cities": {}}
    for s, (_package, block) in SETS.items():
        out["rates"][s] = {
            m: {f: rate(data[s], block, m, f) for f in ("d06", "prox_5m", "prox_5m_centre")}
            for m in ("plus_opt", "ambush_a95", "pursuit")
        }
    for name, spec in CONTRASTS.items():
        f = {s: families(data[s], SETS[s][1], spec) for s in SETS}
        out["contrasts"][name] = {
            "TEST_family_95": fam_boot(f["TEST"]),
            "HELDOUT_B_family_95": fam_boot(f["HELDOUT_B"]),
            "TEST_minus_HELDOUT_B_95": difference(f["TEST"], f["HELDOUT_B"]),
            "families": {s: len(f[s]) for s in SETS},
        }
    for s, (_package, block) in SETS.items():
        for city in sorted({k.split("|")[2] for k in data[s]}):
            fams = families(data[s], block, CONTRASTS["plb_minus_pursuit_oc"], city=city)
            out["cities"][city] = {
                "set": s,
                "families": len(fams),
                "pursuit_oc": rate(data[s], block, "pursuit", "d06", city),
                "plb_oc": rate(data[s], block, "plus_opt", "d06", city),
                "pursuit_body_gap_5m": rate(data[s], block, "pursuit", "prox_5m", city),
                "plb_minus_pursuit_oc_family_95": fam_boot(fams),
            }
    est = [c["plb_minus_pursuit_oc_family_95"][0] for c in out["cities"].values()]
    out["cities_with_positive_estimate"] = [sum(e > 0 for e in est), len(est)]
    with open(os.path.join(ROOT, args.package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
