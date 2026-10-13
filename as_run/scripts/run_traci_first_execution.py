"""First execution of the TraCI call surface. See the package PROTOCOL_EN.md.

This is not a campaign and not a capability trial. It starts a SUMO process, exercises every
method of the `SimulatorBackend` protocol against it, tests whether SUMO's own state
save/load reproduces a continuation exactly, and closes the process.

No capture is attempted and no success is scored. Nothing here supports a claim about
physical feasibility.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import resource
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from joint_interception.domain.contracts import load_domain  # noqa: E402
from joint_interception.simulator.backend import Command  # noqa: E402
from joint_interception.simulator.sumo_adapter import TraciBackend  # noqa: E402

MAPS_STATUS = os.path.join(ROOT, "MAPS_STATUS.json")


def training_map(map_id: str | None) -> dict:
    """Return a TRAINING map record. Refuses any map declared TEST."""
    with open(MAPS_STATUS, encoding="utf-8") as handle:
        status = json.load(handle)
    test_ids = set(status["usable_by_declared_split"]["test"])
    train_ids = status["usable_by_declared_split"]["train"]
    chosen = map_id or train_ids[0]
    if chosen in test_ids:
        raise SystemExit(f"REFUSED: {chosen} is a TEST map. This package may not open one.")
    if chosen not in train_ids:
        raise SystemExit(f"REFUSED: {chosen} is not in the TRAINING split {train_ids}.")
    for record in status["maps"]:
        if record["map_id"] == chosen:
            return record
    raise SystemExit(f"map {chosen} not found in MAPS_STATUS.json")


def pick_route(backend: TraciBackend, net_path: str, minimum_edges: int) -> list[str]:
    """Find a connected route of at least `minimum_edges` edges, using SUMO's own router."""
    import sumolib

    net = sumolib.net.readNet(net_path)
    edges = [
        edge
        for edge in net.getEdges()
        if edge.allows("passenger") and edge.getLength() > 50.0 and not edge.isSpecial()
    ]
    edges.sort(key=lambda e: e.getID())
    for start in edges[:40]:
        for end in reversed(edges[:400]):
            if start.getID() == end.getID():
                continue
            found = backend.find_route_edges(start.getID(), end.getID())
            if len(found) >= minimum_edges:
                return found
    raise SystemExit("no route of the required length was found on this network")


def trajectory(backend: TraciBackend, steps: int) -> list[dict]:
    """Advance `steps` physical steps, recording every vehicle's full state each step."""
    frames = []
    for _ in range(steps):
        backend.step(1)
        frames.append(
            {
                "time_s": backend.time_s,
                "vehicles": [
                    {
                        "vehicle_id": state.vehicle_id,
                        "x": state.x,
                        "y": state.y,
                        "heading_rad": state.heading_rad,
                        "speed_mps": state.speed_mps,
                        "lane_id": state.lane_id,
                        "lane_position_m": state.lane_position_m,
                    }
                    for state in (backend.vehicle_state(vid) for vid in backend.vehicle_ids())
                ],
            }
        )
    return frames


