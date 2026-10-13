"""F3: confirmatory caging test on real maps (A-73). SUMO only, parallel.

As F2 (run_caging_sweep.py) but with gate HYSTERESIS (a pursuer keeps its gate while it is still
a gate it can take first) and a pooled real-map primary analysis.

Cell = (map, team size, evader speed factor). Per run, every decision:
- TIME cage: the evader's safe region (connected, A-71) has <= K junctions;
- PHYSICAL cage: time cage AND every gate is held by a pursuer physically there (front within
  HOLD_RADIUS_M of the gate junction, speed <= HOLD_SPEED_MPS);
each counted once it has held PERSIST_S. Strategies cut / individual / pursuit as in F1.
Summary per cell: P(caged) per strategy for both certificates, and the paired difference
cut - individual bootstrapped over scenarios.
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
SUMO = "/Library/Frameworks/Python.framework/Versions/3.10/bin/sumo"
K_NODES = 2
MARGIN_S = 0.5
PERSIST_S = 10.0
HOLD_RADIUS_M = 25.0
HOLD_SPEED_MPS = 2.0


def path_of(map_id):
    with open(os.path.join(ROOT, "assets", "controlled", "manifest.json"), encoding="utf-8") as h:
        m = json.load(h)
    if map_id in m:
        return os.path.join(ROOT, m[map_id]["path"])
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as h:
        return {x["map_id"]: x["path"] for x in json.load(h)["maps"]}[map_id]


class _Persist:
    def __init__(self):
        self.since = None
        self.at = None

    def update(self, ok, t):
        if ok:
            self.since = t if self.since is None else self.since
            if self.at is None and t - self.since >= PERSIST_S:
                self.at = self.since
        else:
            self.since = None


def run_one(map_id, index, speed, strategy, seed, salt, team, record=False):
    import sumolib

    from joint_interception.domain.contracts import load_domain
    from joint_interception.native.caging import Reach, certificate, plan_commands, vehicle_edge
    from joint_interception.native.engine import run_plan
    from joint_interception.simulator.evader import EvaderLevel
    from joint_interception.world.construction import Plan, make_scenario
    from joint_interception.world.network import GraphNetwork

    domain = load_domain()
    path = path_of(map_id)
    net = GraphNetwork.from_sumo(path)
    pursuers = domain["team"]["pursuer_ids"][:team]
    sc = make_scenario(net, map_id, EvaderLevel.AVOIDANT, pursuers, f"{salt}s{index}")
    if len(sc.pursuer_starts) != team:
        return None
    coords = {n.getID(): n.getCoord() for n in sumolib.net.readNet(path).getNodes()}
    reach = Reach(net)
    history: list[dict] = []
    time_cage, phys_cage = _Persist(), _Persist()
    last = {"assignment": {}}

    def controller(d, t, states, conn):
        if "e1" not in states:
            return {}
        e_pos = vehicle_edge(states["e1"], conn, "e1", net)
        p_pos, fronts = {}, {}
        for vid in sc.pursuer_starts:
            if vid in states:
                pos = vehicle_edge(states[vid], conn, vid, net)
                if pos is not None:
                    p_pos[vid] = pos
                    fronts[vid] = (conn.vehicle.getPosition(vid), states[vid][3])
        if e_pos is None or not p_pos:
            return {}
        safe, gates, t_e, per = certificate(reach, e_pos, p_pos, speed, MARGIN_S)
        commands, assignment = plan_commands(
            strategy, reach, safe, gates, t_e, per, e_pos[0], net, previous=last["assignment"]
        )
        last["assignment"] = assignment
        held = {
            g
            for g in gates
            if g in coords
            and any(
                math.dist(xy, coords[g]) <= HOLD_RADIUS_M and v <= HOLD_SPEED_MPS
                for xy, v in fronts.values()
            )
        }
        small = len(safe) <= K_NODES
        time_cage.update(small, t)
        phys_cage.update(small and held == gates, t)
        entry = {"t": t, "safe": len(safe), "gates": len(gates), "held": len(held)}
        if record:
            entry.update(
                {"safe_nodes": sorted(safe), "gate_nodes": sorted(gates), "assignment": assignment}
            )
        history.append(entry)
        return commands

    def stop_when(t):
        return phys_cage.at is not None and t >= phys_cage.at + PERSIST_S + 10.0

    run = run_plan(
        net,
        path,
        sc,
        Plan(),
        domain,
        SUMO,
        sigma=0.5,
        seed=seed,
        label=f"cf{map_id[:3]}{index}{strategy[0]}{team}{int(speed * 10)}{seed}",
        controller=controller,
        evader_speed_factor=speed,
        stop_when=stop_when,
        stop_on_capture=False,
    )
    row = {
        "map_id": map_id,
        "index": index,
        "team": team,
        "speed": speed,
        "strategy": strategy,
        "seed": seed,
        "time_caged": time_cage.at is not None,
        "time_caged_at": time_cage.at,
        "phys_caged": phys_cage.at is not None,
        "phys_caged_at": phys_cage.at,
        "min_safe": min((h["safe"] for h in history), default=None),
        "contact_capture": run.verdict.verdict.value == "SUPPORTED",
        "collisions": len(run.collisions),
        # > 7 m/s^2 (0.7 m/s in one 0.1 s step): true emergency braking. The engine's
        # hard_braking (> 5 m/s^2) also counts ordinary 4.5 m/s^2 braking plus sigma dawdling.
        "emergency_braking": _emergencies(run.trace),
        "hard_braking": len(run.hard_braking),
        "end_s": run.trace[-1].time_s if run.trace else 0.0,
    }
    if record:
        return row, run, history, sc
    return row


def _emergencies(trace):
    count, last = 0, {}
    for f in trace:
        for vid, v in f.vehicles.items():
            if vid in last and last[vid] - v.speed_mps > 0.7:
                count += 1
            last[vid] = v.speed_mps
    return count


def task(args):
    return run_one(*args)


def bootstrap(xs, reps=10000, seed=7):
    if not xs:
        return None, None, None
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(reps))
    return sum(xs) / len(xs), means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def paired(rows, metric, a, b):
    diffs = []
    for key in sorted({r["index"] for r in rows}):
        x = [r[metric] for r in rows if r["index"] == key and r["strategy"] == a]
        y = [r[metric] for r in rows if r["index"] == key and r["strategy"] == b]
        if x and y:
            diffs.append(sum(x) / len(x) - sum(y) / len(y))
    mean, lo, hi = bootstrap(diffs)
    return None if mean is None else [round(mean, 3), round(lo, 3), round(hi, 3)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--maps", nargs="+", required=True)
    parser.add_argument("--teams", nargs="+", type=int, default=[3, 4, 5])
    parser.add_argument("--speeds", nargs="+", type=float, default=[1.0, 1.2, 1.5])
    parser.add_argument("--strategies", nargs="+", default=["cut", "individual", "pursuit"])
    parser.add_argument("--scenarios", type=int, default=15)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--salt", required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    tasks = [
        (m, i, sp, st, 8000 + k, args.salt, tm)
        for m in args.maps
        for tm in args.teams
        for sp in args.speeds
        for i in range(args.scenarios)
        for st in args.strategies
        for k in range(1, args.seeds + 1)
    ]
    rows = []
    with (
        mp.get_context("spawn").Pool(args.workers) as pool,
        open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as out,
    ):
        for row in pool.imap_unordered(task, tasks, chunksize=3):
            if row is None:
                continue
            rows.append(row)
            out.write(json.dumps(row) + "\n")
            out.flush()
    cells = {}
    for m in args.maps:
        for tm in args.teams:
            for sp in args.speeds:
                rs = [r for r in rows if r["map_id"] == m and r["team"] == tm and r["speed"] == sp]
                if not rs:
                    continue
                entry = {"runs": len(rs)}
                for st in args.strategies:
                    x = [r for r in rs if r["strategy"] == st]
                    n = max(1, len(x))
                    entry[f"time_{st}"] = round(sum(r["time_caged"] for r in x) / n, 3)
                    entry[f"phys_{st}"] = round(sum(r["phys_caged"] for r in x) / n, 3)
                    entry[f"contact_{st}"] = round(sum(r["contact_capture"] for r in x) / n, 3)
                entry["d_phys_cut_minus_individual"] = paired(rs, "phys_caged", "cut", "individual")
                entry["d_time_cut_minus_individual"] = paired(rs, "time_caged", "cut", "individual")
                entry["d_phys_cut_minus_pursuit"] = paired(rs, "phys_caged", "cut", "pursuit")
                d = entry["d_phys_cut_minus_individual"]
                entry["coordination_regime"] = bool(
                    d and d[1] > 0.05 and 0.10 <= entry["phys_cut"] <= 0.95
                )
                cells[f"{m}|team{tm}|x{sp}"] = entry
    diffs = []
    groups: dict = {}
    for r in rows:
        key = (r["map_id"], r["team"], r["speed"], r["index"])
        groups.setdefault(key, {}).setdefault(r["strategy"], []).append(r["phys_caged"])
    for key in sorted(groups):
        a, b = groups[key].get("cut"), groups[key].get("individual")
        if a and b:
            diffs.append(sum(a) / len(a) - sum(b) / len(b))
    mean, lo, hi = bootstrap(diffs)
    primary = {
        "pooled_real_map_delta_phys": None
        if mean is None
        else [round(mean, 3), round(lo, 3), round(hi, 3)],
        "scenario_cells": len(diffs),
        "passes": lo is not None and lo > 0,
        "rule": "pooled over maps, team sizes, speeds: paired Delta P(phys cage) cut - individual, bootstrap over scenario cells, CI lower > 0",
    }
    regime = [k for k, v in cells.items() if v["coordination_regime"]]
    real = [k for k in regime if not k.startswith("C")]
    summary = {
        "primary": primary,
        "cells": cells,
        "coordination_regime_cells": regime,
        "secondary_regime_cells_with_real": len(real),
    }
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(summary, h, indent=2)
    print(json.dumps({"primary": primary, "regime": regime}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
