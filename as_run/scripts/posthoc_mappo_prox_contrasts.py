"""Post hoc contrasts on the sealed test set of the proximity-trained MAPPO study (A-129 note).

Reads experiments/20261005_mappo_prox_r01/results.jsonl without modifying the sealed package and
writes family-clustered and city->family intervals for contrasts that the registered summary does
not report, in particular the OC-selected imitation controller minus PLB.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from addendum_reanalysis import fam_boot  # noqa: E402

SOURCE = os.path.join(ROOT, "experiments", "20261005_mappo_prox_r01", "results.jsonl")
OUT = os.path.join(ROOT, "experiments", "20261005_mappo_prox_posthoc_r01")
CONTRASTS = [
    ("d06", "mappo_oc", "planner_c215"),
    ("d06", "planner_c215", "pursuit"),
    ("prox_5m", "planner_c215", "pursuit"),
    ("d06", "proxlast_mlp_s1", "pursuit"),
    ("d06", "proxlast_mlp_s2", "pursuit"),
]


def cell_means(path):
    cell = {}
    with open(path, encoding="utf-8") as h:
        for line in h:
            r = json.loads(line)
            if not r["key"].startswith("test|") or "failed" in r:
                continue
            _, p, m, i, _seed, level, team = r["key"].split("|")
            for f in ("d06", "prox_5m"):
                cell.setdefault((f, p, m, int(i), level, int(team)), []).append(float(r[f]))
    return {k: sum(v) / len(v) for k, v in cell.items()}


def contrast(mean, field, a, b):
    fams = {}
    for k, v in mean.items():
        other = (field, b) + k[2:]
        if k[0] == field and k[1] == a and other in mean:
            fams.setdefault(k[2:5], []).append(v - mean[other])
    return {
        "families": len(fams),
        "family_95": fam_boot(fams),
        "city_family_95": fam_boot(fams, two_stage=True),
    }


def main() -> int:
    mean = cell_means(SOURCE)
    out = {
        "status": "post hoc; not registered",
        "source": "experiments/20261005_mappo_prox_r01/results.jsonl",
        "contrasts": {f"{f}:{a}_minus_{b}": contrast(mean, f, a, b) for f, a, b in CONTRASTS},
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "POSTHOC.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    print(json.dumps(out["contrasts"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
