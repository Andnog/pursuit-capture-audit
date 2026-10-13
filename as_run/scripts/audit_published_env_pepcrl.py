"""Capture-event audit of the official PEPCRL-MVP real-map environment (A-137, pre-registered).

Same audit as `audit_published_env.py` (A-126), on the released real map of a second published
method, with the two corrections of A-133 built in: every first capture within the published
horizon has a complete 30 s follow-up, and the stop analogue is measured in simulation time behind
one and the same pursuer. The official code runs unmodified from a byte-identical temporary copy.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import multiprocessing as mp
import os
import random
import shutil
import statistics
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import audit_published_env as r01  # noqa: E402
from analyse_published_env import RELATIONS, boot, events_ok  # noqa: E402
from audit_published_env_r02 import REQUIRED_S, StopObserver  # noqa: E402

THIRD = os.path.join(ROOT, "third_party", "PEPCRL-MVP")
COMMIT = "ac8ca695ed9defc8728ede131a4840f7949b4c31"
SCENARIOS = {"RealMap_6_3": ("63", 6, 3), "RealMap_7_4": ("74", 7, 4), "RealMap_8_5": ("85", 8, 5)}
SEEDS_PER_SCENARIO = 150
SEED0 = 137000
FOLLOW_S, MARKS = 30, (1, 2, 5, 10, 30)


def _init(counter):
    """Per worker: a private byte-identical copy of the official code, imported from there."""
    with counter.get_lock():
        index = counter.value
        counter.value += 1
    work = tempfile.mkdtemp(prefix="pepcrl_audit_")
    shutil.copytree(THIRD, work, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    assert r01.source_hashes(work) == r01.source_hashes(THIRD)
    os.chdir(work)
    sys.path.insert(0, work)
    os.environ.setdefault("MPLBACKEND", "Agg")
    sys.stdout = open(os.devnull, "w")  # noqa: SIM115 - the official code prints every step
    sys.stderr = open(os.path.join(work, "stderr.log"), "w")  # noqa: SIM115
    import env.environment as official
    import settings

    official.sumoBinary_nogui = r01.SUMO  # undefined on macOS in the release
    official.sumoBinary = r01.SUMO
    r01._W.clear()
    r01._W.update(work=work, index=index, official=official, base=dict(settings.params))


def _params(scenario):
    """The released parameters of one scenario (values of the release's settings.py)."""
    stem, n_p, n_e = SCENARIOS[scenario]
    p = dict(r01._W["base"])
    p.update(
        env_name=scenario,
        rou_path=f"./env/RealMap/RealMap{stem}.rou.xml",
        cfg_path=f"./env/RealMap/RealMap{stem}.sumocfg",
        net_path="./env/RealMap/RealMap.net.xml",
        num_pursuit=n_p,
        pursuer_ids=[f"p{i}" for i in range(n_p)],
        num_evader=n_e,
        evader_ids=[f"e{i}" for i in range(n_e)],
        num_action=3,
        lane_code_length=7,
        num_background_veh=300,
        congested_lane=["-E14"],
        congested_prob=0.2,
        strat_warm_step=50,
        num_edge=106,
        max_steps=800,
        gui=False,
        port=44000 + 10 * r01._W["index"],
    )
    return p


def episode(args):
    key, scenario, arm, mode, index = args
    params = _params(scenario)
    horizon = params["max_steps"]
    if mode == "followup":
        params["max_steps"] = horizon + FOLLOW_S + 5  # only the horizon parameter is raised
    random.seed(SEED0 + index)
    import numpy

    numpy.random.seed(SEED0 + index)
    row = {"key": key, "scenario": scenario, "arm": arm, "mode": mode, "index": index}
    env = traci = None
    try:
        env, traci = r01._make_env(mode, params)
        env.reset()
        obs, follow, first, done = StopObserver(), [], None, False
        while not done:
            targets = r01._targets(env)
            if arm == "null":
                actions = {p: random.randrange(3) for p in params["pursuer_ids"]}
            else:
                actions = r01._greedy(env, traci, targets)
            if mode == "published":
                obs.observe(traci, list(env.evader_vehs))
            _, done, _ = env.step(actions, targets)
            if done or mode == "published":
                continue
            if first is None and env.flagged:
                first = min(env.flagged.values(), key=lambda r: r["step"])
            if first is None:
                if env.steps >= horizon:
                    break  # no capture within the published horizon
                continue
            dt = env.steps - first["step"]
            if dt in MARKS:
                ev, pv = env.evader_vehs[first["evader"]], env.pursuit_vehs[first["pursuer"]]
                follow.append(
                    {
                        "dt": dt,
                        "evader_speed": traci.vehicle.getSpeed(first["evader"]),
                        "dist_capturer_m": math.hypot(ev["x"] - pv["x"], ev["y"] - pv["y"]),
                        "dist_nearest_m": min(
                            math.hypot(ev["x"] - q["x"], ev["y"] - q["y"])
                            for q in env.pursuit_vehs.values()
                        ),
                    }
                )
            if dt >= FOLLOW_S:
                break
        if not done:
            traci.close()
            env.sumoProcess.kill()
        row.update(steps=env.steps, n_evaders=params["num_evader"], events=env.capture_log)
        if mode == "published":
            spans = obs.spans()
            row.update(
                captured=len(env.success_evader),
                success=len(env.evader_vehs) == 0,
                longest_span_s={k: round(v, 3) for k, v in sorted(spans.items())},
                stopped_2s=sorted(k for k, v in spans.items() if v >= REQUIRED_S - 1e-9),
            )
        else:
            row.update(first_event=first, follow=follow)
    except Exception as error:  # noqa: BLE001
        row["failed"] = f"{type(error).__name__}: {str(error)[:160]}"
        # What the unmodified environment had produced before it aborted is kept (A-137 note).
        row.update(
            steps=getattr(env, "steps", None),
            n_evaders=params["num_evader"],
            events=list(getattr(env, "capture_log", [])),
            captured=len(getattr(env, "success_evader", [])),
        )
        for closer in (lambda: traci.close(), lambda: env.sumoProcess.kill()):
            with contextlib.suppress(Exception):
                closer()
    return row


def tasks(limit=None):
    out = []
    n = SEEDS_PER_SCENARIO if limit is None else min(SEEDS_PER_SCENARIO, limit)
    for index in range(n):
        for scenario in SCENARIOS:
            for arm in ("null", "greedy"):
                for mode in ("published", "followup"):
                    out.append((f"{scenario}|{arm}|{mode}|{index}", scenario, arm, mode, index))
    return out


def _reasons(rows):
    out = {}
    for r in rows:
        if "failed" in r:
            reason = r["failed"][:60]
            out[reason] = out.get(reason, 0) + 1
    return out


def summarise(rows):
    out = {"rows": len(rows), "failed": sum("failed" in r for r in rows.values()), "cells": {}}
    for scenario in SCENARIOS:
        for arm in ("null", "greedy"):
            sel = [r for r in rows.values() if (r["scenario"], r["arm"]) == (scenario, arm)]
            pub_all = [r for r in sel if r["mode"] == "published"]
            fol_all = [r for r in sel if r["mode"] == "followup"]
            pub = [r for r in pub_all if "failed" not in r]
            fol = [r for r in fol_all if "failed" not in r]
            # Geometry uses every capture event of the unmodified dynamics, including those
            # recorded before an episode aborted; rates use completed episodes, with bounds.
            per = [events_ok(r) for r in pub_all]
            flat = [e for ev in per for e in ev]
            aborted_events = sum(len(events_ok(r)) for r in pub_all if "failed" in r)
            wins = sum(bool(r["success"]) for r in pub)

            def share(pred, per=per):
                return boot([(float(sum(pred(e) for e in ev)), float(len(ev))) for ev in per if ev])

            block = {
                "published": {
                    "scheduled": len(pub_all),
                    "episodes": len(pub),
                    "failed": len(pub_all) - len(pub),
                    "success": boot([(float(r["success"]), 1.0) for r in pub]),
                    "success_bounds_over_scheduled": [
                        round(wins / max(1, len(pub_all)), 4),
                        round((wins + len(pub_all) - len(pub)) / max(1, len(pub_all)), 4),
                    ],
                    "failure_reasons": _reasons(pub_all),
                    "capture_events_from_aborted_episodes": aborted_events,
                    "any_capture": boot([(float(r["captured"] > 0), 1.0) for r in pub]),
                    "captured_share_of_evaders": boot(
                        [(float(r["captured"]), float(r["n_evaders"])) for r in pub]
                    ),
                    "mean_steps": round(statistics.mean(r["steps"] for r in pub), 1)
                    if pub
                    else None,
                    "capture_events": len(flat),
                    "relation_counts": {
                        x: sum(e["relation"] == x for e in flat) for x in RELATIONS
                    },
                    "relation": {x: share(lambda e, x=x: e["relation"] == x) for x in RELATIONS},
                    "evader_faster_than_1mps": share(lambda e: e["evader_speed"] > 1.0),
                    "heading_diff_at_least_150deg": share(lambda e: e["heading_diff_deg"] >= 150.0),
                    "median_distance_m": round(statistics.median(e["distance_m"] for e in flat), 2)
                    if flat
                    else None,
                    "stopped_2s_share_of_evaders": boot(
                        [(float(len(r["stopped_2s"])), float(r["n_evaders"])) for r in pub]
                    ),
                }
            }
            first = [r for r in fol if r.get("first_event")]
            same = checked = 0
            for r in first:
                twin = rows.get(r["key"].replace("|followup|", "|published|"))
                if twin is None or "failed" in twin or not events_ok(twin):
                    continue
                a, b = r["first_event"], min(events_ok(twin), key=lambda e: e["step"])
                checked += 1
                same += (a["step"], a["evader"], a["pursuer"]) == (
                    b["step"],
                    b["evader"],
                    b["pursuer"],
                )
            marks = {}
            for dt in MARKS:
                fs = [next((f for f in r["follow"] if f["dt"] == dt), None) for r in first]
                fs = [f for f in fs if f is not None]
                marks[f"+{dt}s"] = {
                    "observed": len(fs),
                    "within_5m_of_capturer": boot(
                        [(float(f["dist_capturer_m"] < 5.0), 1.0) for f in fs]
                    ),
                    "over_50m_from_every_pursuer": boot(
                        [(float(f["dist_nearest_m"] > 50.0), 1.0) for f in fs]
                    ),
                    "evader_faster_than_1mps": boot(
                        [(float(f["evader_speed"] > 1.0), 1.0) for f in fs]
                    ),
                    "median_dist_capturer_m": round(
                        statistics.median(f["dist_capturer_m"] for f in fs), 1
                    )
                    if fs
                    else None,
                }
            block["followup"] = {
                "scheduled": len(fol_all),
                "failed": len(fol_all) - len(fol),
                "failure_reasons": _reasons(fol_all),
                "first_captures": len(first),
                "first_event_identical_to_published": [same, checked],
                "marks": marks,
            }
            out["cells"][f"{scenario}|{arm}"] = block
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--budget-min", type=float, default=25.0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    os.makedirs(package, exist_ok=True)
    results = os.path.join(package, "results.jsonl")
    rows = {}
    if os.path.exists(results):
        with open(results, encoding="utf-8") as h:
            for line in h:
                if line.strip():
                    r = json.loads(line)
                    rows[r["key"]] = r
    with open(os.path.join(package, "third_party_hashes.json"), "w", encoding="utf-8") as h:
        json.dump(
            {"commit": COMMIT, "sha256": r01.source_hashes(THIRD)}, h, indent=1, sort_keys=True
        )
    todo = [t for t in tasks(args.limit) if t[0] not in rows]
    deadline = time.time() + 60 * args.budget_min
    counter = mp.get_context("spawn").Value("i", 0)
    done = 0
    with mp.get_context("spawn").Pool(args.workers, initializer=_init, initargs=(counter,)) as pool:
        it = pool.imap_unordered(episode, todo)
        with open(results, "a", encoding="utf-8") as h:
            for _ in todo:
                if time.time() > deadline:
                    break
                try:
                    row = it.next(timeout=900)
                except mp.TimeoutError:
                    break
                rows[row["key"]] = row
                h.write(json.dumps(row) + "\n")
                h.flush()
                done += 1
        pool.terminate()
    remaining = len(todo) - done
    if remaining == 0 and args.limit is None:
        with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
            json.dump(summarise(rows), h, indent=2)
    print(json.dumps({"done": done, "remaining": remaining}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
