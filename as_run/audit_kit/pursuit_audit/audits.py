"""Summaries that a pursuit study can report: rates per endpoint and their disagreement.

Episodes of one scenario are not independent, so intervals resample whole groups (for example
all team sizes and seeds of one scenario), not episodes.
"""

from __future__ import annotations

import random


def grouped_bootstrap(values_by_group: dict, reps: int = 10000, seed: int = 1, alpha: float = 0.05):
    """Mean of all values and a percentile interval obtained by resampling groups."""
    groups = sorted(values_by_group)
    flat = [x for g in groups for x in values_by_group[g]]
    if not flat:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(reps):
        sample = []
        for g in (rng.choice(groups) for _ in groups):
            sample += values_by_group[g]
        means.append(sum(sample) / len(sample))
    means.sort()
    lo, hi = means[int(alpha / 2 * reps)], means[int((1 - alpha / 2) * reps) - 1]
    return [sum(flat) / len(flat), lo, hi]


def endpoint_rates(rows: list[dict], endpoints: list[str], group_key: str = "group") -> dict:
    """Success rate of each endpoint over scored episodes, with a grouped interval."""
    out = {}
    for name in endpoints:
        by_group: dict = {}
        for row in rows:
            by_group.setdefault(row[group_key], []).append(float(bool(row[name])))
        out[name] = grouped_bootstrap(by_group)
    return out


def disagreement(rows: list[dict], lenient: str, strict: str, group_key: str = "group"):
    """Paired difference (lenient endpoint minus strict endpoint) on the same episodes."""
    by_group: dict = {}
    for row in rows:
        by_group.setdefault(row[group_key], []).append(
            float(bool(row[lenient])) - float(bool(row[strict]))
        )
    return grouped_bootstrap(by_group)
