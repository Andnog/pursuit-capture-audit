"""Scan of the capture instants used by the hold audit (A-137, fifth review, F5-2 and F5-5).

The hold audit (A-108) froze the pursuers at the instant returned by `_witness`, a helper that did
not reset a pursuer's run when the pursuer was absent from a frame. Traces were not stored, so the
1,433 audited captures are replayed here once (natural run, historical dispatch bookkeeping), and
for each one this script compares:

- the sealed instant and finisher of the audit row;
- the earlier helper, recomputed (`audit_d06_persistence._witness`);
- the corrected extractor (`evaluation.capture_time.earliest_capture`);
- the independent judge, one pursuer at a time (`judge_earliest_capture`).

It also records, for every trace, the frames in which a vehicle is absent (separating gaps inside
a vehicle's record from a final disappearance), any invalid value (non-finite, negative speed,
non-positive dimension) and the collisions with their times. No episode is new: every task is a
deterministic replay of a sealed development-phase episode (salt PE11, seven non-TEST cities).
Resumable chunks (--budget-min).
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from run_ambush_optimization import Store  # noqa: E402

EXP = os.path.join(ROOT, "experiments")
AUDIT = os.path.join(EXP, "20261003_d06_persistence_audit_r01")
A99 = os.path.join(EXP, "20261002_ambush_optimization_r01")
METHODS = {"plus_opt": "ambush_plus", "ambush_a95": "ambush", "pursuit": "pursuit"}
STEP_S = 0.1


def _init():
    import torch

    import joint_interception.native.engine as engine

    torch.set_num_threads(1)
    engine.DISPATCH_MODE = "legacy"  # the bookkeeping in force when the audit ran (A-119)


def compare(trace, sealed_t, sealed_finisher, team_ids):
    """Pure comparison of the four instants on one trace; unit tested."""
    from types import SimpleNamespace

    from audit_d06_persistence import _witness
    from joint_interception.domain.contracts import CaptureParameters
    from joint_interception.evaluation.capture_judge import trace_defect
    from joint_interception.evaluation.capture_time import (
        TraceIntegrityError,
        absent_frames,
        earliest_capture,
        judge_earliest_capture,
    )

    params = CaptureParameters.from_domain()
    row = {"sealed": [sealed_t, sealed_finisher], "frames": len(trace)}
    legacy = _witness(SimpleNamespace(trace=trace))
    row["legacy"] = None if legacy is None else [round(legacy[0], 1), legacy[1]]
    row["invalid"] = trace_defect(trace)
    try:
        c = earliest_capture(trace, "e1", params, STEP_S)
        j = judge_earliest_capture(trace, "e1", params, STEP_S)
        row["corrected"] = None if c is None else [round(c.time_s, 1), c.pursuer_id]
        row["judge"] = None if j is None else [round(j.time_s, 1), j.pursuer_id]
    except TraceIntegrityError as error:
        row["integrity_error"] = str(error)[:160]
        row["corrected"] = row["judge"] = None
    absent = absent_frames(trace, team_ids)
    row["absent"] = {v: a for v, a in absent.items() if a["absent"]}
    row["inner_gap_frames"] = sum(a["inner_gap_frames"] for a in absent.values())
    row["reproduced"] = row["legacy"] == row["sealed"]
    row["same_instant"] = (
        row["corrected"] is not None
        and row["legacy"] is not None
        and row["corrected"][0] == row["legacy"][0] == sealed_t
        and row["judge"] is not None
        and row["judge"][0] == sealed_t
    )
    return row


def task(args):
    from audit_cage_certificate import replay

    key, m, i, seed, level, team, method, params, sealed_t, sealed_finisher = args
    row = {"key": key}
    try:
        ep, _ = replay(
            m, i, seed, "PE11", "T", None, "policy", 300.0, kind=METHODS[method], speed=1.0,
            level=level, team=team, learner={"params": params} if params is not None else None,
            reward_mode="certificate",
        )  # fmt: skip
        ids = ["e1", *[f"p{k}" for k in range(1, team + 1)]]
        row.update(compare(ep.trace, sealed_t, sealed_finisher, ids))
        row["captured"] = bool(ep.contact_capture)
        row["end_s"] = ep.end_s
        row["collision_times"] = sorted({c["t"] for c in ep.collision_events})[:20]
        row["collisions"] = len(ep.collision_events)
    except Exception as error:  # noqa: BLE001
        row["failed"] = f"{type(error).__name__}: {str(error)[:120]}"
    return row


def tasks():
    with open(os.path.join(A99, "summary.json"), encoding="utf-8") as h:
        c215 = json.load(h)["final_params"]
    out = []
    with open(os.path.join(AUDIT, "results.jsonl"), encoding="utf-8") as h:
        for x in h:
            r = json.loads(x)
            if "t_c" not in r:
                continue
            _, method, m, i, seed, level, team = r["key"].split("|")
            params = c215 if method == "plus_opt" else None
            out.append(
                (r["key"], m, int(i), int(seed), level, int(team), method, params)
                + (r["t_c"], r["finisher"])
            )
    return sorted(out)


def summarise(rows):
    done = [r for r in rows if "failed" not in r]
    differ = [r for r in done if not r["same_instant"]]
    with_gap = [r for r in done if r["inner_gap_frames"]]
    with_absence = [r for r in done if r["absent"]]
    collided = [r for r in done if r["collisions"]]
    before = [r for r in collided if min(r["collision_times"]) <= r["sealed"][0] + 1e-9]
    return {
        "replays": len(rows),
        "failed": len(rows) - len(done),
        "reproduced_sealed_instant_and_finisher": sum(r["reproduced"] for r in done),
        "captured_by_engine_judge": sum(r["captured"] for r in done),
        "same_instant_all_four": len(done) - len(differ),
        "instants_that_differ": [
            {k: r.get(k) for k in ("key", "sealed", "legacy", "corrected", "judge")} for r in differ
        ],
        "corrected_equals_judge_instant_and_pursuer": sum(
            r["corrected"] == r["judge"] and r["corrected"] is not None for r in done
        ),
        "traces_with_an_inner_gap": len(with_gap),
        "inner_gap_keys": [r["key"] for r in with_gap][:50],
        "traces_with_any_absent_frame": len(with_absence),
        "absent_vehicle_counts": {
            v: sum(v in r["absent"] for r in done)
            for v in sorted({v for r in done for v in r["absent"]})
        },
        "traces_with_invalid_values": sum(r["invalid"] is not None for r in done),
        "integrity_errors": sum("integrity_error" in r for r in done),
        "frames_scanned": sum(r["frames"] for r in done),
        "episodes_with_a_collision": len(collided),
        "episodes_with_a_collision_at_or_before_capture": len(before),
        "episodes_with_collisions_only_after_capture": len(collided) - len(before),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=0, help="development check: first N tasks")
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    deadline = time.time() + 60 * args.budget_min
    todo = tasks()
    if args.limit:
        todo = todo[: args.limit]
    store = Store(package)
    with mp.get_context("spawn").Pool(args.workers, initializer=_init) as pool:
        complete = store.run(pool, todo, deadline, task)
    print(json.dumps({"done": len(store.rows), "of": len(todo), "complete": complete}), flush=True)
    if complete:
        out = summarise([store.rows[t[0]] for t in todo])
        with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
            json.dump(out, h, indent=2)
        print(json.dumps({k: v for k, v in out.items() if not isinstance(v, list)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
