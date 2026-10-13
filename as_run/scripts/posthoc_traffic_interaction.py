"""Post hoc: is the PLB advantage with traffic different from the advantage without? (A-133, R4-C)

Reads the sealed kinematic (arm K0) and traffic packages and computes, per cell, the difference of
differences (PLB - pursuit with traffic) - (PLB - pursuit without), with family-clustered and
city -> family intervals. Nothing sealed is modified.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import run_kinematic_sensitivity as ks  # noqa: E402
from addendum_reanalysis import fam_boot  # noqa: E402

EXP = os.path.join(ROOT, "experiments")
OUT = os.path.join(EXP, "20261005_traffic_interaction_posthoc_r01")


def rows(package, prefix):
    out = {}
    with open(os.path.join(EXP, package, "results.jsonl"), encoding="utf-8") as h:
        for line in h:
            r = json.loads(line)
            if r["key"].startswith(prefix):
                out[r["key"]] = r
    return out


def interaction(d06):
    """{family: [difference of differences per cell]} from seed-averaged OC cell means."""

    def sub(variant, method):
        return {k[2:]: v for k, v in d06.items() if k[:2] == (variant, method)}

    kt_plb, kt_pur = sub("KT", "plus_opt"), sub("KT", "pursuit")
    k0_plb, k0_pur = sub("K0", "plus_opt"), sub("K0", "pursuit")
    fams = {}
    for k in sorted(set(kt_plb) & set(kt_pur) & set(k0_plb) & set(k0_pur)):
        fams.setdefault(k[:3], []).append((kt_plb[k] - kt_pur[k]) - (k0_plb[k] - k0_pur[k]))
    return fams


def main() -> int:
    both = rows("20261005_kinematic_sensitivity_r01", "K|K0|")
    both.update(rows("20261005_traffic_sensitivity_r01", "K|KT|"))
    fams = interaction(ks.cell_means(both, "d06"))
    out = {
        "status": "post hoc; not registered",
        "quantity": "(PLB - pursuit with traffic) - (PLB - pursuit without traffic), OC",
        "families": len(fams),
        "cells": sum(len(v) for v in fams.values()),
        "family_95": fam_boot(fams),
        "city_family_95": fam_boot(fams, two_stage=True),
    }
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "POSTHOC.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
