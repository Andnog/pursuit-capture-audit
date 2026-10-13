"""Does a constructively computed arrival time hold on a real SUMO network?

See the package PROTOCOL_EN.md. `UNDER` means a time is ACHIEVABLE. In the finite
abstraction that is a theorem about an integral. On a lane network it is a claim about
reality, and this is the first test of it.

A late arrival refutes `UNDER` on the network. An early arrival is a different failure: the
arrival set asserts arrival AT t, not BY t.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import resource
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from joint_interception.domain.contracts import load_domain  # noqa: E402
from joint_interception.opportunities.interaction import (  # noqa: E402
    ConsistencyVerdict,
    Lane,
    Participant,
    solve_mutual_consistency,
)
from joint_interception.opportunities.schedule import (  # noqa: E402
    arrival_at,
    constructive_arrival_set,
    earliest_arrival,
)
from joint_interception.simulator.sumo_adapter import TraciBackend  # noqa: E402
from run_traci_first_execution import pick_route, training_map  # noqa: E402

#: Declared in the protocol before any run: arrival is observed once per physical step, so
#: below that resolution equality is not observable. Never widened afterwards.
TOLERANCE_S = 0.1


def route_speed_limit(backend: TraciBackend, edges: list[str]) -> tuple[float, list[float]]:
    """Minimum allowed speed over the route's edges.

    The abstraction carries ONE speed limit. Taking the minimum makes the profile legal
    everywhere on the route rather than only on average; taking the mean would let the
    schedule assume a speed the vehicle may not use on some edge.
    """
    limits = []
    for edge in edges:
        lane_count = backend._connection.edge.getLaneNumber(edge)
        limits.append(
            min(backend._connection.lane.getMaxSpeed(f"{edge}_{i}") for i in range(lane_count))
        )
    return min(limits), limits


def speeds_from_profile(profile, step_s: float) -> list[float]:
    """Sample the constructive profile into one commanded speed per physical step."""
    speeds = []
    speed = profile.initial_speed_mps
    for segment in profile.segments:
        steps = int(round(segment.duration_s / step_s))
        for _ in range(steps):
            speed += segment.acceleration_mps2 * step_s
            speeds.append(max(0.0, speed))
    return speeds


#: `getDrivingDistance` returns this when the target is not reachable ahead of the vehicle.
#: The first run of this package read it as an arrival, because -2^30 satisfies `<= 0`.
INVALID_DOUBLE = -1073741824.0


def drive_to_station(
    backend: TraciBackend,
    vehicle_id: str,
    station_distance_m: float,
    commanded: list[float],
    step_s: float,
    max_steps: int,
):
    """Follow the commanded speeds, recording when the station distance is covered.

    Arrival is measured on the **odometer** (`getDistance`), which is monotone and has no
    sentinel. The first version of this function used `getDrivingDistance` and tested
    `distance <= 0`, which read SUMO's invalid-value sentinel as an arrival.

    When the profile runs out, speed control is **released** (`setSpeed(-1)`) rather than
    set to zero. Commanding zero made a vehicle that was already behind schedule stop
    permanently, so lateness could not be measured at all - the run reported "not reached"
    where the honest answer was "reached late".
    """
    origin = backend._connection.vehicle.getDistance(vehicle_id)
    clamped_steps = 0
    released_at = None
    for index in range(max_steps):
        if vehicle_id not in backend._connection.vehicle.getIDList():
            return {
                "arrived": False,
                "reason": "vehicle left the network",
                "covered_m": None,
                "released_at_step": released_at,
            }
        covered = backend._connection.vehicle.getDistance(vehicle_id) - origin
        if covered == INVALID_DOUBLE:
            return {"arrived": False, "reason": "odometer returned the invalid sentinel"}
        if covered >= station_distance_m:
            return {
                "arrived": True,
                "time_s": backend.time_s,
                "step_index": index,
                "covered_m": covered,
                "overshoot_m": covered - station_distance_m,
                "clamped_steps": clamped_steps,
                "released_at_step": released_at,
            }
        if index < len(commanded):
            target = commanded[index]
            backend._connection.vehicle.setSpeed(vehicle_id, target)
            backend.step(1)
            executed = backend._connection.vehicle.getSpeed(vehicle_id)
            if abs(executed - target) > 1e-6:
                clamped_steps += 1
        else:
            if released_at is None:
                released_at = index
                backend._connection.vehicle.setSpeed(vehicle_id, -1)
            backend.step(1)
    return {
        "arrived": False,
        "reason": "station not reached within the step budget",
        "covered_m": backend._connection.vehicle.getDistance(vehicle_id) - origin,
        "required_m": station_distance_m,
        "released_at_step": released_at,
    }


def drive_many(
    backend: TraciBackend,
    plans: dict[str, dict],
    step_s: float,
    max_steps: int,
) -> dict[str, dict]:
    """Drive several vehicles CONCURRENTLY, recording each arrival as it happens.

    The first version of arm 2 drove participants one after another. Every vehicle in a
    SUMO process advances on every `simulationStep`, so by the time the second was driven it
    had already left the network. Sequential driving of a shared simulation is not a
    simplification; it is a different experiment, and a broken one.

    `plans[vid]` carries `commanded` (one speed per step) and `distance_m` (that vehicle's
    own driving distance to the station, measured rather than assumed).
    """
    origins = {vid: backend._connection.vehicle.getDistance(vid) for vid in plans}
    outcomes: dict[str, dict] = {}
    clamped = dict.fromkeys(plans, 0)
    released: dict[str, int | None] = dict.fromkeys(plans, None)

    for index in range(max_steps):
        live = set(backend._connection.vehicle.getIDList())
        for vid, plan in plans.items():
            if vid in outcomes:
                continue
            if vid not in live:
                outcomes[vid] = {
                    "arrived": False,
                    "reason": "vehicle left the network before reaching the station",
                    "released_at_step": released[vid],
                }
                continue
            covered = backend._connection.vehicle.getDistance(vid) - origins[vid]
            if covered == INVALID_DOUBLE:
                outcomes[vid] = {"arrived": False, "reason": "odometer returned the sentinel"}
                continue
            if covered >= plan["distance_m"]:
                outcomes[vid] = {
                    "arrived": True,
                    "time_s": backend.time_s,
                    "step_index": index,
                    "covered_m": covered,
                    "overshoot_m": covered - plan["distance_m"],
                    "clamped_steps": clamped[vid],
                    "released_at_step": released[vid],
                }
        if len(outcomes) == len(plans):
            break
        for vid, plan in plans.items():
            if vid in outcomes or vid not in live:
                continue
            commanded = plan["commanded"]
            if index < len(commanded):
                backend._connection.vehicle.setSpeed(vid, commanded[index])
            elif released[vid] is None:
                released[vid] = index
                backend._connection.vehicle.setSpeed(vid, -1)
        backend.step(1)
        live_after = set(backend._connection.vehicle.getIDList())
        for vid, plan in plans.items():
            if vid in outcomes or vid not in live_after or index >= len(plan["commanded"]):
                continue
            executed = backend._connection.vehicle.getSpeed(vid)
            if abs(executed - plan["commanded"][index]) > 1e-6:
                clamped[vid] += 1

    for vid, plan in plans.items():
        if vid not in outcomes:
            outcomes[vid] = {
                "arrived": False,
                "reason": "station not reached within the step budget",
                "required_m": plan["distance_m"],
                "released_at_step": released[vid],
            }
    return outcomes


def build(backend, edges, domain, vehicles):
    vehicle = domain["vehicle"]
    backend.add_route("r0", edges)
    for index, vid in enumerate(vehicles):
        backend.add_vehicle(
            vid,
            "r0",
            type_id="DEFAULT_VEHTYPE",
            depart_position_m=0.0 if len(vehicles) == 1 else index * 20.0,
            depart_speed_mps=0.0,
            body_length_m=vehicle["body_length_m"],
            body_width_m=vehicle["body_width_m"],
            min_gap_m=vehicle["min_gap_m"],
        )
        backend.assign_class(vid, "pursuer")
    backend.step(1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--map", default=None)
    parser.add_argument("--seed", type=int, default=20260922)
    parser.add_argument("--reseal", action="store_true")
    args = parser.parse_args()
    package = args.package if os.path.isabs(args.package) else os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    if os.path.isfile(os.path.join(package, "checksums.json")) and not args.reseal:
        print(f"REFUSED: {os.path.basename(package)} is sealed.", file=sys.stderr)
        return 2

    domain = load_domain()
    step_s = domain["timing"]["physical_step_s"]
    vehicle = domain["vehicle"]
    map_record = training_map(args.map)
    sumo_binary = os.environ.get("SUMO_BINARY") or "sumo"

    started_wall = time.time()
    started_cpu = resource.getrusage(resource.RUSAGE_SELF)
    stamp = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    events = [{"ts": stamp, "event": "run_started", "package": os.path.basename(package)}]
    results = []
    starts = 0
    simulated_s = 0.0

    # -- geometry, fixed before any target time is chosen ---------------------------
    probe = TraciBackend(
        map_record["path"], seed=args.seed, step_s=step_s, sumo_binary=sumo_binary, label="geom"
    )
    starts += 1
    try:
        edges = pick_route(probe, map_record["path"], minimum_edges=6)
        limit, per_edge = route_speed_limit(probe, edges)
        build(probe, edges, domain, ["probe"])
        total = probe._connection.vehicle.getDrivingDistance(
            "probe", edges[-1], probe._connection.lane.getLength(f"{edges[-1]}_0")
        )
        station_index = max(1, int(len(edges) * 0.6))
        station_edge = edges[station_index]
        station_lane_length = probe._connection.lane.getLength(f"{station_edge}_0")
        station_pos = station_lane_length * 0.5
        station_distance = probe._connection.vehicle.getDrivingDistance(
            "probe", station_edge, station_pos
        )
        simulated_s += probe.time_s
    finally:
        probe.close()

    geometry = {
        "route_edges": len(edges),
        "route_drivable_length_m": round(total, 3),
        "station_edge": station_edge,
        "station_position_m": round(station_pos, 3),
        "station_driving_distance_m": round(station_distance, 3),
        "route_speed_limit_min_mps": round(limit, 3),
        "route_speed_limits_mps": [round(v, 3) for v in per_edge],
        "speed_limit_choice": "minimum over the route's edges, so the profile is legal everywhere",
    }
    events.append({"ts": stamp, "event": "geometry_fixed", **geometry})

    accel = 2.6
    decel = 4.5
    witness = constructive_arrival_set(
        "p1", station_distance, 0.0, limit, accel, decel, horizon_s=300.0
    )
    if witness is None:
        print("REFUSED: the station is unreachable in the abstraction", file=sys.stderr)
        return 1
    earliest = witness.earliest_s
    targets = [earliest, earliest * 1.25, earliest * 1.6, earliest * 2.0]

    # -- Arm 1: kinematics alone ----------------------------------------------------
    arm1 = []
    for target in targets:
        profile = arrival_at(station_distance, 0.0, limit, accel, decel, target)
        if profile is None:
            arm1.append({"target_s": target, "arrived": False, "reason": "no profile"})
            continue
        backend = TraciBackend(
            map_record["path"],
            seed=args.seed,
            step_s=step_s,
            sumo_binary=sumo_binary,
            label=f"arm1_{len(arm1)}",
        )
        starts += 1
        try:
            build(backend, edges, domain, ["p1"])
            observed = drive_to_station(
                backend,
                "p1",
                station_distance,
                speeds_from_profile(profile, step_s),
                step_s,
                max_steps=int(300.0 / step_s),
            )
            simulated_s += backend.time_s
        finally:
            backend.close()
        row = {"target_s": round(target, 6), **observed}
        if observed.get("arrived"):
            row["error_s"] = round(observed["time_s"] - target, 6)
            row["late"] = row["error_s"] > TOLERANCE_S
            row["early"] = row["error_s"] < -TOLERANCE_S
            row["within_tolerance"] = abs(row["error_s"]) <= TOLERANCE_S
        arm1.append(row)

    arrived = [r for r in arm1 if r.get("arrived")]
    arm1_ok = bool(arrived) and all(r["within_tolerance"] for r in arrived)
    results.append(
        {
            "check_id": "A1",
            "name": "a_constructive_arrival_time_holds_on_the_network",
            "tolerance_s": TOLERANCE_S,
            "targets": arm1,
            "arrived": len(arrived),
            "within_tolerance": sum(1 for r in arrived if r["within_tolerance"]),
            "worst_error_s": (
                round(max((abs(r["error_s"]) for r in arrived), default=0.0), 6)
                if arrived
                else None
            ),
            "status": "PASSED" if arm1_ok else "FAILED",
        }
    )

    # -- Arm 2: the mutual-consistency witness --------------------------------------
    lane = Lane("station", 14.0, vehicle["body_length_m"], vehicle["min_gap_m"])
    participants = [
        Participant(f"p{i + 1}", station_distance + i * 20.0, 0.0, limit, accel, decel)
        for i in range(3)
    ]
    consistency = solve_mutual_consistency(
        participants,
        lane,
        horizon_s=300.0,
        dwell_s=domain["capture_predicate"]["parameters"]["dwell_time_s"]["value"],
        grid=7,
    )
    arm2 = {"consistency_verdict": consistency.verdict.value, "arrivals": []}
    arm2_ok = False
    if consistency.verdict is ConsistencyVerdict.WITNESS_VERIFIED:
        backend = TraciBackend(
            map_record["path"], seed=args.seed, step_s=step_s, sumo_binary=sumo_binary, label="arm2"
        )
        starts += 1
        try:
            build(backend, edges, domain, [p.participant_id for p in participants])
            plans = {}
            for p, c in zip(participants, consistency.commitments, strict=True):
                own_distance = backend._connection.vehicle.getDrivingDistance(
                    p.participant_id, station_edge, station_pos
                )
                profile = arrival_at(own_distance, 0.0, limit, accel, decel, c.arrival_s)
                plans[p.participant_id] = {
                    "distance_m": own_distance,
                    "commanded": speeds_from_profile(profile, step_s) if profile else [],
                    "committed_s": c.arrival_s,
                    "profile_found": profile is not None,
                }
            outcomes = drive_many(backend, plans, step_s, max_steps=int(300.0 / step_s))
            for vid, plan in plans.items():
                row = {
                    "participant": vid,
                    "committed_s": round(plan["committed_s"], 6),
                    "own_distance_m": round(plan["distance_m"], 3),
                    "profile_found": plan["profile_found"],
                    **outcomes[vid],
                }
                if row.get("arrived"):
                    row["error_s"] = round(row["time_s"] - plan["committed_s"], 6)
                    row["within_tolerance"] = abs(row["error_s"]) <= TOLERANCE_S
                arm2["arrivals"].append(row)
            simulated_s += backend.time_s
        finally:
            backend.close()
        got = [r for r in arm2["arrivals"] if r.get("arrived")]
        arm2_ok = len(got) == len(participants) and all(r["within_tolerance"] for r in got)
    results.append(
        {
            "check_id": "A2",
            "name": "a_mutually_consistent_commitment_set_holds_on_the_network",
            "tolerance_s": TOLERANCE_S,
            **arm2,
            "status": "PASSED" if arm2_ok else "FAILED",
            "note": (
                "Arm 2 drives all three participants CONCURRENTLY in one process and "
                "measures each one's own driving distance to the station rather than "
                "assuming it. It tests the committed TIMES, not simultaneous lane occupancy."
            ),
        }
    )

    ended_cpu = resource.getrusage(resource.RUSAGE_SELF)
    cpu_s = (ended_cpu.ru_utime - started_cpu.ru_utime) + (
        ended_cpu.ru_stime - started_cpu.ru_stime
    )
    if not arrived:
        verdict = "RUN_FAILED"
    elif arm1_ok and arm2_ok:
        verdict = "CONSTRUCTIVE_TIMES_HOLD"
    elif arm1_ok:
        verdict = "CONSTRUCTIVE_TIMES_HOLD_ARM_1_ONLY"
    else:
        verdict = "CONSTRUCTIVE_TIMES_FAIL"

    events.append({"ts": stamp, "event": "run_ended", "verdict": verdict})
    with open(os.path.join(package, "events.jsonl"), "w", encoding="utf-8") as h:
        for e in events:
            h.write(json.dumps(e) + "\n")
    with open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as h:
        for r in results:
            h.write(json.dumps(r) + "\n")

    summary = {
        "package": os.path.basename(package),
        "stage": "W5",
        "claim_class": "does_an_abstraction_level_result_transfer_to_the_simulator",
        "verdict": verdict,
        "tolerance_s": TOLERANCE_S,
        "tolerance_justification": (
            "arrival is observed once per 0.1 s physical step; below the simulator's own "
            "resolution equality is not observable. Declared before any run."
        ),
        "geometry": geometry,
        "map": {
            "map_id": map_record["map_id"],
            "declared_split": map_record["declared_split"],
            "sha256": map_record["sha256"],
            "opened_read_only": True,
        },
        "not_established": [
            "capture, assistance, learning, benefit, transfer or novelty",
            "simultaneous lane occupancy under the capacity constraint on the network",
            "anything O22 guards",
        ],
        "resources": {
            "sumo_process_starts": starts,
            "simulated_seconds": round(simulated_s, 3),
            "wall_seconds": round(time.time() - started_wall, 3),
            "cpu_seconds": round(cpu_s, 3),
            "optimizer_updates": 0,
            "checkpoint_loads": 0,
            "test_split_accesses": 0,
        },
    }
    with open(os.path.join(package, "result.json"), "w", encoding="utf-8") as h:
        json.dump(summary, h, indent=2)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def drive_closed_loop(
    backend: TraciBackend,
    vehicle_id: str,
    station_distance_m: float,
    target_s: float,
    limit_mps: float,
    accel: float,
    decel: float,
    step_s: float,
    max_steps: int,
):
    """Re-plan every step, and record the step at which the target becomes infeasible.

    Open-loop execution of a time-indexed profile measures something narrower than
    achievability: once the vehicle falls behind, every later command corresponds to a
    position it is not at, and the initial deviation is amplified. This asks the honest
    question instead - **at this instant, does a legal schedule landing at `target_s` still
    exist from where the vehicle actually is?**

    Losing feasibility mid-flight is the refutation, and it is a sharper statement than an
    arrival error: it names the moment the claim stopped being true.
    """
    origin = backend._connection.vehicle.getDistance(vehicle_id)
    start_time = backend.time_s
    lost_at = None
    lost_detail = None
    clamped_steps = 0

    for index in range(max_steps):
        if vehicle_id not in backend._connection.vehicle.getIDList():
            return {"arrived": False, "reason": "vehicle left the network", "lost_at_step": lost_at}
        covered = backend._connection.vehicle.getDistance(vehicle_id) - origin
        if covered == INVALID_DOUBLE:
            return {"arrived": False, "reason": "odometer returned the sentinel"}
        if covered >= station_distance_m:
            return {
                "arrived": True,
                "time_s": backend.time_s,
                "step_index": index,
                "covered_m": covered,
                "clamped_steps": clamped_steps,
                "feasibility_lost_at_step": lost_at,
                "feasibility_lost_detail": lost_detail,
            }

        remaining_m = station_distance_m - covered
        remaining_s = target_s - (backend.time_s - start_time)
        speed = backend._connection.vehicle.getSpeed(vehicle_id)

        profile = None
        if remaining_s > step_s / 2:
            profile = arrival_at(remaining_m, speed, limit_mps, accel, decel, remaining_s)
        if profile is None and lost_at is None:
            lost_at = index
            lost_detail = {
                "time_s": backend.time_s,
                "remaining_distance_m": round(remaining_m, 3),
                "remaining_time_s": round(remaining_s, 3),
                "speed_mps": round(speed, 3),
                "fastest_possible_s": round(
                    earliest_arrival(remaining_m, speed, limit_mps, accel)[0], 3
                ),
            }

        if profile is not None and profile.segments:
            commanded = max(0.0, speed + profile.segments[0].acceleration_mps2 * step_s)
            backend._connection.vehicle.setSpeed(vehicle_id, commanded)
            backend.step(1)
            if abs(backend._connection.vehicle.getSpeed(vehicle_id) - commanded) > 1e-6:
                clamped_steps += 1
        else:
            # Feasibility is gone. Drive as fast as legal, so the actual arrival is measured
            # rather than the vehicle being left to stall.
            backend._connection.vehicle.setSpeed(vehicle_id, -1)
            backend.step(1)

    return {
        "arrived": False,
        "reason": "station not reached within the step budget",
        "feasibility_lost_at_step": lost_at,
        "feasibility_lost_detail": lost_detail,
    }
