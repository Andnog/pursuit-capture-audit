"""A-58 native-replication search (N01). See the package's PROTOCOL_EN.md.

Per TRAINING map: the W4 search under the revised declared model, fresh seeds (salt "n01"),
AVOIDANT; a model CONSTRUCTED ends the search only if it replicates natively in SUMO
(`validation.native.native_check`). Refuses to write into a sealed package.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import platform
import resource
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from joint_interception.domain.contracts import load_domain  # noqa: E402
from joint_interception.simulator.evader import EvaderLevel  # noqa: E402
from joint_interception.validation.native import native_check  # noqa: E402
from joint_interception.world.construction import Constructor, make_scenario  # noqa: E402
from joint_interception.world.network import GraphNetwork  # noqa: E402

MAPS = ["adelaide_cbd", "seattle_downtown", "toronto_downtown", "washington_downtown"]
SUMO = "/Library/Frameworks/Python.framework/Versions/3.10/bin/sumo"


def main() -> int:
    import sumolib

    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--salt", required=True)
    parser.add_argument("--level", default="AVOIDANT")
    parser.add_argument("--cpu-per-map", type=float, required=True)
    parser.add_argument("--exp-per-map", type=int, required=True)
    args = parser.parse_args()
    package = args.package if os.path.isabs(args.package) else os.path.join(ROOT, args.package)
    if os.path.isfile(os.path.join(package, "checksums.json")):
        print("REFUSED: package is sealed", file=sys.stderr)
        return 2
    domain = load_domain()
    level = EvaderLevel[args.level]
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as h:
        paths = {m["map_id"]: m["path"] for m in json.load(h)["maps"]}
    started = time.time()
    child0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    native_count = 0
    with open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as out:
        for map_id in MAPS:
            net = GraphNetwork.from_sumo(paths[map_id])
            snet = sumolib.net.readNet(paths[map_id], withInternal=True)
            scenario = make_scenario(net, map_id, level, domain["team"]["pursuer_ids"], args.salt)
            constructor = Constructor(net, scenario, domain, args.exp_per_map, args.cpu_per_map)
            checks = {"n": 0, "sumo_process_starts": 0}

            def accept(result, plan, _n=net, _s=snet, _m=map_id, _sc=scenario, _c=checks):
                _c["n"] += 1
                ok, detail = native_check(
                    result, plan, _n, _s, paths[_m], _sc, domain, SUMO, label=f"n{_m}{_c['n']}"
                )
                _c["sumo_process_starts"] += detail["sumo_process_starts"]
                return ok, detail

            cpu0 = time.process_time()
            result = constructor.search(accept=accept)
            cpu = time.process_time() - cpu0
            native = result["verdict"] == "CONSTRUCTED"
            native_count += native
            if native:
                stop = "native construction found"
            elif constructor.expansions >= args.exp_per_map:
                stop = "expansion cap"
            elif cpu >= args.cpu_per_map - 0.5:
                stop = "CPU cap"
            else:
                stop = "candidate queue exhausted"
            first_failed = collections.Counter(
                next(
                    (
                        k
                        for k, v in r["acceptance"].items()
                        if isinstance(v, dict) and not v["passes"]
                    ),
                    "none",
                )
                for r in constructor.rejected
            )
            row = {
                "map_id": map_id,
                "level": level.name,
                "salt": args.salt,
                "scenario_seed": scenario.seed,
                "verdict": "NATIVE_CONSTRUCTED" if native else result["verdict"],
                "result": result,
                "model_constructed_rejected_natively": len(constructor.rejected),
                "rejection_first_failed_arm": dict(first_failed),
                "rejected": constructor.rejected[:20],
                "expansions": constructor.expansions,
                "cpu_seconds_python": round(cpu, 1),
                "native_checks": checks["n"],
                "sumo_process_starts": checks["sumo_process_starts"],
                "stopped_by": stop,
                "tally": constructor._tally(),
            }
            out.write(json.dumps(row) + "\n")
            out.flush()
            print(
                f"{map_id:20s} {row['verdict']:26s} exp {constructor.expansions:6d} cpu {cpu:7.1f} "
                f"model-constructed rejected natively {len(constructor.rejected)} stop: {stop}",
                flush=True,
            )
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    summary = {
        "native_constructions": native_count,
        "prerequisite": "MET" if native_count >= 2 else "NOT_MET",
        "rule": "at least two TRAINING maps with a natively replicated construction",
        "cpu_seconds_sumo": round(
            child.ru_utime + child.ru_stime - child0.ru_utime - child0.ru_stime, 1
        ),
        "wall_seconds": round(time.time() - started, 1),
        "python_version": platform.python_version(),
    }
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(summary, h, indent=2)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
