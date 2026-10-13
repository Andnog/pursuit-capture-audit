"""O27: run the frozen protocol (and its amendment) over the eight scenarios.

Offline: no SUMO process, no optimizer, no checkpoint, no TEST map. Budget per the protocol:
90 CPU-minutes across the four AVOIDANT cases, 30 across the four OPTIMAL_ESCAPE cases,
evenly per case; at most 100,000 expansions per case. Unused time is not redistributed.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from joint_interception.domain.contracts import load_domain  # noqa: E402
from joint_interception.simulator.evader import EvaderLevel  # noqa: E402
from joint_interception.world.construction import Constructor, make_scenario  # noqa: E402
from joint_interception.world.network import GraphNetwork  # noqa: E402

MAPS = ["adelaide_cbd", "seattle_downtown", "toronto_downtown", "washington_downtown"]
BUDGET = {EvaderLevel.AVOIDANT: 90 * 60 / 4, EvaderLevel.OPTIMAL_ESCAPE: 30 * 60 / 4}
MAX_EXPANSIONS = 100_000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package) if not os.path.isabs(args.package) else args.package
    if os.path.isfile(os.path.join(package, "checksums.json")):
        print("REFUSED: package is sealed", file=sys.stderr)
        return 2
    domain = load_domain()
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as h:
        status = json.load(h)
    paths = {m["map_id"]: m["path"] for m in status["maps"]}
    out_path = os.path.join(package, "results.jsonl")
    started = time.time()
    with open(out_path, "w", encoding="utf-8") as out:
        for level in (EvaderLevel.AVOIDANT, EvaderLevel.OPTIMAL_ESCAPE):
            for map_id in MAPS:
                net = GraphNetwork.from_sumo(paths[map_id])
                scenario = make_scenario(net, map_id, level, domain["team"]["pursuer_ids"])
                constructor = Constructor(net, scenario, domain, MAX_EXPANSIONS, BUDGET[level])
                result = constructor.search()
                row = {
                    "map_id": map_id,
                    "level": level.name,
                    "scenario_seed": scenario.seed,
                    "evader_start": scenario.evader_start,
                    "pursuer_starts": scenario.pursuer_starts,
                    "budget_cpu_s": BUDGET[level],
                    **result,
                    "expansions": constructor.expansions,
                }
                out.write(json.dumps(row) + "\n")
                out.flush()
                print(
                    f"{level.name:14s} {map_id:20s} {result['verdict']:30s} "
                    f"expansions {constructor.expansions:6d} tally {result.get('tally')}",
                    flush=True,
                )
    with open(os.path.join(package, "environment.json"), "w", encoding="utf-8") as h:
        json.dump(
            {
                "python_version": platform.python_version(),
                "platform": platform.platform(),
                "offline": True,
                "sumo_process_starts": 0,
                "optimizer_run": False,
                "checkpoint_loaded": False,
                "test_split_accessed": False,
                "wall_seconds": round(time.time() - started, 1),
            },
            h,
            indent=2,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
