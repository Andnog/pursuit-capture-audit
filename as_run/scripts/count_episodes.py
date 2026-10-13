"""Reproducible count of the simulations behind the article (A-133, R4-C).

Every record of every package used by the article is assigned to one category by an explicit rule:
- evaluation: an episode run to estimate a rate or a contrast that the article reports;
- selection: an episode used to choose parameters or candidates (search rungs, search validation);
- replay: a re-run of an earlier episode for an audit (follow-up, hold, bookkeeping, reproduction,
  including the replay of sealed training episodes to audit a training loop);
- failed: a scheduled task that produced no episode (almost always a placement failure).
Episodes generated while training a learner, validation during training, and development checks
are not in these files and are not counted. Writes `provenance/EPISODE_COUNTS.json`.
"""

from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experiments")

E, S, R = "evaluation", "selection", "replay"
# (package, file, rule). A rule is a category for every record, or {key prefix: category}.
RULES = [
    ("20261001_endpoint_validation_r01", "endpoint.jsonl", E),
    ("20261001_endpoint_validation_r01", "audit.jsonl", R),
    ("20261001_final_study_r01", "run.jsonl", E),
    ("20261001_final_study_r01", "audit.jsonl", R),
    ("20261001_robustness_study_r01", "results.jsonl", E),
    ("20261001_ambush_study_r01", "results.jsonl", E),
    ("20261001_ambush_learning_r01", "test.jsonl", E),
    ("20261002_ambush_optimization_r01", "results.jsonl", {"test": E, "g": S, "val": S}),
    ("20261002_sensitivity_r02", "results.jsonl", {"SP": E, "T7": E, "s7": S, "v7": S}),
    ("20261002_mappo_r01", "results.jsonl", {"test": E}),
    ("20261003_commitment_r01", "results.jsonl", {"C": E}),
    ("20261003_d06_persistence_audit_r01", "results.jsonl", R),
    (
        "20261003_test_confirmation_r01",
        "results.jsonl",
        {"TX": E, "TS": E, "OX": E, "OS": E, "CA": R},
    ),
    ("20261003_goal_evader_r01", "results.jsonl", {"GD": E, "GS": E}),
    (
        "20261004_audit_addendum_r01",
        "results.jsonl",
        {"B3": E, "B1": R, "B2F": R, "B2T": R, "B6": R},
    ),
    ("20261004_mappo_v2_r01", "results.jsonl", {"test": E}),
    ("20261004_audit_addendum_r02", "results.jsonl", R),
    ("20261004_audit_addendum_r03", "results.jsonl", {"AB": E, "AE": R, "RC": R, "RP": R}),
    ("20261004_mechanism_diagnostics_r01", "results.jsonl", {"M1": E, "M2": R}),
    ("20261005_mappo_prox_r01", "results.jsonl", {"test": E}),
    ("20261005_kinematic_sensitivity_r01", "results.jsonl", {"K": E}),
    ("20261005_traffic_sensitivity_r01", "results.jsonl", {"K": E}),
    ("20261005_tuned_evader_r01", "results.jsonl", {"T": E, "R1": S, "R2": S}),
    ("20261005_mappo_v3_r01", "results.jsonl", {"test": E}),
    ("20261005_heldout_b_r01", "results.jsonl", {"HB": E, "HN": E}),
    ("20261005_capture_instant_scan_r01", "results.jsonl", R),
    ("20261005_v3_first_batch_reconstruction_r01", "results.jsonl", R),
    ("20261006_mappo_v4_r01", "results.jsonl", {"test": E}),
]
THIRD_PARTY = [
    ("20261005_published_env_audit_r01", "results.jsonl", E),
    ("20261005_published_env_audit_r02", "results.jsonl", R),
    # A-137: the mode is a field of the record (key: scenario|team|mode|index).
    (
        "20261005_published_env_pepcrl_r01",
        "results.jsonl",
        {"mode:published": E, "mode:followup": R},
    ),
]


def category(rule, record):
    if isinstance(rule, str):
        return rule
    if all(k.startswith("mode:") for k in rule):
        return rule[f"mode:{record['mode']}"]
    key = str(record.get("key", ""))
    prefix = key.split("|")[0]
    for start in sorted(rule, key=len, reverse=True):
        if prefix == start or (start in ("g", "s7") and prefix.startswith(start)):
            return rule[start]
    raise KeyError(f"no rule for record key {key!r}")


def count(rules):
    per_package, total = {}, {E: 0, S: 0, R: 0, "failed": 0}
    for package, name, rule in rules:
        path = os.path.join(EXP, package, name)
        if not os.path.isfile(path):
            continue
        block = per_package.setdefault(package, {E: 0, S: 0, R: 0, "failed": 0})
        with open(path, encoding="utf-8") as h:
            for line in h:
                if not line.strip():
                    continue
                record = json.loads(line)
                cat = "failed" if "failed" in record else category(rule, record)
                block[cat] += 1
                total[cat] += 1
    return per_package, total


def main() -> int:
    own, own_total = count(RULES)
    third, third_total = count(THIRD_PARTY)
    out = {
        "rule": __doc__.strip().split("\n\n")[1] if "\n\n" in __doc__ else "",
        "own_setting": {"total": own_total, "packages": own},
        "third_party_environment": {"total": third_total, "packages": third},
    }
    with open(os.path.join(ROOT, "provenance", "EPISODE_COUNTS.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1)
    print(json.dumps({"own": own_total, "third_party": third_total}))
    for package, block in own.items():
        print(f"  {package:42s} {block}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
