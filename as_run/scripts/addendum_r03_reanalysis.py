"""Analysis of audit addendum r03 (A-121). Output: ADDENDUM_R03_SUMMARY.json in the package.

AB  coordinated - independent PLB: pooled, by evader and by team; family-clustered bootstrap.
AE  active escape after capture: reproduction, escapes, attempt types, families and cities.
RC  checked-dispatch re-runs: agreement with sealed outcomes; sealed contrasts recomputed on checked
    outcomes (family-clustered).
RP  reproduction of sealed outcomes per package.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from addendum_reanalysis import fam_boot  # noqa: E402


def rows(path):
    with open(path, encoding="utf-8") as h:
        return [json.loads(x) for x in h]


def seed_mean(items):
    """[(method, city, scenario, evader, team, value)] -> seed-averaged value per cell."""
    acc = {}
    for method, m, i, lv, team, v in items:
        acc.setdefault((method, m, i, lv, team), []).append(v)
    return {k: sum(v) / len(v) for k, v in acc.items()}


def contrast(tab, a, b, levels=None, teams=None):
    fams = {}
    for k, v in tab.items():
        if k[0] != a or (levels and k[3] not in levels) or (teams and k[4] not in teams):
            continue
        kb = (b,) + k[1:]
        if kb in tab:
            fams.setdefault((k[1], k[2], k[3]), []).append(v - tab[kb])
    return fams


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    res = rows(os.path.join(package, "results.jsonl"))
    out = {}

    # AB
    items = []
    for r in res:
        if r["key"].startswith("AB|") and "failed" not in r:
            _, name, m, i, _seed, level, team = r["key"].split("|")
            items.append((name, m, int(i), level, int(team), float(r["d06"])))
    tab = seed_mean(items)
    ab = {
        "episodes": len(items),
        "failed": sum(1 for r in res if r["key"].startswith("AB|") and "failed" in r),
        "rates": {
            n: round(
                sum(v for k, v in tab.items() if k[0] == n)
                / max(1, sum(1 for k in tab if k[0] == n)),
                4,
            )
            for n in ("coord", "indep")
        },
        "primary_pooled": fam_boot(contrast(tab, "coord", "indep")),
        "by_evader": {},
        "by_team": {},
    }
    for lv in ("AVOIDANT", "RANDOM", "GOAL_DIRECTED"):
        ab["by_evader"][lv] = fam_boot(contrast(tab, "coord", "indep", levels=(lv,)))
    for t in (3, 5, 7):
        ab["by_team"][str(t)] = fam_boot(contrast(tab, "coord", "indep", teams=(t,)))
    ab["primary_passes"] = bool(ab["primary_pooled"] and ab["primary_pooled"][1] > 0)
    out["AB"] = ab

    # AE
    ae = [r for r in res if r["key"].startswith("AE|")]
    ok = [r for r in ae if "failed" not in r]
    attempts, fams, cities = {}, set(), {}
    for r in ok:
        for a, c in (r.get("attempts") or {}).items():
            attempts[a] = attempts.get(a, 0) + c
        _, _, _method, m, i, _seed, level, _team = r["key"].split("|")
        fams.add((m, i, level))
        cities[m] = cities.get(m, 0) + 1
    out["AE"] = {
        "captures": len(ae),
        "failed": len(ae) - len(ok),
        "reproduced": sum(r.get("reproduced", False) for r in ok),
        "follow_up_60": sum(
            (r.get("follow_up") or {}).get("follow_up_s", 0) >= 60 - 1e-6 for r in ok
        ),
        "escapes": sum(bool((r.get("follow_up") or {}).get("escape")) for r in ok),
        "escapes_among_reproduced": sum(
            bool((r.get("follow_up") or {}).get("escape")) for r in ok if r.get("reproduced")
        ),
        "with_lane_change_attempt": sum(
            1 for r in ok if (r.get("attempts") or {}).get("lane_change")
        ),
        "escapes_with_lane_option": sum(
            bool((r.get("follow_up") or {}).get("escape"))
            for r in ok
            if (r.get("attempts") or {}).get("lane_change")
        ),
        "escapes_without_lane_option": sum(
            bool((r.get("follow_up") or {}).get("escape"))
            for r in ok
            if not (r.get("attempts") or {}).get("lane_change")
        ),
        "escape_families": sorted(
            {
                "|".join(r["key"].split("|")[3:5] + r["key"].split("|")[6:7])
                for r in ok
                if (r.get("follow_up") or {}).get("escape")
            }
        ),
        "attempt_totals": attempts,
        "families": len(fams),
        "cities": cities,
    }

    # RC
    rc = {}
    for cohort in ("a99", "goal"):
        sel = [r for r in res if r["key"].startswith(f"RC|{cohort}|") and "failed" not in r]
        agree = sum(r["d06"] == r["sealed_d06"] for r in sel)
        per = {}
        checked, sealed = [], []
        for r in sel:
            k = r["key"].split("|")[2:]
            if cohort == "a99":
                _, method, m, i, _seed, level, team = k
            else:
                _, method, m, i, _seed, team = k
                level = "GOAL_DIRECTED"
            per.setdefault(method, [0, 0])
            per[method][0] += int(r["d06"] == r["sealed_d06"])
            per[method][1] += 1
            checked.append((method, m, int(i), level, int(team), float(r["d06"])))
            sealed.append((method, m, int(i), level, int(team), float(r["sealed_d06"])))
        tc, ts = seed_mean(checked), seed_mean(sealed)
        entry = {
            "episodes": len(sel),
            "agreement": round(agree / max(1, len(sel)), 4),
            "changed": len(sel) - agree,
            "by_method": {k: {"agree": v[0], "n": v[1]} for k, v in per.items()},
        }
        if cohort == "a99":
            ar = ("AVOIDANT", "RANDOM")
            entry["plb_minus_pursuit"] = {
                "checked": fam_boot(contrast(tc, "plus_opt", "pursuit", ar)),
                "sealed": fam_boot(contrast(ts, "plus_opt", "pursuit", ar)),
            }
            entry["plb_minus_a95"] = {
                "checked": fam_boot(contrast(tc, "plus_opt", "ambush_a95", ar)),
                "sealed": fam_boot(contrast(ts, "plus_opt", "ambush_a95", ar)),
            }
        else:
            entry["plb_minus_pursuit"] = {
                "checked": fam_boot(contrast(tc, "plus_opt", "pursuit")),
                "sealed": fam_boot(contrast(ts, "plus_opt", "pursuit")),
            }
        rc[cohort] = entry
    out["RC"] = rc

    # RP
    rp = {}
    for r in res:
        if not r["key"].startswith("RP|"):
            continue
        pkg = r["key"].split("|")[1]
        d = rp.setdefault(pkg, {"n": 0, "failed": 0, "reproduced": 0})
        if "failed" in r:
            d["failed"] += 1
            continue
        d["n"] += 1
        d["reproduced"] += int(r["d06"] == r["sealed_d06"])
    out["RP"] = rp
    with open(os.path.join(package, "ADDENDUM_R03_SUMMARY.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
