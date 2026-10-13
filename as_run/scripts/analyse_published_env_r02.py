"""Analysis of addendum r02 of the published-environment audit (A-133, R4-B). Read-only inputs.

Merges the sealed follow-up marks of r01 with the 12 completed follow-ups of r02 and reports each
mark with its denominator and an episode-level bootstrap interval; reports the stop analogue with
a time-based duration next to the earlier two-observation quantity.
"""

from __future__ import annotations

import json
import os
import random
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import audit_published_env_r02 as r02  # noqa: E402

PACKAGE = os.path.join(ROOT, "experiments", "20261005_published_env_audit_r02")
MARKS = (1, 2, 5, 10, 30)
REPS = 10000


def share(flags, seed=133):
    """[share, lo, hi, numerator, denominator] with a percentile bootstrap over episodes."""
    n = len(flags)
    if n == 0:
        return None
    rng = random.Random(seed)
    means = sorted(sum(flags[rng.randrange(n)] for _ in range(n)) / n for _ in range(REPS))
    lo, hi = means[int(0.025 * REPS)], means[int(0.975 * REPS) - 1]
    return [round(sum(flags) / n, 4), round(lo, 4), round(hi, 4), int(sum(flags)), n]


def main() -> int:
    sealed = r02.sealed_rows()
    new = {}
    with open(os.path.join(PACKAGE, "results.jsonl"), encoding="utf-8") as h:
        for line in h:
            if line.strip():
                r = json.loads(line)
                new[r["key"]] = r
    completed = {k[2:]: r for k, r in new.items() if k.startswith("F|")}
    out = {"marks": {}, "stop_analogue": {}}
    for cell in sorted({(r["scenario"], r["arm"]) for r in sealed.values()}):
        rows = [
            r
            for r in sealed.values()
            if (r["scenario"], r["arm"]) == cell
            and r["mode"] == "followup"
            and r02.first_event(r) is not None
        ]
        block = {"first_captures": len(rows)}
        for dt in MARKS:
            fs = []
            for r in rows:
                source = completed.get(r["key"], r)
                f = next((x for x in source["follow"] if x["dt"] == dt), None)
                if f is not None:
                    fs.append(f)
            block[f"+{dt}s"] = {
                "observed": len(fs),
                "within_5m_of_capturer": share([f["dist_capturer_m"] < 5.0 for f in fs]),
                "over_50m_from_every_pursuer": share([f["dist_nearest_m"] > 50.0 for f in fs]),
                "evader_faster_than_1mps": share([f["evader_speed"] > 1.0 for f in fs]),
                "median_dist_capturer_m": round(
                    statistics.median(f["dist_capturer_m"] for f in fs), 1
                ),
            }
        out["marks"]["|".join(cell)] = block
        stop = [
            r
            for k, r in new.items()
            if k.startswith("S|") and (r["scenario"], r["arm"]) == cell and "failed" not in r
        ]
        per_two = [(len(r["legacy_two_observations"]), r["n_evaders"]) for r in stop]
        per_2s = [(len(r["stopped_2s"]), r["n_evaders"]) for r in stop]
        out["stop_analogue"]["|".join(cell)] = {
            "episodes": len(stop),
            "evaders": sum(d for _, d in per_2s),
            "two_consecutive_observations": sum(n for n, _ in per_two),
            "stopped_at_least_2s_same_leader": sum(n for n, _ in per_2s),
            "share_two_observations": round(
                sum(n for n, _ in per_two) / sum(d for _, d in per_two), 4
            ),
            "share_stopped_2s": round(sum(n for n, _ in per_2s) / sum(d for _, d in per_2s), 4),
        }
    with open(os.path.join(PACKAGE, "ANALYSIS.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
    for cell, block in out["marks"].items():
        print(cell, block["first_captures"], block["+5s"]["within_5m_of_capturer"],
              block["+10s"]["over_50m_from_every_pursuer"], block["+30s"]["observed"],
              out["stop_analogue"][cell])  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
