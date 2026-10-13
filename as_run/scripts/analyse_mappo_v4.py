"""Analysis of a MAPPO-v4 package (A-143): integrity checks fixed in its protocol, and the ledger.

Reads the package only (plus the sealed MAPPO-v3 log and the sealed reconstruction of its first
batches, for the two integrity checks). Simulates nothing. Writes `ANALYSIS.json`:

- integrity: start validations against MAPPO-v3, first batches against the reconstruction, source
  hashes against `inputs.json`;
- training: per run and overall, attempted / failed / valid / used episodes, transitions, end
  reasons, exclusions, timed collisions, and what the earlier contract would have done;
- validation curves with their numerators and denominators;
- test: the registered primaries and the contrasts that the article reports, copied from
  `summary.json`, and the integrity counts of the test episodes.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experiments")
V3 = os.path.join(EXP, "20261005_mappo_v3_r01")
RECON = os.path.join(EXP, "20261005_v3_first_batch_reconstruction_r01")
ORDER = [
    "W_mlp_s1",
    "W_mlp_s2",
    "P_mlp_s1",
    "P_mlp_s2",
    "F_mlp_s1",
    "F_mlp_s2",
    "F_kan_s1",
    "F_kan_s2",
]


def jsonl(path):
    with open(path, encoding="utf-8") as h:
        return [json.loads(x) for x in h if x.strip()]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def last_per_key(rows, fields):
    """A chunk stopped between writing and saving repeats a batch: keep the last copy."""
    out = {}
    for r in rows:
        out[tuple(r[f] for f in fields)] = r
    return list(out.values())


def start_validation(log):
    v3 = {
        r["run"]: r["val"]
        for r in jsonl(os.path.join(V3, "train_log.jsonl"))
        if r["stage"] == "start"
    }
    out = {}
    for r in log:
        if r["stage"] != "start":
            continue
        num, den = r["val"]
        out[r["run"]] = {
            "v4": [num, den],
            "v3_logged": v3[r["run"]],
            "equal": abs(num / den - v3[r["run"]]) < 1e-12,
        }
    return out


def first_batches(ledger):
    recon = {}
    for r in jsonl(os.path.join(RECON, "results.jsonl")):
        recon.setdefault(r["key"].split("|")[0], []).append(r)
    out = {}
    for name in ORDER:
        mine = [
            r for r in ledger if r["run"] == name and r["phase"] == "train" and r["iteration"] == 1
        ]
        if not mine:
            continue

        def counts(rows):
            good = [r for r in rows if "failed" not in r]
            return {
                "attempted": len(rows),
                "valid": len(good),
                "success": sum(bool(r["success"]) for r in good),
                "oc": sum(bool(r["d06"]) for r in good),
                "proximity": sum(bool(r["prox_5m"]) for r in good),
                "captures": sorted(r["capture_s"] for r in good if r["capture_s"] is not None),
            }

        a, b = counts(mine), counts(recon[name])
        out[name] = {
            "v4": {k: v for k, v in a.items() if k != "captures"},
            "reconstruction_of_v3": {k: v for k, v in b.items() if k != "captures"},
            "equal": a == b,
        }
    return out


def hashes(package):
    with open(os.path.join(package, "inputs.json"), encoding="utf-8") as h:
        recorded = json.load(h)["sources"]
    changed = [f for f, d in recorded.items() if sha256(os.path.join(ROOT, f)) != d]
    return {"recorded": len(recorded), "changed": changed}


def training(ledger):
    out, total = {}, {}

    def add(target, key, value=1):
        target[key] = target.get(key, 0) + value

    for name in ORDER:
        for phase in ("warmup", "train"):
            rows = [r for r in ledger if r["run"] == name and r["phase"] == phase]
            if not rows:
                continue
            valid = [r for r in rows if r["status"] == "ok"]
            used = [r for r in valid if r["included"]]
            captured = [r for r in valid if r["d06"]]
            cell = {
                "attempted": len(rows),
                "failed": len(rows) - len(valid),
                "valid": len(valid),
                "used": len(used),
                "excluded": len(valid) - len(used),
                "transitions": sum(r["transitions"] for r in used),
                "terminal_observations_not_trained": sum(
                    r["terminal_observation_ticks"] for r in valid
                ),
                "ended_by_objective": sum(r["end_reason"] == "event" for r in valid),
                "ended_at_horizon": sum(r["end_reason"] == "horizon" for r in valid),
                "ended_by_evader_exit": sum(r["end_reason"] == "evader_exit" for r in valid),
                "episodes_with_a_collision": sum(r["collided"] for r in valid),
                "collision_inside_trained_interval": sum(r["collision_in_interval"] for r in valid),
                "collision_only_outside": sum(
                    r["collided"] and not r["collision_in_interval"] for r in valid
                ),
                "inner_gap_frames": sum(r["inner_gap_frames"] for r in valid),
                "earlier_contract_decisions": sum(r["legacy"]["ticks"] for r in valid),
                "earlier_contract_decisions_without_future": sum(
                    r["legacy"]["trained_decisions_without_future"] for r in valid
                ),
                "earlier_contract_episodes_with_such_a_decision": sum(
                    r["legacy"]["trained_decisions_without_future"] > 0 for r in valid
                ),
                "captures": len(captured),
                "captures_on_a_decision_tick": sum(r["legacy"]["capture_on_a_tick"] for r in valid),
                "earlier_capture_instant_differs": sum(
                    r["legacy"]["capture_s"] != r["capture_s"] for r in captured
                ),
            }
            cell["failure_reasons"] = {}
            for r in rows:
                if "failed" in r:
                    add(cell["failure_reasons"], r["failed"].split(":")[0])
            cell["exclusion_reasons"] = {}
            for r in valid:
                if not r["included"]:
                    add(cell["exclusion_reasons"], r.get("exclusion") or "no_decision_recorded")
            out[f"{name}|{phase}"] = cell
            for k, v in cell.items():
                if isinstance(v, int):
                    add(total, k, v)
                else:
                    for kk, vv in v.items():
                        add(total.setdefault(k, {}), kk, vv)
    return {"runs": out, "all": total}


def validation(log, val_ledger):
    curves = {}
    for r in log:
        if r["stage"] == "start":
            curves[r["run"]] = [r["val"]]
        elif r["stage"] == "validation":
            curves[r["run"]].append(r["val"])
    rows = last_per_key(val_ledger, ("run", "iteration", "key"))
    return {
        "curves": curves,
        "episodes": len(rows),
        "failed": sum(r["status"] != "ok" for r in rows),
        "failure_reasons": _count(r["failed"].split(":")[0] for r in rows if "failed" in r),
    }


def _count(values):
    out: dict[str, int] = {}
    for v in values:
        out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))


def test(package):
    with open(os.path.join(package, "summary.json"), encoding="utf-8") as h:
        s = json.load(h)
    with open(os.path.join(package, "test_integrity.json"), encoding="utf-8") as h:
        integrity = json.load(h)
    sec = s["secondary"]
    keep = [k for k in sec if "_s1_" not in k and "_s2_" not in k]
    return {
        "scheduled": s["episodes"],
        "failed": s["failed"],
        "completed": s["episodes"] - s["failed"],
        "collisions": s["collisions"],
        "selected_is_start": s["selected_is_start"],
        "primary_1": s["primary_1_W_selected_minus_start_oc"],
        "primary_2": s["primary_2_gap_P_final_minus_start"],
        "secondary": {k: sec[k] for k in keep},
        "per_seed": {k: sec[k] for k in sec if k not in keep},
        "rates": s["rates"],
        "runs": s["runs"],
        "integrity": integrity,
    }


def main() -> int:
    package = os.path.join(ROOT, sys.argv[1])
    log = jsonl(os.path.join(package, "train_log.jsonl"))
    ledger = last_per_key(
        jsonl(os.path.join(package, "train_ledger.jsonl")), ("run", "phase", "key")
    )
    out = {
        "integrity": {
            "start_validation_equals_v3": start_validation(log),
            "first_batch_equals_reconstruction": first_batches(ledger),
            "source_hashes": hashes(package)
            if os.path.exists(os.path.join(package, "inputs.json"))
            else None,
        },
        "training": training(ledger),
        "validation": validation(log, jsonl(os.path.join(package, "validation_ledger.jsonl"))),
    }
    if os.path.exists(os.path.join(package, "summary.json")):
        out["test"] = test(package)
    integ = out["integrity"]
    out["integrity"]["all_start_validations_equal"] = all(
        v["equal"] for v in integ["start_validation_equals_v3"].values()
    )
    out["integrity"]["all_first_batches_equal"] = all(
        v["equal"] for v in integ["first_batch_equals_reconstruction"].values()
    )
    with open(os.path.join(package, "ANALYSIS.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    brief = {
        "start_vals_equal": out["integrity"]["all_start_validations_equal"],
        "first_batches_equal": out["integrity"]["all_first_batches_equal"],
        "hashes_changed": (integ["source_hashes"] or {}).get("changed"),
        "training_all": {k: v for k, v in out["training"]["all"].items() if isinstance(v, int)},
    }
    if "test" in out:
        brief["p1"], brief["p2"] = out["test"]["primary_1"], out["test"]["primary_2"]
    print(json.dumps(brief, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
