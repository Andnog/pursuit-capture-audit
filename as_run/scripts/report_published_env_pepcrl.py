"""Markdown and LaTeX tables of the PEPCRL-MVP real-map audit (A-137), from its summary.json."""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "experiments", "20261005_published_env_pepcrl_r01")
CELLS = [
    (f"RealMap_{s}|{arm}", f"{label} {team}")
    for s, label in (("6_3", "P6-E3"), ("7_4", "P7-E4"), ("8_5", "P8-E5"))
    for arm, team in (("null", "null"), ("greedy", "chaser"))
]


def pct(b, interval=False, tex=False):
    if b is None:
        return "--"
    sign = "\\%" if tex else " %"
    if interval:
        return f"{100 * b[0]:.1f}{sign} [{100 * b[1]:.1f}, {100 * b[2]:.1f}]"
    return f"{100 * b[0]:.1f}{sign}"


def rows(summary, tex=False):
    pub = [summary["cells"][c]["published"] for c, _ in CELLS]
    fol = [summary["cells"][c]["followup"] for c, _ in CELLS]
    unit = "\\,m" if tex else " m"

    def mark(f, dt, key, interval=False):
        m = f["marks"][f"+{dt}s"]
        v = m[key]
        if isinstance(v, list):
            return pct(v, interval, tex)
        return "--" if v is None else f"{v:.0f}{unit}"

    def bounds(p):
        lo, hi = p["success_bounds_over_scheduled"]
        return f"{100 * lo:.1f}–{100 * hi:.1f}" + ("\\%" if tex else " %")

    def distance(p):
        return f"{p['median_distance_m']:.1f}{unit}" if p["median_distance_m"] else "--"

    return [
        ("Episodes completed / scheduled", [f"{p['episodes']} / {p['scheduled']}" for p in pub]),
        ("Published success, completed episodes", [pct(p["success"], True, tex) for p in pub]),
        ("Published success, bounds over scheduled", [bounds(p) for p in pub]),
        ("At least one capture", [pct(p["any_capture"], False, tex) for p in pub]),
        (
            "Share of evaders captured",
            [pct(p["captured_share_of_evaders"], False, tex) for p in pub],
        ),
        ("Capture events", [str(p["capture_events"]) for p in pub]),
        ("same lane", [str(p["relation_counts"]["same_lane"]) for p in pub]),
        (
            "opposite directions",
            [pct(p["relation"]["opposite_direction"], False, tex) for p in pub],
        ),
        ("inside a junction", [pct(p["relation"]["junction"], False, tex) for p in pub]),
        ("different roads", [pct(p["relation"]["different_road"], False, tex) for p in pub]),
        (
            "headings differ by at least 150 deg",
            [pct(p["heading_diff_at_least_150deg"], False, tex) for p in pub],
        ),
        ("evader faster than 1 m/s", [pct(p["evader_faster_than_1mps"], False, tex) for p in pub]),
        ("median front-to-front distance", [distance(p) for p in pub]),
        ("First captures followed for 30 s", [str(f["first_captures"]) for f in fol]),
        (
            "identical to the unmodified run",
            ["{}/{}".format(*f["first_event_identical_to_published"]) for f in fol],
        ),
        ("+1 s: within 5 m of its captor", [mark(f, 1, "within_5m_of_capturer") for f in fol]),
        ("+5 s: within 5 m of its captor", [mark(f, 5, "within_5m_of_capturer") for f in fol]),
        ("+10 s: evader faster than 1 m/s", [mark(f, 10, "evader_faster_than_1mps") for f in fol]),
        (
            "+10 s: over 50 m from every pursuer",
            [mark(f, 10, "over_50m_from_every_pursuer", True) for f in fol],
        ),
        (
            "+30 s: median distance to its captor",
            [mark(f, 30, "median_dist_capturer_m") for f in fol],
        ),
        (
            "Evaders stopped at least 2 s behind one stopped pursuer",
            [pct(p["stopped_2s_share_of_evaders"], False, tex) for p in pub],
        ),
    ]


def main() -> int:
    with open(os.path.join(PACKAGE, "summary.json"), encoding="utf-8") as h:
        summary = json.load(h)
    tex = "--latex" in sys.argv
    table = rows(summary, tex)
    if tex:
        for name, values in table:
            print(f"{name} & " + " & ".join(values) + " \\\\")
    else:
        print("| | " + " | ".join(label for _, label in CELLS) + " |")
        print("|---|" + "---|" * len(CELLS))
        for name, values in table:
            print(f"| {name} | " + " | ".join(values) + " |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
