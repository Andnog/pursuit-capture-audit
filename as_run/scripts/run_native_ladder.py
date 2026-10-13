"""Native ladder stage runner (docs/PLAN_NATIVE_CONTROLLED_EN.md). Parallel, SUMO only.

One task = (map, evader level, scenario index). Writes one JSON line per task, a per-map summary
and, per map and level, a side-by-side-ready pair of GIFs (factual vs helper never acting) for the
best construction found (robust first, else fragile).
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

SUMO = "/Library/Frameworks/Python.framework/Versions/3.10/bin/sumo"


def _paths() -> dict:
    with open(os.path.join(ROOT, "assets", "controlled", "manifest.json"), encoding="utf-8") as h:
        out = {k: os.path.join(ROOT, v["path"]) for k, v in json.load(h).items()}
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as h:
        out.update({m["map_id"]: m["path"] for m in json.load(h)["maps"]})
    return out


def task(args):
    map_id, level_name, index, salt, budget, package, generator = args
    from joint_interception.domain.contracts import load_domain
    from joint_interception.native.engine import search_scenario
    from joint_interception.simulator.evader import EvaderLevel
    from joint_interception.world.construction import make_scenario
    from joint_interception.world.network import GraphNetwork

    domain = load_domain()
    path = _paths()[map_id]
    net = GraphNetwork.from_sumo(path)
    level = EvaderLevel[level_name]
    sc = make_scenario(net, map_id, level, domain["team"]["pursuer_ids"], f"{salt}s{index}")
    if len(sc.pursuer_starts) != len(domain["team"]["pursuer_ids"]):
        return {"map_id": map_id, "level": level_name, "index": index, "skipped": "no starts"}
    res = search_scenario(
        net,
        path,
        sc,
        domain,
        SUMO,
        budget,
        label=f"{map_id[:3]}{level_name[:1]}{index}_",
        generator=generator,
    )
    row = {
        "map_id": map_id,
        "level": level_name,
        "index": index,
        "scenario_seed": sc.seed,
        "plans_tried": res.plans_tried,
        "captures": res.captures,
        "labels": res.labels,
        "coordinated": len(res.coordinated),
        "robust": len(res.robust),
        "constructions": res.coordinated,
        "cpu_seconds": res.cpu_seconds,
        "stopped_by": res.stopped_by,
    }
    if res.best_traces:
        import pickle

        tdir = os.path.join(package, "traces")
        os.makedirs(tdir, exist_ok=True)
        with open(os.path.join(tdir, f"{map_id}_{level_name}_{index}.pkl"), "wb") as h:
            pickle.dump(res.best_traces, h)
        row["best"] = {
            k: res.best_traces[k] for k in ("finisher", "helper", "witness_start_s", "robust")
        }
    return row


def gifs(package, rows, paths):
    import pickle

    from render_capture_gif import render

    gdir = os.path.join(package, "gifs")
    os.makedirs(gdir, exist_ok=True)
    best: dict = {}
    for r in rows:
        if "best" not in r:
            continue
        key = (r["map_id"], r["level"])
        rank = (r["best"]["robust"], -r["index"])
        if key not in best or rank > best[key][0]:
            best[key] = (rank, r)
    made = []
    for (map_id, level), (_, r) in sorted(best.items()):
        with open(os.path.join(package, "traces", f"{map_id}_{level}_{r['index']}.pkl"), "rb") as h:
            t = pickle.load(h)
        w = t["witness_start_s"]
        f = next(x for x in t["factual"] if abs(x.time_s - w) < 0.05)
        centre = (f.vehicles["e1"].x, f.vehicles["e1"].y)
        tag = "robust" if t["robust"] else "FRAGILE"
        for arm in ("factual", "helper_never_acts"):
            out = os.path.join(gdir, f"{map_id}_{level}_{arm}.gif")
            render(
                out,
                paths[map_id],
                t[arm],
                t["finisher"],
                t["helper"],
                max(0.0, w - 30),
                w + 4,
                f"{map_id} {level} s{r['index']} {arm} ({tag})",
                centre=centre,
            )
            made.append(out)
    return made


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--maps", nargs="+", required=True)
    parser.add_argument("--levels", nargs="+", default=["AVOIDANT"])
    parser.add_argument("--extra", nargs="*", default=[], help="map:LEVEL pairs added")
    parser.add_argument("--scenarios", type=int, default=8)
    parser.add_argument("--budget", type=float, required=True, help="CPU s per scenario")
    parser.add_argument("--salt", required=True)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--generator", default="exact", choices=["exact", "margin"])
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    if os.path.isfile(os.path.join(package, "checksums.json")):
        print("REFUSED: sealed", file=sys.stderr)
        return 2
    pairs = [(m, lv) for m in args.maps for lv in args.levels]
    pairs += [tuple(x.split(":")) for x in args.extra]
    tasks = [
        (m, lv, i, args.salt, args.budget, package, args.generator)
        for m, lv in pairs
        for i in range(args.scenarios)
    ]
    rows = []
    with (
        mp.get_context("spawn").Pool(args.workers) as pool,
        open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as out,
    ):
        for row in pool.imap_unordered(task, tasks):
            rows.append(row)
            out.write(json.dumps(row) + "\n")
            out.flush()
            print(
                row.get("map_id"),
                row.get("level"),
                row.get("index"),
                "tried",
                row.get("plans_tried"),
                "coord",
                row.get("coordinated"),
                "robust",
                row.get("robust"),
                flush=True,
            )
    summary = {}
    for m, lv in pairs:
        rs = [r for r in rows if r["map_id"] == m and r["level"] == lv and "plans_tried" in r]
        tried = sum(r["plans_tried"] for r in rs)
        summary[f"{m}:{lv}"] = {
            "scenarios": len(rs),
            "with_capture": sum(r["captures"] > 0 for r in rs),
            "with_coordinated": sum(r["coordinated"] > 0 for r in rs),
            "with_robust": sum(r["robust"] > 0 for r in rs),
            "plans_tried": tried,
            "coordinated_per_100_plans": round(
                100 * sum(r["coordinated"] for r in rs) / max(1, tried), 3
            ),
            "robust_per_100_plans": round(100 * sum(r["robust"] for r in rs) / max(1, tried), 3),
            "cpu_seconds": round(sum(r["cpu_seconds"] for r in rs), 1),
        }
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(summary, h, indent=2)
    made = gifs(package, rows, _paths())
    print(json.dumps(summary, indent=1))
    print("GIFS", *made, sep="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
