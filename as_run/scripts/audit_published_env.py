"""Capture-event audit of a published multi-vehicle pursuit environment (A-126, stage A).

The official DGMARL-MVP environment (third_party/DGMARL-MVP, commit 62bd72e2) runs unmodified.
An observer subclass reads the kinematic state of every pursuer-evader pair that satisfies the
published capture rule (front-bumper distance < 5 m) before the environment removes the evader.

Arms: ``null`` (uniformly random turns) and ``greedy`` (shortest-path chaser in the published action
space). Modes: ``published`` (unmodified dynamics) and ``followup`` (the evader of the first capture
event is not removed and is followed for 30 s).

No file of the third-party repository is edited or imported from this project's sources: a
byte-identical copy is placed in a temporary directory per worker and its hashes are recorded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
import random
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THIRD = os.path.join(ROOT, "third_party", "DGMARL-MVP")
COMMIT = "62bd72e2a6ae94c1b5afba0ddee89aeee5ea9257"
SUMO = os.environ.get(
    "SUMO_BINARY",
    "/Library/Frameworks/Python.framework/Versions/3.10/lib/python3.10/site-packages/sumo/bin/sumo",
)
SCENARIOS = {
    "3x3Traffic_4_2": ("3x3Grid42", 4, 2),
    "3x3Traffic_7_4": ("3x3Grid74", 7, 4),
}
EPISODES = {"3x3Traffic_4_2": 300, "3x3Traffic_7_4": 100}
SEED0 = 126000
FOLLOW_S = 30
MARKS = (1, 2, 5, 10, 30)
CAPTURE_M = 5.0  # the published threshold; used only to read which pairs satisfy the published rule

_W = {}


def source_hashes(base):
    out = {}
    for folder, _, files in os.walk(base):
        if ".git" in folder.split(os.sep):
            continue
        for name in sorted(files):
            path = os.path.join(folder, name)
            with open(path, "rb") as h:
                out[os.path.relpath(path, base)] = hashlib.sha256(h.read()).hexdigest()
    return out


def _init(counter):
    """Per-worker: private byte-identical copy of the official code, imported from there."""
    with counter.get_lock():
        index = counter.value
        counter.value += 1
    work = tempfile.mkdtemp(prefix="dgmarl_audit_")
    shutil.copytree(THIRD, work, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git"))
    assert source_hashes(work) == source_hashes(THIRD)
    os.chdir(work)
    sys.path.insert(0, work)
    os.environ.setdefault("MPLBACKEND", "Agg")
    sys.stdout = open(os.devnull, "w")  # noqa: SIM115 - the official code prints every step
    sys.stderr = open(os.path.join(work, "stderr.log"), "w")  # noqa: SIM115
    import env.environment as official
    import settings

    official.sumoBinary_nogui = SUMO  # undefined on macOS in the release
    official.sumoBinary = SUMO
    _W.update(work=work, index=index, official=official, base=dict(settings.params))


def _params(scenario):
    stem, n_p, n_e = SCENARIOS[scenario]
    p = dict(_W["base"])
    p.update(
        env_name=scenario,
        rou_path=f"./env/3x3Traffic/{stem}.rou.xml",
        cfg_path=f"./env/3x3Traffic/{stem}.sumocfg",
        net_path="./env/3x3Traffic/3x3Grid.net.xml",
        num_pursuit=n_p,
        pursuer_ids=[f"p{i}" for i in range(n_p)],
        num_evader=n_e,
        evader_ids=[f"e{i}" for i in range(n_e)],
        gui=False,
        port=43000 + 10 * _W["index"],
    )
    return p


def _wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def _vehicle(traci, vid):
    x, y = traci.vehicle.getPosition(vid)
    return {
        "x": x,
        "y": y,
        "speed": traci.vehicle.getSpeed(vid),
        "angle": traci.vehicle.getAngle(vid),
        "road": traci.vehicle.getRoadID(vid),
        "lane": traci.vehicle.getLaneID(vid),
        "lane_pos": traci.vehicle.getLanePosition(vid),
    }


def classify(e, p):
    """Geometry of one pair at the published capture instant (pure; unit-tested)."""
    dx, dy = p["x"] - e["x"], p["y"] - e["y"]
    heading = math.radians(e["angle"])  # SUMO: 0 = north, clockwise
    ux, uy = math.sin(heading), math.cos(heading)
    longitudinal = dx * ux + dy * uy
    lateral = abs(-dx * uy + dy * ux)
    dheading = abs(_wrap(p["angle"] - e["angle"]))
    internal = e["road"].startswith(":") or p["road"].startswith(":")
    if internal:
        relation = "junction"
    elif e["lane"] == p["lane"]:
        relation = "same_lane"
    elif e["road"].lstrip("-") == p["road"].lstrip("-"):
        relation = "opposite_direction"
    else:
        relation = "different_road"
    return {
        "relation": relation,
        "distance_m": math.hypot(dx, dy),
        "longitudinal_m": longitudinal,
        "lateral_m": lateral,
        "heading_diff_deg": dheading,
        "evader_speed": e["speed"],
        "pursuer_speed": p["speed"],
        "pursuer_ahead": longitudinal > 0.0,
        "stop_compatible": bool(
            relation == "same_lane"
            and longitudinal > 0.0
            and e["speed"] <= 1.0
            and p["speed"] <= 1.0
        ),
    }


def _hits(env, skip=()):
    out = []
    for eid, ev in env.evader_vehs.items():
        if eid in skip:
            continue
        near = []
        for pid, pv in env.pursuit_vehs.items():
            d = math.hypot(ev["x"] - pv["x"], ev["y"] - pv["y"])
            if d < CAPTURE_M:
                near.append((d, pid))
        if near:
            out.append((eid, sorted(near)))
    return out


def _events(env, traci, skip=()):
    rows = []
    for eid, near in _hits(env, skip):
        try:
            e = _vehicle(traci, eid)
            p = _vehicle(traci, near[0][1])
        except traci.TraCIException as error:
            rows.append(
                {"evader": eid, "pursuer": near[0][1], "step": env.steps, "error": str(error)[:80]}
            )
            continue
        rows.append(
            {
                "evader": eid,
                "pursuer": near[0][1],
                "n_pursuers_within": len(near),
                "step": env.steps,
                **classify(e, p),
            }
        )
    return rows


def _make_env(mode, params):
    official = _W["official"]
    traci = official.traci

    class Observer(official.Environment):
        """Reads the state of capturing pairs before the official rule removes the evader."""

        def __init__(self, p):
            self.capture_log = []
            self.flagged = {}
            super().__init__(p)

        def checkPursuit(self):  # noqa: N802 - official name
            if mode == "published":
                self.capture_log.extend(_events(self, traci))
                return super().checkPursuit()
            # follow-up: same detection, no removal; termination is handled by the runner
            for row in _events(self, traci, skip=self.flagged):
                self.flagged[row["evader"]] = row
                self.capture_log.append(row)
            return False

    return Observer(params), traci


def _targets(env):
    """Nearest evader still present. In follow-up mode the captured evader stays a target, which
    keeps its pursuers on it: the favourable case for the published rule."""
    out = {}
    for pid, pv in env.pursuit_vehs.items():
        out[pid] = min(
            env.evader_vehs,
            key=lambda e: math.hypot(
                pv["x"] - env.evader_vehs[e]["x"], pv["y"] - env.evader_vehs[e]["y"]
            ),
        )
    return out


def _greedy(env, traci, targets):
    import networkx as nx

    official = _W["official"]
    actions = {}
    for pid in env.params["pursuer_ids"]:
        if pid not in env.pursuit_vehs:
            continue
        goal = env.evader_vehs[targets[pid]]["e_edge"]
        lane = env.checkLane(traci.vehicle.getLaneID(pid))
        best, best_cost = 1, float("inf")
        for action in (1, 0, 2):
            nxt, ok = official.get_action(lane, action)
            if not ok or nxt is None:
                continue
            try:
                cost = (
                    0.0
                    if nxt == goal
                    else nx.shortest_path_length(env.topology, nxt, goal, weight="weight")
                )
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
            if cost < best_cost:
                best, best_cost = action, cost
        actions[pid] = best
    return actions


def _stop_analogue(traci, eid, state):
    """Evader at most 1 m/s for 2 s with a pursuer as its immediate leader (reference only)."""
    try:
        leader = traci.vehicle.getLeader(eid, 10.0)
        slow = traci.vehicle.getSpeed(eid) <= 1.0
    except traci.TraCIException:
        return False
    blocked = bool(
        slow and leader and leader[0].startswith("p") and traci.vehicle.getSpeed(leader[0]) <= 1.0
    )
    state[eid] = state.get(eid, 0) + 1 if blocked else 0
    return state[eid] >= 2


def episode(args):
    key, scenario, arm, mode, index = args
    params = _params(scenario)
    random.seed(SEED0 + index)
    import numpy

    numpy.random.seed(SEED0 + index)
    row = {"key": key, "scenario": scenario, "arm": arm, "mode": mode, "index": index}
    env = traci = None
    try:
        env, traci = _make_env(mode, params)
        env.reset()
        stop_state, stops, follow, done, end_at = {}, set(), [], False, None
        horizon = params["max_steps"]
        while not done:
            targets = _targets(env)  # nearest evader still present, as in the official wrapper
            if arm == "null":
                actions = {p: random.randrange(3) for p in params["pursuer_ids"]}
            else:
                actions = _greedy(env, traci, targets)
            for eid in list(env.evader_vehs):
                if _stop_analogue(traci, eid, stop_state):
                    stops.add(eid)
            _, done, _ = env.step(actions, targets)
            if mode == "followup" and not done:
                if env.flagged and end_at is None:
                    end_at = min(env.steps + FOLLOW_S, horizon)
                    first = min(env.flagged.values(), key=lambda r: r["step"])
                if end_at is not None:
                    dt = env.steps - first["step"]
                    if dt in MARKS:
                        ev = env.evader_vehs[first["evader"]]
                        pv = env.pursuit_vehs[first["pursuer"]]
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
                    if env.steps >= end_at:
                        break
                if env.steps >= horizon:
                    break
        if mode == "followup" and not done:
            traci.close()
            env.sumoProcess.kill()
        row.update(
            steps=env.steps,
            n_evaders=params["num_evader"],
            captured=len(env.success_evader) if mode == "published" else len(env.flagged),
            success=bool(mode == "published" and len(env.evader_vehs) == 0),
            events=env.capture_log,
            follow=follow,
            stop_analogue=sorted(stops),
        )
    except Exception as error:  # noqa: BLE001
        row["failed"] = f"{type(error).__name__}: {str(error)[:160]}"
        try:
            if traci is not None:
                traci.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            if env is not None:
                env.sumoProcess.kill()
        except Exception:  # noqa: BLE001
            pass
    return row


def tasks(limit=None):
    out = []
    for scenario, n in EPISODES.items():
        for index in range(n if limit is None else min(n, limit)):
            for arm in ("null", "greedy"):
                for mode in ("published", "followup"):
                    out.append((f"{scenario}|{arm}|{mode}|{index}", scenario, arm, mode, index))
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
    seen = set()
    if os.path.exists(results):
        with open(results, encoding="utf-8") as h:
            seen = {json.loads(x)["key"] for x in h if x.strip()}
    with open(os.path.join(package, "third_party_hashes.json"), "w", encoding="utf-8") as h:
        json.dump({"commit": COMMIT, "sha256": source_hashes(THIRD)}, h, indent=1, sort_keys=True)
    todo = [t for t in tasks(args.limit) if t[0] not in seen]
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
                    row = it.next(timeout=600)
                except mp.TimeoutError:
                    break
                h.write(json.dumps(row) + "\n")
                h.flush()
                done += 1
        pool.terminate()
    print(json.dumps({"done": done, "remaining": len(todo) - done}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
