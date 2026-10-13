"""Build the data of the web site from traces and from the sealed records.

    uv run python tools/build_site_data.py

It writes, under `docs/assets/data/`:

- one JSON file per episode shown in the animations: positions, and for every frame the state of
  each condition of the operational capture rule, computed by the library;
- `results.json` and the tables of `docs/generated/`: rates and contrasts of the two held-out
  evaluations, computed by the library from the per-episode records.

Nothing here is typed by hand: every number of the site comes from a sealed package or from a
trace, through `pursuit_audit`.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pursuit_audit as pa  # noqa: E402
from pursuit_audit.endpoints.specification import PairState  # noqa: E402
from pursuit_audit.evidence.package import EvidencePackage  # noqa: E402
from pursuit_audit.reporting.headline import (  # noqa: E402
    ALL_EVADERS,
    AMBUSH,
    BODY_GAP,
    CENTRE,
    HELDOUT_B_PACKAGE,
    OC,
    OPTIMAL,
    PLB,
    PRIMARY_EVADERS,
    PURSUIT,
    TEST_PACKAGE,
    headline_checks,
)
from pursuit_audit.statistics.contrasts import cell_means, pooled_rate  # noqa: E402

DATA = os.path.join(ROOT, "docs", "assets", "data")
GENERATED = os.path.join(ROOT, "docs", "generated")
EPISODES = os.path.join(ROOT, "results", "episodes")
EXAMPLES = os.path.join(ROOT, "as_run", "audit_kit", "examples")
EXPERIMENTS = os.path.join(ROOT, "as_run", "experiments")
EVADER = "e1"
DISPLAY_STEP_S = 0.2
SYNTHETIC = {
    "passing_cars": "Two cars pass in opposite lanes at 12 m/s",
    "follower_behind": "A pursuer trails the evader at 10 m/s",
    "blocked_stop": "The evader stops behind a stopped pursuer",
}
METHOD_NAMES = {"pursuit": "pursuit", "ambush_plus": "predictive lane blocking"}
RULES = (
    pa.ProximityRule(5.0, "body"),
    pa.ProximityRule(5.0, "centre"),
    pa.ProximityRule(5.0, "front"),
)


def annotate(frames: list[pa.Frame], lanes: list[dict], title: str, kind: str) -> dict:
    """Return the display data of one episode, with the rule evaluated at every frame."""
    params = pa.CaptureParameters()
    rule = pa.contact_specification(params)
    names = [part.name for part in rule.parts]
    pursuers = sorted({v for f in frames for v in f.vehicles if v != EVADER})
    vehicles = [EVADER, *pursuers]
    step = round(frames[1].time_s - frames[0].time_s, 6)
    every = max(1, round(DISPLAY_STEP_S / step))
    runs = dict.fromkeys(pursuers, 0.0)
    started: dict[str, float | None] = dict.fromkeys(pursuers)
    out = {"times": [], "frames": [], "focus": [], "mask": [], "run": [], "gap": [], "centre": []}
    for index, frame in enumerate(frames):
        evader = frame.vehicles.get(EVADER)
        best = None
        for pursuer_id in pursuers:
            body = frame.vehicles.get(pursuer_id)
            if evader is None or body is None:
                started[pursuer_id], runs[pursuer_id] = None, 0.0
                continue
            state = PairState.measure(body, evader)
            holds = [part.first_failure(state) is None for part in rule.parts]
            if all(holds):
                if started[pursuer_id] is None:
                    started[pursuer_id] = frame.time_s
                runs[pursuer_id] = frame.time_s - started[pursuer_id]
            else:
                started[pursuer_id], runs[pursuer_id] = None, 0.0
            centre = pa.centre_distance_m(body, evader)
            # In focus: the pursuer that has held the contact longest, otherwise the nearest.
            key = (-runs[pursuer_id], state.gap_m)
            if best is None or key < best[0]:
                best = (key, pursuer_id, holds, state.gap_m, centre)
        if index % every:
            continue
        flat: list[float | None] = []
        for vehicle_id in vehicles:
            body = frame.vehicles.get(vehicle_id)
            if body is None:
                flat += [None, None, None, None]
            else:
                flat += [
                    round(body.x, 2),
                    round(body.y, 2),
                    round(body.heading_rad, 3),
                    round(body.speed_mps, 2),
                ]
        out["times"].append(round(frame.time_s, 1))
        out["frames"].append(flat)
        if best is None:
            out["focus"].append(-1)
            out["mask"].append(0)
            out["run"].append(0)
            out["gap"].append(None)
            out["centre"].append(None)
        else:
            _key, pursuer_id, holds, gap, centre = best
            out["focus"].append(vehicles.index(pursuer_id))
            out["mask"].append(sum(1 << i for i, ok in enumerate(holds) if ok))
            out["run"].append(round(runs[pursuer_id], 1))
            out["gap"].append(round(gap, 2))
            out["centre"].append(round(centre, 2))
    capture = pa.operational_capture(frames, EVADER)
    results = {
        "oc": {
            "reached": capture.captured,
            "time": capture.capture_time_s,
            "pursuer": capture.pursuer,
            "closest_failure": capture.closest_failure,
        }
    }
    for proximity_rule in RULES:
        outcome = pa.proximity(frames, EVADER, proximity_rule)
        results[proximity_rule.name] = {"reached": outcome.reached, "time": outcome.time_s}
    first = next(iter(frames[0].vehicles.values()))
    return {
        "title": title,
        "kind": kind,
        "vehicles": vehicles,
        "length": first.length_m,
        "width": first.width_m,
        "conditions": names,
        "dwell": params.dwell_s,
        "lanes": lanes,
        "results": results,
        **out,
    }


def straight_lanes(frames: list[pa.Frame]) -> list[dict]:
    """Return straight lanes under the vehicles of a synthetic trace, one per distinct ordinate."""
    xs = [v.x for f in frames for v in f.vehicles.values()]
    ys = sorted({round(v.y, 1) for f in frames for v in f.vehicles.values()})
    return [
        {"shape": [[min(xs) - 40, y], [max(xs) + 40, y]], "width": 3.2, "internal": False}
        for y in ys
    ]


def build_episodes() -> list[dict]:
    """Write one file per episode and return the index of the episodes."""
    index = []
    for name, title in SYNTHETIC.items():
        frames = pa.load_trace(os.path.join(EXAMPLES, f"{name}.jsonl"))
        data = annotate(frames, straight_lanes(frames), title, "synthetic")
        index.append(write_episode(name, data))
    for file_name in sorted(os.listdir(EPISODES)):
        if not file_name.endswith(".meta.json"):
            continue
        name = file_name[: -len(".meta.json")]
        with open(os.path.join(EPISODES, file_name), encoding="utf-8") as handle:
            meta = json.load(handle)
        with open(os.path.join(EPISODES, f"{name}.network.json"), encoding="utf-8") as handle:
            lanes = json.load(handle)["lanes"]
        frames = pa.load_trace(os.path.join(EPISODES, f"{name}.trace.jsonl"))
        city = meta["map"].split("_")[0].capitalize()
        title = (
            f"{city}, scenario {meta['scenario']}: {meta['team']} pursuers with "
            f"{METHOD_NAMES[meta['method']]}, {meta['evader'].lower()} evader"
        )
        data = annotate(frames, lanes, title, "simulated")
        if data["results"]["oc"]["reached"] != meta["operational_capture_by_the_frozen_judge"]:
            raise SystemExit(f"{name}: the library and the frozen judge disagree")
        index.append(write_episode(name, data))
    with open(os.path.join(DATA, "episodes.json"), "w", encoding="utf-8") as handle:
        json.dump(index, handle, indent=1)
    return index


def write_episode(name: str, data: dict) -> dict:
    """Write the file of one episode and return its entry in the index."""
    path = os.path.join(DATA, f"{name}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, separators=(",", ":"))
    entry = {"name": name, "title": data["title"], "kind": data["kind"], **data["results"]}
    print(f"{name}: {len(data['times'])} frames, {os.path.getsize(path) / 1e3:.0f} kB")
    return entry


def rates(package_name: str, block: str, null_block: str | None) -> dict:
    """Return the success rates of one held-out evaluation under each endpoint."""
    records = EvidencePackage(os.path.join(EXPERIMENTS, package_name)).records()
    table = {}
    for method in (PLB, AMBUSH, PURSUIT):
        table[method] = {
            field: pooled_rate(cell_means(records, field, block, method), PRIMARY_EVADERS)
            for field in (OC, BODY_GAP, CENTRE)
        }
    by_team = {}
    for evaders, label in (
        (("RANDOM",), "Random"),
        (("AVOIDANT",), "Avoidant"),
        (OPTIMAL, "Optimal"),
    ):
        for team in (3, 5, 7):
            row = {}
            for method in (PLB, AMBUSH, PURSUIT):
                cells = cell_means(records, OC, block, method)
                chosen = {c: v for c, v in cells.items() if c[3] == team}
                row[method] = pooled_rate(chosen, evaders)
            by_team[f"{label}|{team}"] = row
    null_team = None
    if null_block:
        null_team = {
            field: pooled_rate(cell_means(records, field, null_block, "null"), PRIMARY_EVADERS)
            for field in (OC, BODY_GAP, CENTRE)
        }
    all_evaders = {
        field: pooled_rate(cell_means(records, field, block, PURSUIT), ALL_EVADERS)
        for field in (OC, BODY_GAP, CENTRE)
    }
    return {
        "rates": table,
        "by_team": by_team,
        "null_team": null_team,
        "pursuit_all_evaders": all_evaders,
    }


def markdown_table(header: list[str], rows: list[list[str]]) -> str:
    """Return a Markdown table."""
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def number(value: float | None, digits: int = 3) -> str:
    """Format a rate or a difference."""
    return "–" if value is None else f"{value:.{digits}f}"


def build_results() -> None:
    """Write `results.json` and the generated tables."""
    test = rates(TEST_PACKAGE, "TX", None)
    heldout_b = rates(HELDOUT_B_PACKAGE, "HB", "HN")
    checks = headline_checks(EXPERIMENTS)
    results = {
        "test": test,
        "heldout_b": heldout_b,
        "contrasts": [
            {"label": c.label, "value": c.recomputed, "equals_sealed": c.agrees} for c in checks
        ],
    }
    with open(os.path.join(DATA, "results.json"), "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=1)
    names = {PLB: "Predictive lane blocking", AMBUSH: "Junction ambush", PURSUIT: "Pursuit"}
    for key, data in (("test", test), ("heldout_b", heldout_b)):
        rows = [
            [names[m], number(r[OC]), number(r[BODY_GAP]), number(r[CENTRE])]
            for m, r in data["rates"].items()
        ]
        if data["null_team"]:
            null = data["null_team"]
            rows.append(
                ["Team that does not pursue", number(null[OC]), number(null[BODY_GAP]),
                 number(null[CENTRE])]
            )  # fmt: skip
        header = ["Team", "Operational capture", "Body gap ≤ 5 m", "Centre distance ≤ 5 m"]
        write_generated(f"{key}_endpoints.md", markdown_table(header, rows))
        rows = [
            [label.split("|")[0], label.split("|")[1], *(number(row[m]) for m in names)]
            for label, row in data["by_team"].items()
        ]
        header = ["Evader", "Pursuers", *names.values()]
        write_generated(f"{key}_by_team.md", markdown_table(header, rows))
    rows = [
        [c.label, f"{c.recomputed[0]:+.3f}", f"[{c.recomputed[1]:.3f}, {c.recomputed[2]:.3f}]"]
        for c in checks
    ]
    write_generated("contrasts.md", markdown_table(["Contrast", "Difference", "Interval"], rows))


def write_generated(name: str, text: str) -> None:
    """Write one generated table."""
    with open(os.path.join(GENERATED, name), "w", encoding="utf-8") as handle:
        handle.write(text)


def main() -> int:
    """Build every file."""
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(GENERATED, exist_ok=True)
    build_episodes()
    build_results()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
