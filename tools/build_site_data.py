"""Build the data of the web site from traces and from the sealed records.

    uv run python tools/build_site_data.py

It writes, under `docs/assets/data/`:

- one JSON file per episode shown in the animations: positions, and for every frame the state of
  each condition of the operational capture rule, computed by the library;
- `charts.json`: the chart data and dynamic numerical labels. The rates and the contrasts of the
  two held-out evaluations are computed by the library from the per-episode records; the others
  are read from the sealed summaries.

The generated numerical data come from sealed packages or traces through `pursuit_audit`.
Editorial prose separately states study counts, rounded results and limits with source links.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from build_results import sealed_values  # noqa: E402

import pursuit_audit as pa  # noqa: E402
from pursuit_audit.endpoints.specification import PairState  # noqa: E402
from pursuit_audit.evidence.inventory import load_inventory  # noqa: E402
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


def sealed_json(package: str, name: str) -> dict:
    """Return a sealed JSON file of a package."""
    with open(os.path.join(EXPERIMENTS, package, name), encoding="utf-8") as handle:
        return json.load(handle)


def interval(values: list[float], scale: float = 1.0) -> dict:
    """Return ``{"v", "lo", "hi"}`` from a sealed ``[estimate, low, high]``."""
    return {"v": values[0] * scale, "lo": values[1] * scale, "hi": values[2] * scale}


def parse_printed(text: str) -> dict:
    """Parse a value as the article prints it, such as ``42.7% [37.3, 48.3]`` or ``+0.126 [..]``."""
    numbers = [float(x) for x in re.findall(r"[-+]?\d+\.?\d*", text.replace("\u2212", "-"))]
    if len(numbers) == 1:
        return {"v": numbers[0]}
    if len(numbers) == 2:
        return {"lo": numbers[0], "hi": numbers[1]}
    return {"v": numbers[0], "lo": numbers[1], "hi": numbers[2]}


def rounded(value: object) -> object:
    """Round every number of a nested structure to four decimals, as the summaries store them."""
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {key: rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rounded(item) for item in value]
    return value


def build_charts() -> None:
    """Write `charts.json`: every number that the page draws or prints, with its source."""
    printed = dict(sealed_values())
    test = rates(TEST_PACKAGE, "TX", None)
    heldout_b = rates(HELDOUT_B_PACKAGE, "HB", "HN")
    checks = {check.label: check for check in headline_checks(EXPERIMENTS)}
    if not all(check.agrees for check in checks.values()):
        raise SystemExit("a recomputed headline value differs from the sealed one")
    calibration = sealed_json("20261004_audit_addendum_r02", "ADDENDUM_R02_SUMMARY.json")["N_I"]
    reanalysis = sealed_json("20261004_audit_addendum_r01", "ADDENDUM_SUMMARY.json")["B4"]
    third = sealed_json("20261004_audit_addendum_r03", "ADDENDUM_R03_SUMMARY.json")
    set_a = sealed_json("20261005_mappo_prox_r01", "summary.json")["secondary"]
    set_b = sealed_json("20261005_mappo_v3_r01", "summary.json")["secondary"]
    final = sealed_json("20261006_mappo_v4_r01", "ANALYSIS.json")["test"]
    set_c = final["secondary"]
    heldout_summary = sealed_json(HELDOUT_B_PACKAGE, "summary.json")

    def measured(entry: dict) -> dict:
        low, high = entry["family_95"]
        return {"v": 100 * entry["observed"], "lo": 100 * low, "hi": 100 * high, "n": entry["n"]}

    def reversal(name: str, oc: list, body: list, centre: list) -> dict:
        return {"set": name, "oc": interval(oc), "body": interval(body), "centre": interval(centre)}

    def contrast(label: str) -> dict:
        return interval(checks[label].recomputed)

    by_team = {}
    for key, data in (("test", test), ("heldout_b", heldout_b)):
        by_team[key] = [
            {"evader": label.split("|")[0], "team": int(label.split("|")[1]), **row}
            for label, row in data["by_team"].items()
        ]
    ablation = third["AB"]
    charts = {
        "null_team": {
            "development": {
                "oc": measured(calibration["null_d06"]),
                "body": measured(calibration["null_prox_5m"]),
                "centre": measured(calibration["null_prox_5m_centre"]),
                "body10": measured(calibration["null_prox_10m"]),
            },
            "heldout_b": {
                k: 100 * v
                for k, v in zip(
                    ("oc", "body", "centre"), heldout_b["null_team"].values(), strict=True
                )
            },
        },
        "pursuit": {
            "test": {
                k: 100 * v
                for k, v in zip(
                    ("oc", "body", "centre"), test["pursuit_all_evaders"].values(), strict=True
                )
            },
            "heldout_b": {
                k: 100 * v
                for k, v in zip(
                    ("oc", "body", "centre"), heldout_b["rates"][PURSUIT].values(), strict=True
                )
            },
        },
        "published": [
            {
                "name": "DGMARL-MVP",
                "detail": "4 pursuers, 2 evaders",
                "random": parse_printed(printed["Published env null 4v2"]),
                "chase": parse_printed(printed["Published env chaser 4v2"]),
            },
            {
                "name": "DGMARL-MVP",
                "detail": "7 pursuers, 4 evaders",
                "random": parse_printed(printed["Published env null 7v4"]),
                "chase": parse_printed(printed["Published env chaser 7v4"]),
            },
            *(
                {
                    "name": "PEPCRL-MVP",
                    "detail": f"{size[0]} pursuers, {size[2]} evaders",
                    "random": parse_printed(printed[f"PEPCRL null {size}"]),
                    "chase": {
                        **parse_printed(printed[f"PEPCRL chaser {size}"]),
                        **parse_printed(printed[f"PEPCRL chaser {size} interval"]),
                    },
                }
                for size in ("6_3", "7_4", "8_5")
            ),
        ],
        "published_events": int(
            re.search(r"\d+", printed["Published events, both environments"]).group()
        ),
        "reversal": [
            reversal(
                "Set A",
                set_a["d06:plb_minus_pursuit"],
                set_a["prox_5m:plb_minus_pursuit"],
                set_a["prox_5m_centre:plb_minus_pursuit"],
            ),
            reversal(
                "Set B",
                set_b["d06:plb_minus_pursuit"],
                set_b["prox_5m:plb_minus_pursuit"],
                set_b["prox_5m_centre:plb_minus_pursuit"],
            ),
            reversal(
                "Set C",
                set_c["d06:plb_minus_pursuit"],
                set_c["prox_5m:plb_minus_pursuit"],
                set_c["prox_5m_centre:plb_minus_pursuit"],
            ),
            reversal(
                "HELD-OUT B",
                heldout_summary["B1_family_95"],
                heldout_summary["plb_minus_pursuit_under_body_gap_5m"],
                heldout_summary["plb_minus_pursuit_under_centre_5m"],
            ),
        ],
        "containment": [
            {
                "level": "Junction level",
                "cities": "development cities",
                **measured(calibration["B2F_junction_joint"]),
            },
            {
                "level": "Junction level",
                "cities": "TEST cities",
                **measured(calibration["B2T_junction_joint"]),
            },
            {
                "level": "Lane level",
                "cities": "development cities",
                **measured(calibration["B2F_lane_nv_joint"]),
            },
            {
                "level": "Lane level",
                "cities": "TEST cities",
                **measured(calibration["B2T_lane_nv_joint"]),
            },
        ],
        "hold": {
            "captures": third["AE"]["captures"],
            "escapes_held": sealed_json("20261004_audit_addendum_r02", "ADDENDUM_R02_SUMMARY.json")[
                "P"
            ]["escapes_observed"],
            "escapes_probe": third["AE"]["escapes"],
        },
        "advantage": [
            {
                "label": "TEST cities",
                "note": "held out, evaluated once; 97.5 % interval",
                **contrast("TEST: PLB - pursuit, family 97.5 %"),
                "primary": True,
            },
            {
                "label": "HELD-OUT B cities",
                "note": "held out, evaluated once; 97.5 % interval",
                **contrast("HELD-OUT B: PLB - pursuit, family 97.5 %"),
                "primary": True,
            },
            {
                "label": "Development cities",
                "note": "avoidant and random evaders",
                **interval(reanalysis["A99_plb_minus_pursuit"]["family_95"]),
            },
            {
                "label": "Optimal evader",
                "note": "TEST cities",
                **contrast("TEST: PLB - pursuit, optimal evader, family 95 %"),
            },
            {
                "label": "Optimal evader",
                "note": "HELD-OUT B cities",
                **contrast("HELD-OUT B: PLB - pursuit, optimal evader, family 95 %"),
            },
            {
                "label": "Goal-directed evader",
                "note": "development cities",
                **interval(reanalysis["GOAL_plb_minus_pursuit"]["family_95"]),
            },
            {
                "label": "Evader tuned against the controller",
                "note": "development cities",
                **parse_printed(printed["Tuned evader primary"]),
            },
            {
                "label": "Ballistic position update",
                "note": "another kinematic model",
                **parse_printed(printed["Kinematics K1"]),
            },
            {
                "label": "IDM car following",
                "note": "another kinematic model",
                **parse_printed(printed["Kinematics K2"]),
            },
            {
                "label": "With background traffic",
                "note": "about 300 other cars per city",
                **parse_printed(printed["Traffic primary"]),
            },
        ],
        "by_team": by_team,
        "ablation": {
            "all": interval(ablation["primary_pooled"]),
            "rows": [
                {"label": "Avoidant evader", **interval(ablation["by_evader"]["AVOIDANT"])},
                {"label": "Random evader", **interval(ablation["by_evader"]["RANDOM"])},
                {
                    "label": "Goal-directed evader",
                    **interval(ablation["by_evader"]["GOAL_DIRECTED"]),
                },
                {"label": "Team of 3", **interval(ablation["by_team"]["3"])},
                {"label": "Team of 5", **interval(ablation["by_team"]["5"])},
                {"label": "Team of 7", **interval(ablation["by_team"]["7"])},
            ],
        },
        "learning": [
            {
                "label": "Fine-tuned, with a critic warm-up",
                "note": "final minus imitation start",
                **interval(set_c["d06:final_W_mlp_minus_start"]),
            },
            {
                "label": "Fine-tuned, without warm-up",
                "note": "final minus imitation start",
                **interval(set_c["d06:final_F_mlp_minus_start"]),
            },
            {
                "label": "Fine-tuned, Kolmogorov\u2013Arnold head",
                "note": "final minus imitation start",
                **interval(set_c["d06:final_F_kan_minus_start"]),
            },
            {
                "label": "Imitation of the planner",
                "note": "imitation minus the planner itself",
                **interval(set_c["d06:start_mlp_minus_plb"]),
            },
        ],
        "counts": {
            "evaluation": int(printed["Count evaluation"]),
            "selection": int(printed["Count selection"]),
            "replay": int(printed["Count replay"]),
            "studies": sum(e["kind"] == "sealed" for e in load_inventory()["packages"].values()),
            "demonstrations": sum(
                e["kind"] == "demonstration" for e in load_inventory()["packages"].values()
            ),
            "article_numbers": len(printed),
            "headline_recomputed": len(checks),
        },
    }
    with open(os.path.join(DATA, "charts.json"), "w", encoding="utf-8") as handle:
        json.dump(rounded(charts), handle, indent=1)
    print(f"charts.json: {len(charts)} blocks")


def build_networks() -> None:
    """Draw the fifteen network outlines directly from the frozen SUMO geometries."""
    snapshot = Path(ROOT) / "as_run"
    split = json.loads((snapshot / "contracts/split_manifest.json").read_text())
    groups = {k: v["cities"] for k, v in split["splits"].items()}
    groups["HELD-OUT B"] = json.loads((snapshot / "assets/osm_b/MANIFEST.json").read_text())[
        "accepted"
    ]
    for group, cities in groups.items():
        for city in cities:
            folder = "osm_b" if group == "HELD-OUT B" else "osm"
            network = ET.parse(snapshot / "assets" / folder / f"{city}.net.xml").getroot()
            lines = []
            for edge in network.findall("edge"):
                lane = edge.find("lane")
                if edge.get("function") == "internal" or lane is None:
                    continue
                lines.append(
                    [tuple(map(float, p.split(","))) for p in lane.attrib["shape"].split()]
                )
            xs = [p[0] for line in lines for p in line]
            ys = [p[1] for line in lines for p in line]
            x0, y0 = min(xs), min(ys)
            scale = min(144 / (max(xs) - x0), 104 / (max(ys) - y0))
            dx = (160 - (max(xs) - x0) * scale) / 2
            dy = (120 - (max(ys) - y0) * scale) / 2
            paths = []
            for line in lines:
                coords = " L".join(
                    f"{dx + (x - x0) * scale:.1f},{120 - dy - (y - y0) * scale:.1f}"
                    for x, y in line
                )
                paths.append("M" + coords)
            svg = (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 120">'
                f"<title>{city}: {group} road geometry</title>"
                '<path fill="none" stroke="#8b9daf" stroke-width="0.65" '
                f'd="{" ".join(paths)}"/></svg>\n'
            )
            Path(DATA, f"network-{city}.svg").write_text(svg)


def build_all() -> None:
    """Build the display data without altering any source evidence."""
    os.makedirs(DATA, exist_ok=True)
    build_episodes()
    build_charts()
    build_networks()


def main() -> int:
    """Build all assets or compare a temporary rebuild with the committed files."""
    global DATA  # noqa: PLW0603 — temporarily redirect only generated outputs
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        committed = Path(DATA)
        with tempfile.TemporaryDirectory(prefix="pursuit-site-") as directory:
            DATA = directory
            try:
                build_all()
                stale = [
                    p.name
                    for p in Path(DATA).iterdir()
                    if not (committed / p.name).exists()
                    or p.read_bytes() != (committed / p.name).read_bytes()
                ]
            finally:
                DATA = str(committed)
        print("Site data: " + (", ".join(sorted(stale)) if stale else "all current"))
        return int(bool(stale))
    build_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
