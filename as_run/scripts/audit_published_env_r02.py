"""Addendum r02 to the published-environment audit (A-133, R4-B). Versioned replays only.

1. Follow-up completion: the episodes of the sealed audit whose first capture left less than 30 s
   before the horizon are re-run in follow-up mode with the horizon extended to the capture plus
   30 s. Each must reproduce the sealed first event.
2. Stop analogue with a time-based duration: the published-mode episodes are re-run with an
   observer that records, per evader, the longest uninterrupted span (simulation seconds) during
   which it is at most 1 m/s behind the same pursuer, itself at most 1 m/s. Each re-run must
   reproduce the sealed capture events.

The sealed package (r01) is read and never written. The official code is executed unmodified, as
in r01 (`audit_published_env`).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import multiprocessing as mp
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import audit_published_env as r01  # noqa: E402

SEALED = os.path.join(ROOT, "experiments", "20261005_published_env_audit_r01", "results.jsonl")
SLOW_MPS = 1.0
REQUIRED_S = 2.0


def sealed_rows():
    rows = {}
    with open(SEALED, encoding="utf-8") as h:
        for line in h:
            if line.strip():
                r = json.loads(line)
                rows[r["key"]] = r
    return rows


def first_event(row):
    events = [e for e in row.get("events", []) if "error" not in e]
    return min(events, key=lambda e: e["step"]) if events else None


def censored_keys(rows):
    """Follow-up episodes of r01 with a first capture but no observation at +30 s."""
    out = []
    for key, r in sorted(rows.items()):
        if r["mode"] != "followup" or "failed" in r or first_event(r) is None:
            continue
        if r01.FOLLOW_S not in {f["dt"] for f in r["follow"]}:
            out.append(key)
    return out


def longest_span_s(times):
    """Longest uninterrupted span, in seconds, of a sorted list of observation times 1 s apart.

    A single observation spans 0 s; n consecutive observations span n - 1 seconds."""
    best = run_start = prev = None
    for t in times:
        if prev is None or t - prev > 1.0 + 1e-9:
            run_start = t
        span = t - run_start
        best = span if best is None else max(best, span)
        prev = t
    return best


class StopObserver:
    """Per evader: time-stamped observations of 'stopped behind a stopped pursuer', by leader."""

    def __init__(self):
        self.times = {}  # (evader, leader) -> [simulation time]

    def observe(self, traci, evaders):
        now = float(traci.simulation.getTime())
        for eid in evaders:
            try:
                leader = traci.vehicle.getLeader(eid, 10.0)
                slow = traci.vehicle.getSpeed(eid) <= SLOW_MPS
                blocked = bool(
                    slow
                    and leader
                    and leader[0].startswith("p")
                    and traci.vehicle.getSpeed(leader[0]) <= SLOW_MPS
                )
            except traci.TraCIException:
                blocked, leader = False, None
            if blocked:
                self.times.setdefault((eid, leader[0]), []).append(now)

    def spans(self):
        """{evader: longest span in seconds behind one and the same pursuer}."""
        out = {}
        for (eid, _leader), ts in self.times.items():
            out[eid] = max(out.get(eid, 0.0), longest_span_s(sorted(ts)))
        return out


def _actions(arm, env, traci, params, targets):
    if arm == "null":
        return {p: random.randrange(3) for p in params["pursuer_ids"]}
    return r01._greedy(env, traci, targets)


def stop_episode(args):
    """Published mode, unmodified dynamics; same control flow as r01 plus the new observer."""
    key, scenario, arm, index = args
    params = r01._params(scenario)
    random.seed(r01.SEED0 + index)
    import numpy

    numpy.random.seed(r01.SEED0 + index)
    row = {"key": key, "scenario": scenario, "arm": arm, "index": index}
    env = traci = None
    try:
        env, traci = r01._make_env("published", params)
        env.reset()
        obs, legacy_state, legacy, done = StopObserver(), {}, set(), False
        while not done:
            targets = r01._targets(env)
            actions = _actions(arm, env, traci, params, targets)
            evaders = list(env.evader_vehs)
            for eid in evaders:
                # the sealed rule, run by the sealed function, to check identity with r01
                if r01._stop_analogue(traci, eid, legacy_state):
                    legacy.add(eid)
            obs.observe(traci, evaders)
            _, done, _ = env.step(actions, targets)
        spans = obs.spans()
        row.update(
            steps=env.steps,
            n_evaders=params["num_evader"],
            events=env.capture_log,
            legacy_two_observations=sorted(legacy),
            longest_span_s={k: round(v, 3) for k, v in sorted(spans.items())},
            stopped_2s=sorted(k for k, v in spans.items() if v >= REQUIRED_S - 1e-9),
        )
    except Exception as error:  # noqa: BLE001
        row["failed"] = f"{type(error).__name__}: {str(error)[:160]}"
        for closer in (lambda: traci.close(), lambda: env.sumoProcess.kill()):
            with contextlib.suppress(Exception):
                closer()
    return row


def follow_episode(args):
    """Follow-up mode with the horizon extended so that the first capture has 30 s of follow-up."""
    key, scenario, arm, index, sealed_step = args
    params = r01._params(scenario)
    params["max_steps"] = sealed_step + r01.FOLLOW_S + 5  # only the horizon is extended
    random.seed(r01.SEED0 + index)
    import numpy

    numpy.random.seed(r01.SEED0 + index)
    row = {"key": key, "scenario": scenario, "arm": arm, "index": index}
    env = traci = None
    try:
        env, traci = r01._make_env("followup", params)
        env.reset()
        legacy_state, follow, first, done = {}, [], None, False
        while not done:
            targets = r01._targets(env)
            actions = _actions(arm, env, traci, params, targets)
            for eid in list(env.evader_vehs):
                r01._stop_analogue(traci, eid, legacy_state)
            _, done, _ = env.step(actions, targets)
            if done:
                break
            if env.flagged and first is None:
                first = min(env.flagged.values(), key=lambda r: r["step"])
            if first is not None:
                dt = env.steps - first["step"]
                if dt in r01.MARKS:
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
                if dt >= r01.FOLLOW_S:
                    break
        if not done:
            traci.close()
            env.sumoProcess.kill()
        row.update(steps=env.steps, first_event=first, follow=follow)
    except Exception as error:  # noqa: BLE001
        row["failed"] = f"{type(error).__name__}: {str(error)[:160]}"
        for closer in (lambda: traci.close(), lambda: env.sumoProcess.kill()):
            with contextlib.suppress(Exception):
                closer()
    return row


def episode(args):
    return follow_episode(args[1:]) if args[0] == "F" else stop_episode(args[1:])


def tasks(rows):
    out = []
    for key in censored_keys(rows):
        r = rows[key]
        step = first_event(r)["step"]
        out.append(("F", "F|" + key, r["scenario"], r["arm"], r["index"], step))
    for key, r in sorted(rows.items()):
        if r["mode"] == "published":
            out.append(("S", "S|" + key, r["scenario"], r["arm"], r["index"]))
    return out


def _same_events(a, b):
    def sig(events):
        return [(e["step"], e["evader"], e["pursuer"], e.get("relation")) for e in events]

    return sig(a) == sig(b)


def summarise(package, sealed):
    with open(os.path.join(package, "results.jsonl"), encoding="utf-8") as h:
        new = {}
        for line in h:
            if line.strip():
                r = json.loads(line)
                new[r["key"]] = r
    out = {"rows": len(new), "failed": sum("failed" in r for r in new.values())}
    # 1. follow-up completion
    fol = {k[2:]: r for k, r in new.items() if k.startswith("F|") and "failed" not in r}
    identical, completed = 0, {}
    for key, r in fol.items():
        a, b = first_event(sealed[key]), r["first_event"]
        same = b is not None and (a["step"], a["evader"], a["pursuer"]) == (
            b["step"],
            b["evader"],
            b["pursuer"],
        )
        identical += same
        completed[key] = {"same_first_event": same, "marks": sorted(f["dt"] for f in r["follow"])}
    out["followup_completion"] = {
        "censored_in_r01": len(censored_keys(sealed)),
        "rerun": len(fol),
        "same_first_event": identical,
        "episodes": completed,
    }
    marks = {}
    for cell in sorted({(r["scenario"], r["arm"]) for r in sealed.values()}):
        rows = [
            r
            for r in sealed.values()
            if (r["scenario"], r["arm"]) == cell
            and r["mode"] == "followup"
            and "failed" not in r
            and first_event(r) is not None
        ]
        block = {}
        for dt in r01.MARKS:
            fs, sealed_n = [], 0
            for r in rows:
                f = next((x for x in r["follow"] if x["dt"] == dt), None)
                sealed_n += f is not None
                if f is None and r["key"] in fol:
                    f = next((x for x in fol[r["key"]]["follow"] if x["dt"] == dt), None)
                if f is not None:
                    fs.append(f)
            block[f"+{dt}s"] = {
                "first_captures": len(rows),
                "observed_in_r01": sealed_n,
                "observed_after_completion": len(fs),
                "within_5m_of_capturer": sum(f["dist_capturer_m"] < 5.0 for f in fs),
                "over_50m_from_every_pursuer": sum(f["dist_nearest_m"] > 50.0 for f in fs),
                "evader_faster_than_1mps": sum(f["evader_speed"] > 1.0 for f in fs),
                "median_dist_capturer_m": round(
                    sorted(f["dist_capturer_m"] for f in fs)[len(fs) // 2], 1
                )
                if fs
                else None,
            }
        marks["|".join(cell)] = block
    out["marks_with_denominators"] = marks
    # 2. stop analogue
    stop = {k[2:]: r for k, r in new.items() if k.startswith("S|") and "failed" not in r}
    cells = {}
    for key, r in stop.items():
        s = sealed[key]
        c = cells.setdefault(
            f"{r['scenario']}|{r['arm']}",
            {
                "episodes": 0,
                "events_identical": 0,
                "legacy_identical": 0,
                "evaders": 0,
                "two_observations": 0,
                "stopped_2s": 0,
            },
        )
        c["episodes"] += 1
        c["events_identical"] += _same_events(s["events"], r["events"])
        c["legacy_identical"] += sorted(s["stop_analogue"]) == r["legacy_two_observations"]
        c["evaders"] += r["n_evaders"]
        c["two_observations"] += len(r["legacy_two_observations"])
        c["stopped_2s"] += len(r["stopped_2s"])
    for c in cells.values():
        c["two_observations_share"] = round(c["two_observations"] / c["evaders"], 4)
        c["stopped_2s_share"] = round(c["stopped_2s"] / c["evaders"], 4)
    out["stop_analogue"] = cells
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=2)
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
    sealed = sealed_rows()
    results = os.path.join(package, "results.jsonl")
    seen = set()
    if os.path.exists(results):
        with open(results, encoding="utf-8") as h:
            seen = {json.loads(x)["key"] for x in h if x.strip()}
    todo = [t for t in tasks(sealed) if t[1] not in seen]
    if args.limit is not None:
        todo = todo[: args.limit]
    deadline = time.time() + 60 * args.budget_min
    counter = mp.get_context("spawn").Value("i", 0)
    done = 0
    with mp.get_context("spawn").Pool(
        args.workers, initializer=r01._init, initargs=(counter,)
    ) as pool:
        it = pool.imap_unordered(episode, todo)
        with open(results, "a", encoding="utf-8") as h:
            for _ in todo:
                if time.time() > deadline:
                    break
                try:
                    row = it.next(timeout=600)
                except mp.TimeoutError:
                    break
                h.write(json.dumps(row) + "\n")
                h.flush()
                done += 1
        pool.terminate()
    remaining = len(todo) - done
    if remaining == 0 and args.limit is None:
        summarise(package, sealed)
    print(json.dumps({"done": done, "remaining": remaining}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