def digest(frames: list[dict]) -> str:
    return hashlib.sha256(
        json.dumps(frames, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def first_difference(left: list[dict], right: list[dict]) -> dict | None:
    """Return the first exact difference between two trajectories, or None."""
    if len(left) != len(right):
        return {"kind": "length", "left": len(left), "right": len(right)}
    for index, (a, b) in enumerate(zip(left, right, strict=True)):
        if a != b:
            detail = {"kind": "frame", "frame_index": index, "time_s": a["time_s"]}
            for va, vb in zip(a["vehicles"], b["vehicles"], strict=False):
                if va != vb:
                    detail["vehicle_id"] = va["vehicle_id"]
                    detail["fields"] = {
                        key: {"first_run": va[key], "second_run": vb[key]}
                        for key in va
                        if va[key] != vb[key]
                    }
                    break
            return detail
    return None


def exercise(args, domain, map_record, sumo_binary, *, imperfection, tag, extra_args=None):
    """Run one arm: start SUMO, exercise the surface, test restoration, close.

    `imperfection` is the Krauss driver-imperfection parameter (sigma). SUMO's default of
    0.5 is stochastic. Passing 0.0 makes the car-following deterministic, which separates
    "SUMO cannot restore state" from "SUMO restores state but not the random stream".
    """
    step_s = domain["timing"]["physical_step_s"]
    vehicle = domain["vehicle"]
    stamp = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    events = []
    results = []
    final_time_s = 0.0

    backend = TraciBackend(
        map_record["path"],
        seed=args.seed,
        step_s=step_s,
        sumo_binary=sumo_binary,
        label=f"w4_first_execution_{tag}",
        extra_args=extra_args,
    )
    events.append(
        {
            "ts": stamp,
            "arm": tag,
            "event": "sumo_process_started",
            "map_id": map_record["map_id"],
            "declared_split": map_record["declared_split"],
            "imperfection": imperfection,
            "extra_args": extra_args,
            "command": backend.start_command(),
        }
    )

    try:
        edges = pick_route(backend, map_record["path"], minimum_edges=6)
        backend.add_route("r0", edges)
        results.append(
            {
                "check_id": f"{tag}.T1",
                "name": "route_found",
                "observed": {"edges": len(edges), "first": edges[0], "last": edges[-1]},
                "status": "PASSED",
            }
        )

        for index in range(args.pursuers):
            vid = f"p{index + 1}"
            backend.add_vehicle(
                vid,
                "r0",
                type_id="DEFAULT_VEHTYPE",
                depart_position_m=index * 25.0,
                depart_speed_mps=0.0,
                body_length_m=vehicle["body_length_m"],
                body_width_m=vehicle["body_width_m"],
                min_gap_m=vehicle["min_gap_m"],
                imperfection=imperfection,
            )
            backend.assign_class(vid, "pursuer")
        backend.step(1)

        live = backend.vehicle_ids()
        results.append(
            {
                "check_id": f"{tag}.T2",
                "name": "vehicles_present",
                "expected": args.pursuers,
                "observed": len(live),
                "ids": live,
                "status": "PASSED" if len(live) == args.pursuers else "FAILED",
            }
        )

        state = backend.vehicle_state(live[0])
        body_ok = (
            abs(state.body_length_m - vehicle["body_length_m"]) < 1e-9
            and abs(state.body_width_m - vehicle["body_width_m"]) < 1e-9
        )
        results.append(
            {
                "check_id": f"{tag}.T3",
                "name": "body_dimensions_come_from_the_contract_not_a_sumo_default",
                "expected": {
                    "length_m": vehicle["body_length_m"],
                    "width_m": vehicle["body_width_m"],
                },
                "observed": {"length_m": state.body_length_m, "width_m": state.body_width_m},
                "status": "PASSED" if body_ok else "FAILED",
            }
        )

        lane_length = backend.lane_length_m(state.lane_id)
        results.append(
            {
                "check_id": f"{tag}.T4",
                "name": "lane_length_readable",
                "observed": {"lane_id": state.lane_id, "length_m": lane_length},
                "status": "PASSED" if lane_length > 0 else "FAILED",
            }
        )

        backend.queue_command(Command(live[0], 5.0))
        queued = backend.pending_commands()
        results.append(
            {
                "check_id": f"{tag}.T5",
                "name": "command_queue_round_trip",
                "observed": {vid: c.target_speed_mps for vid, c in queued.items()},
                "status": "PASSED" if queued[live[0]].target_speed_mps == 5.0 else "FAILED",
            }
        )

        commanded = 5.0
        backend.step(10)
        executed = backend.vehicle_state(live[0]).speed_mps
        results.append(
            {
                "check_id": f"{tag}.T6",
                "name": "commanded_speed_is_a_request_not_a_guarantee",
                "commanded_mps": commanded,
                "executed_mps": executed,
                "equal": executed == commanded,
                "status": "OBSERVED",
                "note": (
                    "SUMO's safety layer is left ON, so the executed speed may differ from "
                    "the request. Recorded, not corrected: it is the same "
                    "proposed-versus-executed separation the task contract requires."
                ),
            }
        )

        backend.step(args.prefix_steps)
        state_path = os.path.join(args.package_dir, f"sumo_state_prefix_{tag}.xml")
        backend.use_state_path(state_path)
        captured = backend.capture_state()

        first = trajectory(backend, args.replay_steps)
        backend.restore_state(captured)
        restored_time = backend.time_s
        second = trajectory(backend, args.replay_steps)

        difference = first_difference(first, second)
        exact = difference is None
        results.append(
            {
                "check_id": f"{tag}.T7",
                "name": "state_restoration_reproduces_the_continuation_exactly",
                "imperfection": imperfection,
                "prefix_steps": args.prefix_steps,
                "replay_steps": args.replay_steps,
                "captured_time_s": captured["time_s"],
                "time_after_restore_s": restored_time,
                "first_run_digest": digest(first),
                "second_run_digest": digest(second),
                "exact": exact,
                "first_difference": difference,
                "status": "PASSED" if exact else "FAILED",
                "note": (
                    "Compared by exact equality, never within a tolerance. The protocol "
                    "forbids loosening this comparison after seeing its result, and it was "
                    "not loosened: both arms use the same comparison."
                ),
            }
        )
        events.append({"ts": stamp, "arm": tag, "event": "restoration_tested", "exact": exact})
        final_time_s = backend.time_s
    finally:
        backend.close()
        events.append({"ts": stamp, "arm": tag, "event": "sumo_process_closed"})

    return results, events, final_time_s


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--map", default=None)
    parser.add_argument("--pursuers", type=int, default=3)
    parser.add_argument("--prefix-steps", type=int, default=100)
    parser.add_argument("--replay-steps", type=int, default=150)
    parser.add_argument("--seed", type=int, default=20260922)
    parser.add_argument("--reseal", action="store_true")
    args = parser.parse_args()

    package = args.package if os.path.isabs(args.package) else os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    if os.path.isfile(os.path.join(package, "checksums.json")) and not args.reseal:
        print(f"REFUSED: {os.path.basename(package)} is sealed.", file=sys.stderr)
        return 2
    args.package_dir = package

    domain = load_domain()
    map_record = training_map(args.map)
    sumo_binary = os.environ.get("SUMO_BINARY") or "sumo"

    started_wall = time.time()
    started_cpu = resource.getrusage(resource.RUSAGE_SELF)
    stamp = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    events = [{"ts": stamp, "event": "run_started", "package": os.path.basename(package)}]
    results: list[dict] = []
    simulated_s = 0.0

    # Arm A is the protocol's primary test, under SUMO's own defaults.
    # Arm B is a DIAGNOSTIC that isolates the cause of an arm-A failure. It is not a retry:
    # the comparison is identical and arm A's verdict stands whatever arm B shows.
    arms = [
        ("A", None, None),
        ("B", 0.0, None),
        ("C", 0.0, ["--precision", "12"]),
    ]
    for tag, imperfection, extra in arms:
        arm_results, arm_events, arm_time = exercise(
            args,
            domain,
            map_record,
            sumo_binary,
            imperfection=imperfection,
            tag=tag,
            extra_args=extra,
        )
        results += arm_results
        events += arm_events
        simulated_s += arm_time

    ended_cpu = resource.getrusage(resource.RUSAGE_SELF)
    cpu_s = (ended_cpu.ru_utime - started_cpu.ru_utime) + (
        ended_cpu.ru_stime - started_cpu.ru_stime
    )

    arm_a = next(r for r in results if r["check_id"] == "A.T7")
    arm_b = next(r for r in results if r["check_id"] == "B.T7")
    arm_c = next(r for r in results if r["check_id"] == "C.T7")
    surface_ok = all(
        r.get("status") in ("PASSED", "OBSERVED")
        for r in results
        if not r["check_id"].endswith("T7")
    )
    if not surface_ok:
        verdict = "SURFACE_INCOMPLETE"
    elif arm_a["exact"]:
        verdict = "SURFACE_EXERCISED_RESTORATION_EXACT"
    else:
        verdict = "SURFACE_EXERCISED_RESTORATION_INEXACT"

    if arm_a["exact"]:
        diagnosis = "not applicable; the primary arm restored exactly"
    elif arm_b["exact"]:
        diagnosis = (
            "UNRESTORED RANDOMNESS, not an inability to restore state. With Krauss driver "
            "imperfection (sigma) at SUMO's stochastic default the continuation diverges; "
            "with sigma = 0 the same save/load reproduces the continuation EXACTLY. SUMO's "
            "state file therefore carries the vehicle state but not the random stream that "
            "drives car-following noise."
        )
    elif arm_c["exact"]:
        diagnosis = (
            "WRITE PRECISION, and randomness on top of it. SUMO's state file serialises "
            "positions and speeds at --precision digits, default 2, so loadState restores a "
            "state rounded to centimetres and the continuation proceeds correctly from the "
            "WRONG state. With deterministic car-following AND --precision 12 the same "
            "save/load reproduces the continuation EXACTLY. Replay coupling is therefore "
            "achievable, but ONLY under both conditions, and neither is a SUMO default."
        )
    else:
        diagnosis = (
            "NOT EXPLAINED BY RANDOMNESS OR BY WRITE PRECISION. The continuation diverges "
            "even with deterministic car-following at --precision 12, so saveState/loadState "
            "does not reproduce a continuation exactly on this platform. The assistance "
            "audit's replay coupling cannot rest on it."
        )

    with open(os.path.join(package, "events.jsonl"), "w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")
    with open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row) + "\n")

    summary = {
        "package": os.path.basename(package),
        "stage": "W4",
        "claim_class": "software_correctness_and_one_empirical_property_of_sumo",
        "verdict": verdict,
        "map": {
            "map_id": map_record["map_id"],
            "declared_split": map_record["declared_split"],
            "sha256": map_record["sha256"],
            "opened_read_only": True,
            "copied_or_modified": False,
        },
        "restoration": {
            "arm_a_sumo_defaults": {
                "imperfection": "SUMO default (0.5, stochastic)",
                "exact": arm_a["exact"],
                "first_difference": arm_a["first_difference"],
            },
            "arm_b_deterministic_car_following": {
                "imperfection": 0.0,
                "sumo_precision": "default (2)",
                "exact": arm_b["exact"],
                "first_difference": arm_b["first_difference"],
            },
            "arm_c_deterministic_and_high_precision": {
                "imperfection": 0.0,
                "sumo_precision": 12,
                "exact": arm_c["exact"],
                "first_difference": arm_c["first_difference"],
            },
            "diagnosis": diagnosis,
        },
        "not_established": [
            "physical feasibility",
            "capture ability",
            "protocol-supported assistance",
            "anything O22 guards",
        ],
        "resources": {
            "sumo_process_starts": len(arms),
            "simulated_seconds": round(simulated_s, 3),
            "wall_seconds": round(time.time() - started_wall, 3),
            "cpu_seconds": round(cpu_s, 3),
            "optimizer_updates": 0,
            "checkpoint_loads": 0,
            "test_split_accesses": 0,
        },
    }
    with open(os.path.join(package, "result.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print(json.dumps(summary, indent=2))
    return 0 if verdict.startswith("SURFACE_EXERCISED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
