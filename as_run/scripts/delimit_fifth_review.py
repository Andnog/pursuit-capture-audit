"""Offline delimitation of the fifth review's findings from sealed packages (A-139; post hoc).

Reads sealed logs and results only; simulates nothing. For each learning package it reports what
the retained records can and cannot reconstruct:

- denominators of every training iteration of MAPPO-v3, recovered from the three rounded rates that
  the log stores (candidate denominators consistent with all three);
- the number of sampled episodes that did not reach the training objective, which is the number of
  episodes whose last trained decision had no future under the earlier contract (upper bound);
- capture instants of the MAPPO-v2 test rows, which were stored: the share that falls on a 3 s
  decision tick;
- collisions in the sealed test rows of every learning package;
- the arithmetic of the MAPPO-v3 test schedule (erratum of its protocol).
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experiments")
BATCH = 64


def rows(package, name="results.jsonl"):
    with open(os.path.join(EXP, package, name), encoding="utf-8") as h:
        return [json.loads(x) for x in h]


def candidates(rates, batch=BATCH):
    """Denominators n <= batch such that every rounded rate is round(k / n, 3) for an integer k."""
    out = []
    for n in range(1, batch + 1):
        if all(any(round(k / n, 3) == r for k in range(n + 1)) for r in rates):
            out.append(n)
    return out


def numerator(rate, n):
    return next(k for k in range(n + 1) if round(k / n, 3) == rate)


def v3_training():
    log = rows("20261005_mappo_v3_r01", "train_log.jsonl")
    runs: dict[str, dict] = {}
    for r in log:
        if r.get("stage") != "mappo":
            continue
        cand = candidates([r["success"], r["oc"], r["prox"]])
        run = runs.setdefault(
            r["run"],
            {
                "iterations": 0,
                "attempted": 0,
                "unique_denominator": 0,
                "valid_min": 0,
                "valid_max": 0,
                "without_objective_min": 0,
                "without_objective_max": 0,
            },
        )
        run["iterations"] += 1
        run["attempted"] += BATCH
        run["unique_denominator"] += len(cand) == 1
        run["valid_min"] += min(cand)
        run["valid_max"] += max(cand)
        miss = [n - numerator(r["success"], n) for n in cand]
        run["without_objective_min"] += min(miss)
        run["without_objective_max"] += max(miss)
    total = {k: sum(r[k] for r in runs.values()) for k in next(iter(runs.values()))}
    return {"runs": runs, "all_runs": total}


def capture_on_tick():
    """MAPPO-v2 test rows store the capture instant. Decisions are taken every 3 s from 0 s."""
    out = {}
    for r in rows("20261004_mappo_v2_r01"):
        if "failed" in r or r.get("capture_t") is None:
            continue
        policy = r["key"].split("|")[1]
        kind = (
            "learned (3 s decisions)" if policy.startswith(("v2_", "old_", "teacher")) else policy
        )
        cell = out.setdefault(kind, {"captures": 0, "on_a_tick": 0})
        cell["captures"] += 1
        cell["on_a_tick"] += abs(r["capture_t"] / 3.0 - round(r["capture_t"] / 3.0)) < 1e-6
    for cell in out.values():
        cell["share"] = round(cell["on_a_tick"] / cell["captures"], 4)
    return out


def collisions():
    out = {}
    for package in (
        "20261002_mappo_r01",
        "20261004_mappo_v2_r01",
        "20261005_mappo_prox_r01",
        "20261005_mappo_v3_r01",
    ):
        good = [r for r in rows(package) if r["key"].startswith("test|") and "failed" not in r]
        out[package] = {
            "completed_test_rows": len(good),
            "with_collision_flag": sum(bool(r.get("collided")) for r in good),
            "rows_without_the_flag": sum("collided" not in r for r in good),
        }
    return out


def schedule():
    cities, scenarios, sumo_seeds, evaders, teams, policies = 7, 20, 2, 2, 3, 14
    per_policy = cities * scenarios * sumo_seeds * evaders * teams
    test = [r for r in rows("20261005_mappo_v3_r01") if r["key"].startswith("test|")]
    by_policy: dict[str, int] = {}
    for r in test:
        p = r["key"].split("|")[1]
        by_policy[p] = by_policy.get(p, 0) + 1
    return {
        "factors": "7 cities x 20 scenarios x 2 SUMO seeds x 2 evaders x 3 team sizes",
        "scheduled_per_policy": per_policy,
        "protocol_text_says": 840,
        "policies": policies,
        "scheduled_total": per_policy * policies,
        "rows_in_the_sealed_package": len(test),
        "rows_per_policy_in_the_sealed_package": sorted(set(by_policy.values())),
        "completed_per_policy": sorted(
            {
                sum(1 for r in test if r["key"].split("|")[1] == p and "failed" not in r)
                for p in by_policy
            }
        ),
    }


def main() -> int:
    out = {
        "v3_training_from_the_sealed_log": v3_training(),
        "capture_on_a_decision_tick_v2_test": capture_on_tick(),
        "collisions_in_sealed_test_rows": collisions(),
        "v3_test_schedule": schedule(),
    }
    target = sys.argv[1] if len(sys.argv) > 1 else None
    text = json.dumps(out, indent=2)
    if target:
        os.makedirs(os.path.join(ROOT, target), exist_ok=True)
        with open(os.path.join(ROOT, target, "DELIMITATION.json"), "w", encoding="utf-8") as h:
            h.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
