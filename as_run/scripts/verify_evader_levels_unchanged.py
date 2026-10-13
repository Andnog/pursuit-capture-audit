"""Development check for A-127 E: the four existing evader levels behave as before.

Re-runs a fixed sample of already recorded episodes and compares outcomes:
- OPTIMAL_ESCAPE: block OX of the test-confirmation package (non-TEST cities), legacy dispatch;
- GOAL_DIRECTED: the goal-evader package, legacy dispatch;
- AVOIDANT and RANDOM: K0 rows of the kinematic-sensitivity package, checked dispatch.

Run once before and once after the evader source changes. The sample is written on the first run
and reused, so both runs compare the same episodes. Not gated; no TEST city is used.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from run_ambush_optimization import _init  # noqa: E402

EXP = os.path.join(ROOT, "experiments")
FIELDS = ("d06", "prox_5m", "prox_5m_centre")


def _rows(path, prefix):
    out = []
    with open(path, encoding="utf-8") as h:
        for line in h:
            r = json.loads(line)
            if r["key"].startswith(prefix) and "failed" not in r:
                out.append(r)
    return sorted(out, key=lambda r: r["key"])


def build_sample():
    rng = random.Random(127)
    ox = [
        r
        for r in _rows(os.path.join(EXP, "20261003_test_confirmation_r01", "results.jsonl"), "OX|")
        if r["key"].split("|")[1] in ("plus_opt", "pursuit")
    ]
    gd = _rows(os.path.join(EXP, "20261003_goal_evader_r01", "results.jsonl"), "GD|")
    k0 = _rows(os.path.join(EXP, "20261005_kinematic_sensitivity_r01", "results.jsonl"), "K|K0|")
    sample = []
    for name, rows, n in (("OX", ox, 40), ("GD", gd, 40), ("K0", k0, 60)):
        for r in rng.sample(rows, n):
            sample.append(
                {"block": name, "key": r["key"], "recorded": {f: r[f] for f in FIELDS if f in r}}
            )
    return sample


def rerun(item):
    import joint_interception.native.engine as engine

    key, block = item["key"], item["block"]
    p = key.split("|")
    engine.DISPATCH_MODE = "checked" if block == "K0" else "legacy"
    try:
        if block == "OX":
            from run_test_confirmation import episode

            _, method, m, i, seed, level, team = p
            r = episode((key, m, int(i), int(seed), "PE15", level, int(team), method, None))
        elif block == "GD":
            from run_goal_evader_study import episode

            _, method, m, i, seed, team = p
            r = episode((key, m, int(i), int(seed), int(team), method, None))
        else:
            from run_kinematic_sensitivity import episode

            _, variant, method, m, i, seed, level, team = p
            r = episode((key, m, int(i), int(seed), level, int(team), method, variant))
    finally:
        engine.DISPATCH_MODE = "checked"
    if "failed" in r:
        return {"key": key, "block": block, "failed": r["failed"]}
    now = {f: r[f] for f in item["recorded"]}
    return {"key": key, "block": block, "same": now == item["recorded"], "now": now}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--label", required=True, help="before or after")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    sample_path = os.path.join(package, "LEVELS_CHECK_SAMPLE.json")
    if os.path.exists(sample_path):
        with open(sample_path, encoding="utf-8") as h:
            sample = json.load(h)
    else:
        sample = build_sample()
        with open(sample_path, "w", encoding="utf-8") as h:
            json.dump(sample, h, indent=1)
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        res = pool.map(rerun, sample, chunksize=1)
    out = {"label": args.label, "blocks": {}}
    for block in ("OX", "GD", "K0"):
        rs = [r for r in res if r["block"] == block]
        out["blocks"][block] = {
            "episodes": len(rs),
            "failed": sum("failed" in r for r in rs),
            "same": sum(r.get("same", False) for r in rs),
            "different": [r["key"] for r in rs if r.get("same") is False],
        }
    with open(os.path.join(package, f"LEVELS_CHECK_{args.label}.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
