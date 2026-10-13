"""O27 r03: the final pre-registered W4 attempt, AVOIDANT only. See the r03 package PROTOCOL_EN.md.

Identical to r02's runner except: fresh seeds (salt "r03"), the declared model with the A-52 defect
fixed, and AVOIDANT only (the gate's level; A-53). Criterion unchanged: both contrasts.

Records what r01's runner did not: the stop reason, final CPU seconds, refused commands,
and why each factual capture failed verification. Expansion caps are set so that they, not
CPU time, are expected to bind - a search stopped by CPU time depends on machine speed.
"""

from __future__ import annotations

import argparse
import collections
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
SALT = "r03"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--cpu-avoidant", type=float, required=True)
    parser.add_argument("--exp-avoidant", type=int, required=True)
    args = parser.parse_args()
    package = args.package if os.path.isabs(args.package) else os.path.join(ROOT, args.package)
    if os.path.isfile(os.path.join(package, "checksums.json")):
        print("REFUSED: package is sealed", file=sys.stderr)
        return 2
    domain = load_domain()
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as h:
        paths = {m["map_id"]: m["path"] for m in json.load(h)["maps"]}
    caps = {
        EvaderLevel.AVOIDANT: (args.exp_avoidant, args.cpu_avoidant),
    }
    started = time.time()
    with open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as out:
        for level in (EvaderLevel.AVOIDANT,):
            for map_id in MAPS:
                net = GraphNetwork.from_sumo(paths[map_id])
                scenario = make_scenario(net, map_id, level, domain["team"]["pursuer_ids"], SALT)
                max_exp, max_cpu = caps[level]
                constructor = Constructor(net, scenario, domain, max_exp, max_cpu)
                cpu0 = time.process_time()
                result = constructor.search()
                cpu = time.process_time() - cpu0
                if result["verdict"] == "CONSTRUCTED":
                    stop = "construction found"
                elif constructor.expansions >= max_exp:
                    stop = "expansion cap"
                elif cpu >= max_cpu - 0.5:
                    stop = "CPU cap"
                else:
                    stop = "candidate queue exhausted"
                why = collections.Counter(
                    json.dumps(e["why"], sort_keys=True)
                    for e in constructor.log
                    if e["verdict"] == "FACTUAL_FAILED_VERIFICATION"
                )
                row = {
                    "map_id": map_id,
                    "level": level.name,
                    "salt": SALT,
                    "scenario_seed": scenario.seed,
                    "evader_start": scenario.evader_start,
                    "pursuer_starts": scenario.pursuer_starts,
                    **result,
                    "expansions": constructor.expansions,
                    "cpu_seconds_total": round(cpu, 3),
                    "stopped_by": stop,
                    "caps": {"expansions": max_exp, "cpu_seconds": max_cpu},
                    "refused_commands": constructor.refused_commands,
                    "failed_verification_reasons": dict(why),
                }
                out.write(json.dumps(row) + "\n")
                out.flush()
                print(
                    f"{level.name:14s} {map_id:20s} {result['verdict']:30s} "
                    f"exp {constructor.expansions:6d} cpu {cpu:7.1f} stop: {stop}",
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
