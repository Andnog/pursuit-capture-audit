"""Is SUMO deterministic from a fresh start, and does a shared prefix stay coupled?

See the package PROTOCOL_EN.md. Two questions:

Q1 reproducibility - two fresh starts, same seed, same commands: identical trajectories?
Q2 prefix coupling - two fresh starts identical up to decision k and different after:
   are the frames BEFORE k still exactly equal?

Q2 is what the assistance audit needs, and Q1 passing does not imply it.

No capture, no evader, no learning. Commands are a scripted function of the decision index.
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

from joint_interception.domain.contracts import load_domain  # noqa: E402
from joint_interception.simulator.backend import Command  # noqa: E402
from joint_interception.simulator.sumo_adapter import TraciBackend  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from run_traci_first_execution import (  # noqa: E402
    digest,
    first_difference,
    pick_route,
    training_map,
)

#: Scripted schedule. Deterministic in the decision index alone, so two arms issue byte
#: identical commands unless they are deliberately made to differ.
SCHEDULE = (4.0, 9.0, 6.0, 12.0, 7.0, 10.0, 5.0, 11.0)


def scheduled_speed(decision_index: int) -> float:
    return SCHEDULE[decision_index % len(SCHEDULE)]


def run_arm(
    args,
    domain,
    map_record,
    sumo_binary,
    *,
    tag: str,
    imperfection,
    diverge_at: int | None,
    divergent_speed: float,
):
    """Run one fresh SUMO process through the scripted schedule, recording every frame.

    `diverge_at` is the decision index from which this arm departs from the schedule. None
    means it never departs.
    """
    step_s = domain["timing"]["physical_step_s"]
    steps_per_decision = domain["timing"]["physical_steps_per_decision"]
    vehicle = domain["vehicle"]

    backend = TraciBackend(
        map_record["path"],
        seed=args.seed,
        step_s=step_s,
        sumo_binary=sumo_binary,
        label=f"w4_fresh_{tag}",
    )
    frames: list[dict] = []
    commands_issued: list[dict] = []
    try:
        edges = pick_route(backend, map_record["path"], minimum_edges=6)
        backend.add_route("r0", edges)
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

        for decision in range(args.decisions):
            if diverge_at is not None and decision >= diverge_at:
                target = divergent_speed
            else:
                target = scheduled_speed(decision)
            for vid in backend.vehicle_ids():
                backend.queue_command(Command(vid, target))
            commands_issued.append({"decision": decision, "target_speed_mps": target})
            backend.step(steps_per_decision)
            frames.append(
                {
                    "decision": decision,
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
        final_time_s = backend.time_s
    finally:
        backend.close()
    return frames, commands_issued, final_time_s


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--map", default=None)
    parser.add_argument("--pursuers", type=int, default=3)
    parser.add_argument("--decisions", type=int, default=30)
    parser.add_argument("--diverge-at", type=int, default=15)
    parser.add_argument("--divergent-speed", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=20260922)
    parser.add_argument("--reseal", action="store_true")
    args = parser.parse_args()

    package = args.package if os.path.isabs(args.package) else os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    if os.path.isfile(os.path.join(package, "checksums.json")) and not args.reseal:
        print(f"REFUSED: {os.path.basename(package)} is sealed.", file=sys.stderr)
        return 2

    domain = load_domain()
    map_record = training_map(args.map)
    sumo_binary = os.environ.get("SUMO_BINARY") or "sumo"

    started_wall = time.time()
    started_cpu = resource.getrusage(resource.RUSAGE_SELF)
    stamp = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    events = [{"ts": stamp, "event": "run_started", "package": os.path.basename(package)}]
    results: list[dict] = []
    starts = 0
    simulated_s = 0.0

    def arm(tag, imperfection, diverge_at):
        nonlocal starts, simulated_s
        frames, commands, seconds = run_arm(
            args,
            domain,
            map_record,
            sumo_binary,
            tag=tag,
            imperfection=imperfection,
            diverge_at=diverge_at,
            divergent_speed=args.divergent_speed,
        )
        starts += 1
        simulated_s += seconds
        events.append(
            {
                "ts": stamp,
                "event": "arm_completed",
                "arm": tag,
                "imperfection": imperfection,
                "diverge_at": diverge_at,
                "frames": len(frames),
            }
        )
        return frames, commands

    def evaluate(label, imperfection):
        a1, cmd1 = arm(f"{label}1", imperfection, None)
        a2, cmd2 = arm(f"{label}2", imperfection, None)
        b, cmdb = arm(f"{label}B", imperfection, args.diverge_at)

        commands_match = cmd1 == cmd2
        prefix_commands_match = cmd1[: args.diverge_at] == cmdb[: args.diverge_at]
        q1_diff = first_difference(a1, a2)
        q1 = q1_diff is None
        q2_diff = first_difference(a1[: args.diverge_at], b[: args.diverge_at])
        q2 = q2_diff is None
        after_diff = first_difference(a1[args.diverge_at :], b[args.diverge_at :])

        results.append(
            {
                "check_id": f"{label}.Q1",
                "name": "two_fresh_starts_with_identical_commands_are_identical",
                "imperfection": imperfection,
                "arm_1_digest": digest(a1),
                "arm_2_digest": digest(a2),
                "commands_identical": commands_match,
                "exact": q1,
                "first_difference": q1_diff,
                "status": "PASSED" if q1 else "FAILED",
            }
        )
        results.append(
            {
                "check_id": f"{label}.Q2",
                "name": "a_shared_prefix_stays_exactly_equal_when_the_arms_diverge_later",
                "imperfection": imperfection,
                "diverge_at_decision": args.diverge_at,
                "prefix_commands_identical": prefix_commands_match,
                "prefix_a_digest": digest(a1[: args.diverge_at]),
                "prefix_b_digest": digest(b[: args.diverge_at]),
                "exact": q2,
                "first_difference": q2_diff,
                "status": "PASSED" if q2 else "FAILED",
                "note": ("This is what the assistance audit needs. Q1 passing does not imply it."),
            }
        )
        results.append(
            {
                "check_id": f"{label}.Q3",
                "name": "the_arms_actually_diverge_after_the_divergence_point",
                "exact_after": after_diff is None,
                "first_difference_after": after_diff,
                "status": "PASSED" if after_diff is not None else "FAILED",
                "note": (
                    "A control. If the arms did NOT differ after the divergence point the "
                    "command change had no effect and Q2 would be vacuous."
                ),
            }
        )
        return q1, q2

    q1_default, q2_default = evaluate("default", None)

    q1_det = q2_det = None
    if not q1_default:
        events.append(
            {
                "ts": stamp,
                "event": "diagnostic_arm_triggered",
                "reason": "Q1 failed under SUMO defaults",
            }
        )
        q1_det, q2_det = evaluate("deterministic", 0.0)

    ended_cpu = resource.getrusage(resource.RUSAGE_SELF)
    cpu_s = (ended_cpu.ru_utime - started_cpu.ru_utime) + (
        ended_cpu.ru_stime - started_cpu.ru_stime
    )

    effective_q1 = q1_default if q1_default else bool(q1_det)
    effective_q2 = q2_default if q1_default else bool(q2_det)
    if not effective_q1:
        verdict = "NOT_REPRODUCIBLE"
    elif effective_q2:
        verdict = "REPRODUCIBLE_AND_PREFIX_COUPLED"
    else:
        verdict = "REPRODUCIBLE_PREFIX_NOT_COUPLED"

    with open(os.path.join(package, "events.jsonl"), "w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")
    with open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row) + "\n")

    summary = {
        "package": os.path.basename(package),
        "stage": "W4",
        "claim_class": "one_empirical_property_of_sumo",
        "verdict": verdict,
        "questions": {
            "Q1_reproducibility": {
                "sumo_defaults": q1_default,
                "deterministic_car_following": q1_det,
            },
            "Q2_prefix_coupling": {
                "sumo_defaults": q2_default,
                "deterministic_car_following": q2_det,
            },
        },
        "map": {
            "map_id": map_record["map_id"],
            "declared_split": map_record["declared_split"],
            "sha256": map_record["sha256"],
            "opened_read_only": True,
            "copied_or_modified": False,
        },
        "consequence_for_the_assistance_audit": (
            "replay by re-execution is viable"
            if verdict == "REPRODUCIBLE_AND_PREFIX_COUPLED"
            else (
                "replay by re-execution is NOT viable as tested; the audit design must change again"
            )
        ),
        "not_established": [
            "physical feasibility",
            "capture ability",
            "protocol-supported assistance",
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
    with open(os.path.join(package, "result.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
