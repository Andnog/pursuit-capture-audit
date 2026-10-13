"""Summary of the published-environment capture audit (A-126, stage A). Descriptive.

Reads results.jsonl of the package and writes summary.json. Intervals are percentile bootstraps
over episodes (each episode contributes all of its capture events).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPS = 10000
RELATIONS = ("same_lane", "opposite_direction", "junction", "different_road")


def boot(per_episode, reps=REPS, seed=126):
    """per_episode: [(numerator, denominator)] per episode. Ratio of sums with a 95 % interval."""
    den = sum(d for _, d in per_episode)
    if not per_episode or den == 0:
        return None
    rng = random.Random(seed)
    n = len(per_episode)
    vals = []
    for _ in range(reps):
        a = b = 0.0
        for _ in range(n):
            x, y = per_episode[rng.randrange(n)]
            a += x
            b += y
        if b > 0:
            vals.append(a / b)
    vals.sort()
    lo, hi = vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]
    return [round(sum(x for x, _ in per_episode) / den, 4), round(lo, 4), round(hi, 4)]


def load(package):
    rows = {}
    with open(os.path.join(package, "results.jsonl"), encoding="utf-8") as h:
        for line in h:
            if line.strip():
                r = json.loads(line)
                rows[r["key"]] = r
    return rows


def events_ok(r):
    return [e for e in r.get("events", []) if "error" not in e]


def published_block(rows):
    ok = [r for r in rows if "failed" not in r]
    out = {
        "episodes": len(ok),
        "failed": len(rows) - len(ok),
        "success": boot([(float(r["success"]), 1.0) for r in ok]),
        "captured_share_of_evaders": boot(
            [(float(r["captured"]), float(r["n_evaders"])) for r in ok]
        ),
        "mean_steps": round(statistics.mean(r["steps"] for r in ok), 1) if ok else None,
        "any_capture": boot([(float(r["captured"] > 0), 1.0) for r in ok]),
        "stop_analogue_share_of_evaders": boot(
            [(float(len(r["stop_analogue"])), float(r["n_evaders"])) for r in ok]
        ),
    }
    per = [events_ok(r) for r in ok]
    n_events = sum(len(e) for e in per)
    out["capture_events"] = n_events
    out["event_read_errors"] = sum(len(r.get("events", [])) for r in ok) - n_events

    def share(pred):
        return boot([(float(sum(pred(e) for e in ev)), float(len(ev))) for ev in per if ev])

    out["relation"] = {rel: share(lambda e, rel=rel: e["relation"] == rel) for rel in RELATIONS}
    out["evader_faster_than_1mps"] = share(lambda e: e["evader_speed"] > 1.0)
    out["heading_diff_at_least_150deg"] = share(lambda e: e["heading_diff_deg"] >= 150.0)
    out["heading_diff_at_most_15deg"] = share(lambda e: e["heading_diff_deg"] <= 15.0)
    out["stop_compatible"] = share(lambda e: e["stop_compatible"])
    out["same_lane_pursuer_ahead"] = share(
        lambda e: e["relation"] == "same_lane" and e["pursuer_ahead"]
    )
    flat = [e for ev in per for e in ev]
    if flat:
        out["median_evader_speed"] = round(statistics.median(e["evader_speed"] for e in flat), 2)
        out["median_pursuer_speed"] = round(statistics.median(e["pursuer_speed"] for e in flat), 2)
        out["median_distance_m"] = round(statistics.median(e["distance_m"] for e in flat), 2)
    return out


def followup_block(rows, published):
    ok = [r for r in rows if "failed" not in r and events_ok(r)]
    out = {"episodes_with_a_capture": len(ok), "failed": sum("failed" in r for r in rows)}
    same = checked = 0
    for r in ok:
        twin = published.get(r["key"].replace("|followup|", "|published|"))
        if twin is None or "failed" in twin or not events_ok(twin):
            continue
        a = min(events_ok(r), key=lambda e: e["step"])
        b = min(events_ok(twin), key=lambda e: e["step"])
        checked += 1
        same += (a["step"], a["evader"], a["pursuer"]) == (b["step"], b["evader"], b["pursuer"])
    out["first_event_identical_to_published"] = [same, checked]
    marks = {}
    for dt in (1, 2, 5, 10, 30):
        fs = [next((f for f in r["follow"] if f["dt"] == dt), None) for r in ok]
        fs = [f for f in fs if f is not None]
        if not fs:
            continue
        marks[f"+{dt}s"] = {
            "n": len(fs),
            "evader_faster_than_1mps": boot([(float(f["evader_speed"] > 1.0), 1.0) for f in fs]),
            "over_50m_from_every_pursuer": boot(
                [(float(f["dist_nearest_m"] > 50.0), 1.0) for f in fs]
            ),
            "within_5m_of_capturer": boot([(float(f["dist_capturer_m"] < 5.0), 1.0) for f in fs]),
            "median_dist_capturer_m": round(statistics.median(f["dist_capturer_m"] for f in fs), 1),
            "median_dist_nearest_m": round(statistics.median(f["dist_nearest_m"] for f in fs), 1),
            "median_evader_speed": round(statistics.median(f["evader_speed"] for f in fs), 2),
        }
    out["marks"] = marks
    return out


def summarise(package, write=True):
    rows = load(package)
    out = {"rows": len(rows), "failed": sum("failed" in r for r in rows.values()), "cells": {}}
    for scenario in sorted({r["scenario"] for r in rows.values()}):
        for arm in ("null", "greedy"):
            sel = [r for r in rows.values() if r["scenario"] == scenario and r["arm"] == arm]
            pub = [r for r in sel if r["mode"] == "published"]
            fol = [r for r in sel if r["mode"] == "followup"]
            out["cells"][f"{scenario}|{arm}"] = {
                "published": published_block(pub),
                "followup": followup_block(fol, rows),
            }
    if write:
        with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
            json.dump(out, h, indent=2)
    return out


def latex_rows(out):
    """Rows of the supplement table: both scenarios and both teams, from the summary."""
    cells = [
        f"{sc}|{arm}" for sc in ("3x3Traffic_4_2", "3x3Traffic_7_4") for arm in ("null", "greedy")
    ]
    pub = [out["cells"][c]["published"] for c in cells]
    fol = [out["cells"][c]["followup"] for c in cells]

    def pct(b, interval=False):
        if b is None:
            return "--"
        if interval:
            return f"{100 * b[0]:.1f}\\% [{100 * b[1]:.1f}, {100 * b[2]:.1f}]"
        return f"{100 * b[0]:.1f}\\%"

    def mark(f, dt, key, interval=False):
        m = f["marks"].get(f"+{dt}s")
        if m is None:
            return "--"
        return pct(m[key], interval) if isinstance(m[key], list) else f"{m[key]:.0f}\\,m"

    rows = [
        ("Episodes", [str(p["episodes"]) for p in pub]),
        ("Published success", [pct(p["success"], True) for p in pub]),
        ("At least one capture", [pct(p["any_capture"]) for p in pub]),
        ("Share of evaders captured", [pct(p["captured_share_of_evaders"]) for p in pub]),
        ("Mean steps", [f"{p['mean_steps']:.0f}" for p in pub]),
        ("Capture events", [str(p["capture_events"]) for p in pub]),
        ("\\quad same lane", [pct(p["relation"]["same_lane"]) for p in pub]),
        ("\\quad opposite directions", [pct(p["relation"]["opposite_direction"]) for p in pub]),
        ("\\quad inside a junction", [pct(p["relation"]["junction"]) for p in pub]),
        (
            "\\quad headings differ by $\\ge150^\\circ$",
            [pct(p["heading_diff_at_least_150deg"]) for p in pub],
        ),
        ("\\quad evader faster than 1\\,m/s", [pct(p["evader_faster_than_1mps"]) for p in pub]),
        (
            "\\quad median front-to-front distance",
            [f"{p['median_distance_m']:.1f}\\,m" for p in pub],
        ),
        ("First captures followed", [str(f["episodes_with_a_capture"]) for f in fol]),
        (
            "\\quad identical to the unmodified run",
            ["{}/{}".format(*f["first_event_identical_to_published"]) for f in fol],
        ),
        (
            "\\quad $+1$\\,s: within 5\\,m of its captor",
            [mark(f, 1, "within_5m_of_capturer") for f in fol],
        ),
        (
            "\\quad $+5$\\,s: within 5\\,m of its captor",
            [mark(f, 5, "within_5m_of_capturer") for f in fol],
        ),
        (
            "\\quad $+10$\\,s: evader faster than 1\\,m/s",
            [mark(f, 10, "evader_faster_than_1mps") for f in fol],
        ),
        (
            "\\quad $+10$\\,s: over 50\\,m from every pursuer",
            [mark(f, 10, "over_50m_from_every_pursuer", True) for f in fol],
        ),
        (
            "\\quad $+30$\\,s: median distance to its captor",
            [mark(f, 30, "median_dist_capturer_m") for f in fol],
        ),
        (
            "Evaders stopped 2\\,s behind a stopped pursuer",
            [pct(p["stop_analogue_share_of_evaders"]) for p in pub],
        ),
    ]
    return "\n".join(f"{name} & " + " & ".join(v) + " \\\\" for name, v in rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--interim", action="store_true", help="print only; do not write summary")
    parser.add_argument("--latex", action="store_true", help="print the supplement table rows")
    args = parser.parse_args()
    out = summarise(os.path.join(ROOT, args.package), write=not args.interim)
    if args.latex:
        print(latex_rows(out))
        return 0
    for cell, block in out["cells"].items():
        p, f = block["published"], block["followup"]
        print(
            cell, "episodes", p["episodes"], "success", p["success"], "events", p["capture_events"]
        )
        print("   relation", {k: (v[0] if v else None) for k, v in p["relation"].items()})
        print(
            "   evader>1m/s", p["evader_faster_than_1mps"], "stop-compatible", p["stop_compatible"]
        )
        print("   follow", f["first_event_identical_to_published"], f["marks"].get("+10s"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
