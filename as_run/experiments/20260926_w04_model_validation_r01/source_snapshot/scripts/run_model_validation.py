"""A-47 empirical model-validation gate on the DEVELOPMENT maps. See the package's PROTOCOL_EN.md.

Per map: the first CAPTURES legal diagnostic scenarios with a model capture and the first OTHERS
without, in index order (selection on MODEL outcomes only). Each is replayed in SUMO open loop
(scored, the gate) and closed loop (reported). Refuses to write into a sealed package.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from joint_interception.domain.contracts import CaptureParameters, load_domain  # noqa: E402
from joint_interception.evaluation.capture_judge import judge_capture  # noqa: E402
from joint_interception.validation.diagnostic_set import select  # noqa: E402
from joint_interception.validation.metrics import score, summarise  # noqa: E402
from joint_interception.validation.sumo_replay import replay  # noqa: E402
from joint_interception.world.network import GraphNetwork  # noqa: E402

MAPS = ["phoenix_downtown", "portland_downtown", "sapporo_grid"]
SUMO = "/Library/Frameworks/Python.framework/Versions/3.10/bin/sumo"


def main() -> int:
    import sumolib

    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--captures", type=int, required=True)
    parser.add_argument("--others", type=int, required=True)
    parser.add_argument("--max-index", type=int, required=True)
    parser.add_argument("--cpu-budget-s", type=float, required=True)
    parser.add_argument("--maps", nargs="*", default=MAPS, help="harness checks only")
    args = parser.parse_args()
    package = args.package if os.path.isabs(args.package) else os.path.join(ROOT, args.package)
    if os.path.isfile(os.path.join(package, "checksums.json")):
        print("REFUSED: package is sealed", file=sys.stderr)
        return 2
    domain = load_domain()
    params = CaptureParameters.from_domain(domain)
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as h:
        paths = {m["map_id"]: m["path"] for m in json.load(h)["maps"]}
    started = time.time()
    cpu0 = time.process_time()
    child0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    all_items = []
    selection = {}
    sumo_starts = 0
    stopped_by = "completed"
    with open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as out:
        for map_id in args.maps:
            net = GraphNetwork.from_sumo(paths[map_id])
            snet = sumolib.net.readNet(paths[map_id], withInternal=True)
            chosen, tally = select(
                net,
                map_id,
                domain,
                domain["team"]["pursuer_ids"],
                args.captures,
                args.others,
                args.max_index,
            )
            selection[map_id] = tally
            print(map_id, tally, flush=True)
            for index, run in chosen:
                child = resource.getrusage(resource.RUSAGE_CHILDREN)
                used = (time.process_time() - cpu0) + (
                    child.ru_utime + child.ru_stime - child0.ru_utime - child0.ru_stime
                )
                if used > args.cpu_budget_s:
                    stopped_by = "CPU budget"
                    break
                rec = replay(run, net, snet, paths[map_id], domain, SUMO, label=f"v{map_id}{index}")
                closed = replay(
                    run,
                    net,
                    snet,
                    paths[map_id],
                    domain,
                    SUMO,
                    closed_loop=True,
                    label=f"c{map_id}{index}",
                )
                sumo_starts += 2
                items = score(run, net, domain, rec)
                all_items.append(items)
                cj = judge_capture(closed.trace, "e1", params, domain["timing"]["physical_step_s"])
                n = len(run.routes["e1"])
                row = {
                    "map_id": map_id,
                    "index": index,
                    "kind": run.kind,
                    "scenario_seed": run.scenario.seed,
                    "model_capture": run.capture,
                    "model_end_s": run.end_s,
                    "summary": summarise([items]),
                    "m3": items.m3,
                    "stop_errors": len(rec.stop_errors),
                    "inserted_late": rec.inserted_late,
                    "lane_changes": {k: len(v) for k, v in rec.lane_changes.items()},
                    "closed_loop": {
                        "evader_route_matches_model": closed.evader_route[:n] == run.routes["e1"],
                        "judge": cj.verdict.value,
                        "finisher": cj.finisher,
                        "witness_start_s": cj.witness_start_s,
                    },
                }
                out.write(json.dumps(row) + "\n")
                out.flush()
                s = row["summary"]
                print(
                    f"  {index:3d} {run.kind:12s} cap={run.capture is not None!s:5s} "
                    f"m1={s['m1_share_within_1s']:.2f} m2={s['m2_share_within_1m']:.2f} "
                    f"m3={[i['reproduced'] for i in items.m3]} m4p95={s['m4_p95_m']:.2f}",
                    flush=True,
                )
            if stopped_by != "completed":
                break
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = {
        "gate": summarise(all_items),
        "selection": selection,
        "scenarios_scored": len(all_items),
        "stopped_by": stopped_by,
        "cpu_seconds_python": round(time.process_time() - cpu0, 1),
        "cpu_seconds_sumo": round(
            child.ru_utime + child.ru_stime - child0.ru_utime - child0.ru_stime, 1
        ),
        "sumo_process_starts": sumo_starts,
    }
    with open(os.path.join(package, "gate_result.json"), "w", encoding="utf-8") as h:
        json.dump(result, h, indent=2)
    with open(os.path.join(package, "environment.json"), "w", encoding="utf-8") as h:
        json.dump(
            {
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "sumo_binary": SUMO,
                "optimizer_run": False,
                "checkpoint_loaded": False,
                "test_split_accessed": False,
                "wall_seconds": round(time.time() - started, 1),
            },
            h,
            indent=2,
        )
    print(json.dumps(result["gate"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
