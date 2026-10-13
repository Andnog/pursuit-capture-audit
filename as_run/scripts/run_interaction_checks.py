"""The interaction half as an evidence package. See the package PROTOCOL_EN.md.

Analytical only: no simulator, no optimizer, no checkpoint, no TEST access.
"""

from __future__ import annotations

import argparse
import datetime
import itertools
import json
import os
import resource
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from joint_interception.opportunities.interaction import (  # noqa: E402
    ConsistencyVerdict,
    Lane,
    Participant,
    _contains,
    max_concurrent,
    solve_mutual_consistency,
)

LANE = Lane("shared", length_m=14.0, body_length_m=5.0, min_gap_m=2.5)


def p(pid: str, distance_m: float) -> Participant:
    return Participant(pid, distance_m, 0.0, 13.89, 2.6, 4.5)


def pairwise_peak(windows):
    return max(max_concurrent([a, b]) for a, b in itertools.combinations(windows, 2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--reseal", action="store_true")
    args = parser.parse_args()
    package = args.package if os.path.isabs(args.package) else os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    if os.path.isfile(os.path.join(package, "checksums.json")) and not args.reseal:
        print(f"REFUSED: {os.path.basename(package)} is sealed.", file=sys.stderr)
        return 2

    started_wall = time.time()
    started_cpu = resource.getrusage(resource.RUSAGE_SELF)
    stamp = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    events = [{"ts": stamp, "event": "run_started", "package": os.path.basename(package)}]
    results = []

    # C1 - capacity arithmetic agrees with the frozen lane-capacity witness
    results.append(
        {
            "check_id": "C1",
            "name": "capacity_agrees_with_the_frozen_lane_witness",
            "lane_length_m": LANE.length_m,
            "two_bodies_require_m": 2 * 5.0 + 1 * 2.5,
            "three_bodies_require_m": 3 * 5.0 + 2 * 2.5,
            "capacity": LANE.capacity(),
            "status": "PASSED" if LANE.capacity() == 2 else "FAILED",
        }
    )

    # C2 - negative control: pairwise passes, joint fails
    simultaneous = [(0.0, 3.0), (1.0, 4.0), (2.0, 5.0)]
    sequential = [(0.0, 2.0), (1.0, 3.0), (2.5, 4.0)]
    results.append(
        {
            "check_id": "C2",
            "name": "pairwise_is_unsound_as_a_team_certificate",
            "simultaneous_pairwise_peak": pairwise_peak(simultaneous),
            "simultaneous_joint_peak": max_concurrent(simultaneous),
            "sequential_joint_peak": max_concurrent(sequential),
            "capacity": LANE.capacity(),
            "status": (
                "PASSED"
                if pairwise_peak(simultaneous) <= LANE.capacity()
                and max_concurrent(simultaneous) > LANE.capacity()
                and max_concurrent(sequential) <= LANE.capacity()
                else "FAILED"
            ),
            "note": (
                "Pairwise is wrong in BOTH directions: it accepts the simultaneous triple "
                "that does not fit, and a rule forbidding pairwise overlap would reject the "
                "sequential three that do."
            ),
        }
    )

    # C3 - a verified witness
    spread = solve_mutual_consistency(
        [p("p1", 60.0), p("p2", 80.0), p("p3", 110.0)], LANE, 120.0, 2.0, grid=7
    )
    results.append(
        {
            "check_id": "C3",
            "name": "a_mutually_consistent_witness_is_found_and_verified",
            "verdict": spread.verdict.value,
            "commitments": [
                {
                    "participant": c.participant_id,
                    "arrival_s": c.arrival_s,
                    "occupancy": c.occupancy,
                }
                for c in spread.commitments
            ],
            "max_concurrent": spread.max_concurrent,
            "capacity": spread.capacity,
            "status": "PASSED"
            if spread.verdict is ConsistencyVerdict.WITNESS_VERIFIED
            else "FAILED",
        }
    )

    # C4 - the interaction is NOT vacuous: it produces a nonconvex set
    coupled = solve_mutual_consistency(
        [p("far1", 250.0), p("far2", 250.0), p("near", 30.0)], LANE, 120.0, 6.0, grid=9
    )
    near = next((w for w in coupled.witnesses if w.participant == "near"), None)
    intervals = list(near.arrival_set.intervals) if near else []
    hull_readmits = None
    occupied_then = None
    if len(intervals) == 2:
        (low, gap_start), (gap_end, high) = intervals
        blocked_time = (gap_start + gap_end) / 2.0
        hull_readmits = low <= blocked_time <= high and not _contains(near, blocked_time)
        occupied_then = sum(
            1
            for c in coupled.commitments
            if c.participant_id != "near" and c.occupancy[0] <= blocked_time <= c.occupancy[1]
        )
    results.append(
        {
            "check_id": "C4",
            "name": "the_interaction_produces_a_nonconvex_arrival_set",
            "verdict": coupled.verdict.value,
            "near_intervals": [[round(a, 6), round(b, 6)] for a, b in intervals],
            "near_blocking_windows": [
                [round(a, 6), round(b, 6)] for a, b in (near.blocking_windows if near else ())
            ],
            "hull_would_readmit_a_blocked_time": hull_readmits,
            "occupants_at_that_time": occupied_then,
            "capacity": coupled.capacity,
            "status": "PASSED" if len(intervals) == 2 and hull_readmits else "FAILED",
            "note": (
                "A first witness had blocking windows that lay entirely before the blocked "
                "participant's earliest arrival, so the coupling was present and INERT. "
                "This configuration makes it bite: the blockers' joint occupancy punches a "
                "hole strictly inside the near participant's reachable range."
            ),
        }
    )

    # C5 - provable inconsistency, distinguished from a failed search
    tiny = solve_mutual_consistency([p("p1", 50.0)], Lane("tiny", 3.0, 5.0, 2.5), 100.0, 2.0)
    unreachable = solve_mutual_consistency([p("p1", 100_000.0)], LANE, 10.0, 2.0)
    results.append(
        {
            "check_id": "C5",
            "name": "provable_inconsistency_is_reachable_and_carries_a_proof",
            "lane_too_short": {"verdict": tiny.verdict.value, "proof": tiny.proof},
            "unreachable_participant": {
                "verdict": unreachable.verdict.value,
                "proof": unreachable.proof,
            },
            "status": (
                "PASSED"
                if tiny.verdict is ConsistencyVerdict.PROVABLY_INCONSISTENT
                and unreachable.verdict is ConsistencyVerdict.PROVABLY_INCONSISTENT
                else "FAILED"
            ),
        }
    )

    # C6 - a failed search claims nothing
    tight = solve_mutual_consistency(
        [p(f"p{i}", 60.0 + i) for i in range(1, 5)], LANE, 12.0, 6.0, grid=3
    )
    results.append(
        {
            "check_id": "C6",
            "name": "a_failed_search_reports_only_what_it_checked",
            "verdict": tight.verdict.value,
            "combinations_examined": tight.combinations_examined,
            "grid_size": tight.grid_size,
            "proof": tight.proof,
            "status": (
                "PASSED"
                if tight.verdict is ConsistencyVerdict.NOT_FOUND_ON_THIS_GRID
                and tight.proof is None
                else "FAILED"
            ),
            "note": (
                "NOT_FOUND_ON_THIS_GRID carries no proof and licenses no claim of non-existence."
            ),
        }
    )

    loader = unittest.TestLoader()
    suite = loader.discover(os.path.join(ROOT, "tests"), top_level_dir=os.path.join(ROOT, "tests"))
    with open(os.devnull, "w", encoding="utf-8") as sink:
        outcome = unittest.TextTestRunner(verbosity=0, stream=sink).run(suite)
    results.append(
        {
            "check_id": "C7",
            "name": "full_suite_regression",
            "tests_run": outcome.testsRun,
            "failures": len(outcome.failures),
            "errors": len(outcome.errors),
            "status": "PASSED" if outcome.wasSuccessful() else "FAILED",
        }
    )

    ended_cpu = resource.getrusage(resource.RUSAGE_SELF)
    cpu_s = (ended_cpu.ru_utime - started_cpu.ru_utime) + (
        ended_cpu.ru_stime - started_cpu.ru_stime
    )
    passed = all(r["status"] == "PASSED" for r in results)
    verdict = "INTERACTION_OPERATOR_IMPLEMENTED_AND_CONTROLLED" if passed else "FAILED"

    events.append({"ts": stamp, "event": "run_ended", "verdict": verdict})
    with open(os.path.join(package, "events.jsonl"), "w", encoding="utf-8") as h:
        for e in events:
            h.write(json.dumps(e) + "\n")
    with open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as h:
        for r in results:
            h.write(json.dumps(r) + "\n")

    summary = {
        "package": os.path.basename(package),
        "stage": "W4",
        "claim_class": "analytical_correctness_in_a_finite_abstraction_only",
        "verdict": verdict,
        "outcomes_demonstrated": [
            "WITNESS_VERIFIED",
            "NOT_FOUND_ON_THIS_GRID",
            "PROVABLY_INCONSISTENT",
        ],
        "what_is_established": (
            "The circular dependency between participants' committed plans is stated as an "
            "operator and searched constructively. Where a witness is returned, every "
            "committed time is verified to lie in its own arrival set recomputed against the "
            "others, and joint occupancy is verified against lane capacity by sweep."
        ),
        "what_is_NOT_established": [
            "that a mutually consistent commitment set EXISTS in general",
            (
                "any existence theorem: Kakutani needs CONVEX values and these sets "
                "are deliberately nonconvex"
            ),
            "anything on a real SUMO network; this is the finite abstraction",
            "physical feasibility, assistance, learning, benefit, transfer or novelty",
        ],
        "resources": {
            "cpu_seconds": round(cpu_s, 3),
            "wall_seconds": round(time.time() - started_wall, 3),
            "sumo_process_starts": 0,
            "sumo_episodes": 0,
            "optimizer_updates": 0,
            "checkpoint_loads": 0,
            "test_split_accesses": 0,
        },
    }
    with open(os.path.join(package, "result.json"), "w", encoding="utf-8") as h:
        json.dump(summary, h, indent=2)
    print(json.dumps(summary, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
