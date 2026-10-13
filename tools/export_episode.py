"""Export one simulated episode for the web site: its trace and the lanes around it.

This tool runs the frozen code, so it must be started from `as_run/`, in its environment, with
SUMO 1.21 installed:

    cd as_run
    uv run python ../tools/export_episode.py --map adelaide_cbd --index 25 --method pursuit \
        --out ../results/episodes/adelaide_25_pursuit

The episodes that it exports are illustrations. They use their own scenario salt (`DEMO`), on a
city of the development phase, and are not part of any evaluation of the article.

It writes three files: `<out>.trace.jsonl` (every physical step, in the trace format of the
library), `<out>.network.json` (the lanes near the vehicles) and `<out>.meta.json`.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

SNAPSHOT = os.getcwd()
METHODS = ("pursuit", "ambush", "ambush_plus")
MARGIN_M = 80.0


def tuned_parameters() -> dict:
    """Return the parameters of predictive lane blocking that the study selected."""
    path = os.path.join(SNAPSHOT, "experiments", "20261002_ambush_optimization_r01", "summary.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["final_params"]


def lanes_near(net_file: str, box: tuple[float, float, float, float]) -> list[dict]:
    """Return the passenger lanes that cross a bounding box, as polylines with their width."""
    import sumolib

    x0, y0, x1, y1 = box
    lanes = []
    for edge in sumolib.net.readNet(net_file, withInternal=True).getEdges():
        for lane in edge.getLanes():
            if not lane.allows("passenger"):
                continue
            shape = lane.getShape()
            if any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in shape):
                lanes.append(
                    {
                        "shape": [[round(x, 1), round(y, 1)] for x, y in shape],
                        "width": round(lane.getWidth(), 2),
                        "internal": edge.getID().startswith(":"),
                    }
                )
    return lanes


def main() -> int:
    """Run one episode and write its files."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--map", required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--method", choices=METHODS, required=True)
    parser.add_argument("--evader", default="AVOIDANT")
    parser.add_argument("--team", type=int, default=5)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if not os.path.isdir(os.path.join(SNAPSHOT, "experiments")):
        raise SystemExit("run this tool from the as_run directory")
    sys.path.insert(0, os.path.join(SNAPSHOT, "src"))
    sys.path.insert(0, os.path.join(SNAPSHOT, "scripts"))
    from audit_cage_certificate import replay

    seed = 9500 + args.index
    learner = {"params": tuned_parameters()} if args.method == "ambush_plus" else None
    episode, _records = replay(
        args.map,
        args.index,
        seed,
        "DEMO",
        args.method[0],
        None,
        "policy",
        300.0,
        kind=args.method,
        speed=1.0,
        level=args.evader,
        team=args.team,
        learner=learner,
    )
    with open(os.path.join(SNAPSHOT, "MAPS_STATUS.json"), encoding="utf-8") as handle:
        net_file = next(m["path"] for m in json.load(handle)["maps"] if m["map_id"] == args.map)
    xs = [v.x for frame in episode.trace for v in frame.vehicles.values()]
    ys = [v.y for frame in episode.trace for v in frame.vehicles.values()]
    box = (min(xs) - MARGIN_M, min(ys) - MARGIN_M, max(xs) + MARGIN_M, max(ys) + MARGIN_M)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out + ".trace.jsonl", "w", encoding="utf-8") as handle:
        for frame in episode.trace:
            vehicles = {
                vid: {
                    "x": round(v.x, 3),
                    "y": round(v.y, 3),
                    "heading_rad": round(v.heading_rad, 4),
                    "speed": round(v.speed_mps, 3),
                    "length": v.length_m,
                    "width": v.width_m,
                }
                for vid, v in sorted(frame.vehicles.items())
            }
            handle.write(json.dumps({"t": round(frame.time_s, 1), "vehicles": vehicles}) + "\n")
    with open(args.out + ".network.json", "w", encoding="utf-8") as handle:
        json.dump({"box": [round(b, 1) for b in box], "lanes": lanes_near(net_file, box)}, handle)
    meta = {
        "map": args.map,
        "scenario": args.index,
        "sumo_seed": seed,
        "salt": "DEMO",
        "method": args.method,
        "evader": args.evader,
        "team": args.team,
        "frames": len(episode.trace),
        "end_s": episode.end_s,
        "operational_capture_by_the_frozen_judge": bool(episode.contact_capture),
        "collided": bool(episode.collided),
    }
    with open(args.out + ".meta.json", "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=1)
    print(json.dumps(meta))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
