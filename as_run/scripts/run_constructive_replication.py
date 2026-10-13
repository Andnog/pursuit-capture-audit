"""Replication of A-40 across maps and routes. See the package PROTOCOL_EN.md.

Two questions. Does the refutation replicate, and is there ANY route on which the
constructive arrival time holds? The second bounds the repair: if some routes hold, the
domain restriction A-40 called "probably too restrictive" is a live option with a
measurable cost.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import resource
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from joint_interception.domain.contracts import load_domain  # noqa: E402
from joint_interception.opportunities.schedule import (  # noqa: E402
    arrival_at,
    constructive_arrival_set,
)
from joint_interception.simulator.sumo_adapter import TraciBackend  # noqa: E402
from run_constructive_on_network import (  # noqa: E402
    TOLERANCE_S,
    build,
    drive_closed_loop,
    drive_to_station,
    route_speed_limit,
    speeds_from_profile,
)

TRAINING_MAPS = ["adelaide_cbd", "seattle_downtown", "toronto_downtown", "washington_downtown"]
ACCEL = 2.6
DECEL = 4.5


def map_record(map_id: str) -> dict:
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as handle:
        status = json.load(handle)
    if map_id in status["usable_by_declared_split"]["test"]:
        raise SystemExit(f"REFUSED: {map_id} is a TEST map.")
    if map_id not in status["usable_by_declared_split"]["train"]:
        raise SystemExit(f"REFUSED: {map_id} is not in the TRAINING split.")
    return next(m for m in status["maps"] if m["map_id"] == map_id)


def pick_routes(backend: TraciBackend, net_path: str, count: int, minimum_edges: int):
    """Distinct routes in the deterministic order the search returns them.

    Not selected after seeing their errors: the order depends only on edge identifiers.
    """
    import sumolib

    net = sumolib.net.readNet(net_path)
    edges = sorted(
        (
            e
            for e in net.getEdges()
            if e.allows("passenger") and e.getLength() > 50.0 and not e.isSpecial()
        ),
        key=lambda e: e.getID(),
    )
    found: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for start in edges[:60]:
        if len(found) >= count:
            break
        for end in reversed(edges[:400]):
            if start.getID() == end.getID():
                continue
            route = backend.find_route_edges(start.getID(), end.getID())
            key = tuple(route)
            if len(route) >= minimum_edges and key not in seen:
                seen.add(key)
                found.append(list(route))
                break
    return found


def junction_census(net, edges: list[str]) -> dict:
    """Node types along a route, read from the network file."""
    counts: dict[str, int] = {}
    for edge_id in edges:
        try:
            node = net.getEdge(edge_id).getToNode()
        except KeyError:
            continue
        counts[node.getType()] = counts.get(node.getType(), 0) + 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--routes-per-map", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260923)
    parser.add_argument("--reseal", action="store_true")
    args = parser.parse_args()
    package = args.package if os.path.isabs(args.package) else os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    if os.path.isfile(os.path.join(package, "checksums.json")) and not args.reseal:
        print(f"REFUSED: {os.path.basename(package)} is sealed.", file=sys.stderr)
        return 2

    import sumolib

    domain = load_domain()
    step_s = domain["timing"]["physical_step_s"]
    sumo_binary = os.environ.get("SUMO_BINARY") or "sumo"
    started_wall = time.time()
    started_cpu = resource.getrusage(resource.RUSAGE_SELF)
    stamp = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")

    events = [{"ts": stamp, "event": "run_started", "package": os.path.basename(package)}]
    rows: list[dict] = []
    starts = 0
    simulated_s = 0.0

    for map_id in TRAINING_MAPS:
        record = map_record(map_id)
        net = sumolib.net.readNet(record["path"])
        probe = TraciBackend(
            record["path"],
            seed=args.seed,
            step_s=step_s,
            sumo_binary=sumo_binary,
            label=f"probe_{map_id}",
        )
        starts += 1
        try:
            routes = pick_routes(probe, record["path"], args.routes_per_map, minimum_edges=6)
        finally:
            probe.close()
        events.append(
            {"ts": stamp, "event": "routes_found", "map_id": map_id, "routes": len(routes)}
        )

        for route_index, edges in enumerate(routes):
            geom = TraciBackend(
                record["path"],
                seed=args.seed,
                step_s=step_s,
                sumo_binary=sumo_binary,
                label=f"geom_{map_id}_{route_index}",
            )
            starts += 1
            try:
                limit, _ = route_speed_limit(geom, edges)
                build(geom, edges, domain, ["probe"])
                station_index = max(1, int(len(edges) * 0.6))
                station_edge = edges[station_index]
                station_pos = geom._connection.lane.getLength(f"{station_edge}_0") * 0.5
                distance = geom._connection.vehicle.getDrivingDistance(
                    "probe", station_edge, station_pos
                )
                simulated_s += geom.time_s
            finally:
                geom.close()

            if distance is None or distance <= 0 or distance > 1e6:
                continue
            witness = constructive_arrival_set(
                "p1", distance, 0.0, limit, ACCEL, DECEL, horizon_s=400.0
            )
            if witness is None:
                continue

            census = junction_census(net, edges[: station_index + 1])
            junctions = sum(v for k, v in census.items() if k != "dead_end")

            for factor in (1.0, 1.5, 2.0):
                target = witness.earliest_s * factor
                profile = arrival_at(distance, 0.0, limit, ACCEL, DECEL, target)
                if profile is None:
                    continue
                base = {
                    "map_id": map_id,
                    "route_index": route_index,
                    "edges": len(edges),
                    "station_distance_m": round(distance, 3),
                    "speed_limit_mps": round(limit, 3),
                    "junctions_before_station": junctions,
                    "junction_census": census,
                    "factor": factor,
                    "target_s": round(target, 6),
                }
                for arm in ("open_loop", "closed_loop"):
                    backend = TraciBackend(
                        record["path"],
                        seed=args.seed,
                        step_s=step_s,
                        sumo_binary=sumo_binary,
                        label=f"{arm}_{map_id}_{route_index}_{factor}",
                    )
                    starts += 1
                    try:
                        build(backend, edges, domain, ["p1"])
                        if arm == "open_loop":
                            observed = drive_to_station(
                                backend,
                                "p1",
                                distance,
                                speeds_from_profile(profile, step_s),
                                step_s,
                                max_steps=int(400.0 / step_s),
                            )
                        else:
                            observed = drive_closed_loop(
                                backend,
                                "p1",
                                distance,
                                target,
                                limit,
                                ACCEL,
                                DECEL,
                                step_s,
                                max_steps=int(400.0 / step_s),
                            )
                        simulated_s += backend.time_s
                    finally:
                        backend.close()
                    row = {**base, "arm": arm, **observed}
                    if observed.get("arrived"):
                        row["error_s"] = round(observed["time_s"] - target, 6)
                        row["within_tolerance"] = abs(row["error_s"]) <= TOLERANCE_S
                        row["late"] = row["error_s"] > TOLERANCE_S
                    rows.append(row)

    closed = [r for r in rows if r["arm"] == "closed_loop"]
    openl = [r for r in rows if r["arm"] == "open_loop"]
    arrived = [r for r in closed if r.get("arrived")]
    held = [r for r in arrived if r["within_tolerance"]]
    late = [r for r in arrived if r.get("late")]
    lost = [r for r in closed if r.get("feasibility_lost_at_step") is not None]

    if len(arrived) < 4:
        verdict = "RUN_FAILED"
    elif not held:
        verdict = "REFUTATION_REPLICATED"
    elif len(held) == len(arrived):
        verdict = "REFUTATION_NOT_REPLICATED"
    else:
        verdict = "REFUTATION_MIXED"

    # What distinguishes the routes that hold, if any do.
    distinguishing = None
    if held and len(held) < len(arrived):
        failed = [r for r in arrived if not r["within_tolerance"]]
        distinguishing = {
            "held": {
                "count": len(held),
                "junctions_median": statistics.median(
                    [r["junctions_before_station"] for r in held]
                ),
                "distance_median_m": statistics.median([r["station_distance_m"] for r in held]),
                "maps": sorted({r["map_id"] for r in held}),
            },
            "failed": {
                "count": len(failed),
                "junctions_median": statistics.median(
                    [r["junctions_before_station"] for r in failed]
                ),
                "distance_median_m": statistics.median([r["station_distance_m"] for r in failed]),
                "maps": sorted({r["map_id"] for r in failed}),
            },
        }

    errors = [r["error_s"] for r in arrived]
    summary = {
        "package": os.path.basename(package),
        "stage": "W5",
        "claim_class": "replication_of_a_transfer_refutation",
        "verdict": verdict,
        "tolerance_s": TOLERANCE_S,
        "maps": TRAINING_MAPS,
        "judged_on": "the CLOSED-LOOP arm; the open-loop arm is reported alongside it",
        "feasibility": {
            "closed_loop_runs": len(closed),
            "lost_feasibility_mid_flight": len(lost),
            "kept_feasibility_throughout": len(closed) - len(lost),
        },
        "open_loop_comparison": {
            "runs": len(openl),
            "arrived": sum(1 for r in openl if r.get("arrived")),
            "within_tolerance": sum(1 for r in openl if r.get("within_tolerance")),
            "error_median_s": (
                round(statistics.median([r["error_s"] for r in openl if r.get("arrived")]), 6)
                if any(r.get("arrived") for r in openl)
                else None
            ),
        },
        "measurements": {
            "attempted": len(closed),
            "arrived": len(arrived),
            "within_tolerance": len(held),
            "late": len(late),
            "early": len(arrived) - len(held) - len(late),
            "error_min_s": round(min(errors), 6) if errors else None,
            "error_median_s": round(statistics.median(errors), 6) if errors else None,
            "error_max_s": round(max(errors), 6) if errors else None,
            "all_errors_positive": all(e > 0 for e in errors) if errors else None,
        },
        "what_distinguishes_routes_that_hold": distinguishing,
        "relationship_note": (
            "Junction counts are recorded and any relationship is DESCRIBED. Describing a "
            "relationship is not certifying a bound, and nothing here may be fitted into "
            "the arrival construction."
        ),
        "resources": {
            "sumo_process_starts": starts,
            "simulated_seconds": round(simulated_s, 3),
            "wall_seconds": round(time.time() - started_wall, 3),
            "cpu_seconds": round(
                (resource.getrusage(resource.RUSAGE_SELF).ru_utime - started_cpu.ru_utime)
                + (resource.getrusage(resource.RUSAGE_SELF).ru_stime - started_cpu.ru_stime),
                3,
            ),
            "optimizer_updates": 0,
            "checkpoint_loads": 0,
            "test_split_accesses": 0,
        },
    }

    events.append({"ts": stamp, "event": "run_ended", "verdict": verdict})
    with open(os.path.join(package, "events.jsonl"), "w", encoding="utf-8") as h:
        for e in events:
            h.write(json.dumps(e) + "\n")
    with open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as h:
        for r in rows:
            h.write(json.dumps(r) + "\n")
    with open(os.path.join(package, "result.json"), "w", encoding="utf-8") as h:
        json.dump(summary, h, indent=2)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
