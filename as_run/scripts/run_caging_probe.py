"""F1 caging feasibility probe (A-70). SUMO only, parallel.

Task = (map, scenario, evader speed factor, strategy, SUMO seed). Per run: the caging certificate
at every decision; caged = safe region <= K junctions held PERSIST_S; contact capture (D06 + A-57,
any pursuer) reported alongside. Summary per map and speed: P(caged) per strategy and the paired
difference cut - individual and cut - pursuit, bootstrapped over scenarios.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
SUMO = "/Library/Frameworks/Python.framework/Versions/3.10/bin/sumo"
K_NODES = 2
MARGIN_S = 0.5
PERSIST_S = 10.0


def path_of(map_id):
    with open(os.path.join(ROOT, "assets", "controlled", "manifest.json"), encoding="utf-8") as h:
        m = json.load(h)
    if map_id in m:
        return os.path.join(ROOT, m[map_id]["path"])
    with open(os.path.join(ROOT, "MAPS_STATUS.json"), encoding="utf-8") as h:
        return {x["map_id"]: x["path"] for x in json.load(h)["maps"]}[map_id]


def run_one(map_id, index, speed, strategy, seed, salt, record=False):
    from joint_interception.domain.contracts import load_domain
    from joint_interception.native.caging import Reach, certificate, plan_commands, vehicle_edge
    from joint_interception.native.engine import run_plan
    from joint_interception.simulator.evader import EvaderLevel
    from joint_interception.world.construction import Plan, make_scenario
    from joint_interception.world.network import GraphNetwork

    domain = load_domain()
    path = path_of(map_id)
    net = GraphNetwork.from_sumo(path)
    sc = make_scenario(
        net, map_id, EvaderLevel.AVOIDANT, domain["team"]["pursuer_ids"], f"{salt}s{index}"
    )
    if len(sc.pursuer_starts) != len(domain["team"]["pursuer_ids"]):
        return None
    reach = Reach(net)
    history: list[dict] = []
    state = {"run_since": None, "caged_at": None}

    def controller(d, t, states, conn):
        if "e1" not in states:
            return {}
        e_pos = vehicle_edge(states["e1"], conn, "e1", net)
        p_pos = {}
        for vid in sc.pursuer_starts:
            if vid in states:
                pos = vehicle_edge(states[vid], conn, vid, net)
                if pos is not None:
                    p_pos[vid] = pos
        if e_pos is None or not p_pos:
            return {}
        safe, gates, t_e, per = certificate(reach, e_pos, p_pos, speed, MARGIN_S)
        commands, assignment = plan_commands(strategy, reach, safe, gates, t_e, per, e_pos[0], net)
        caged = len(safe) <= K_NODES
        if caged:
            state["run_since"] = t if state["run_since"] is None else state["run_since"]
            if state["caged_at"] is None and t - state["run_since"] >= PERSIST_S:
                state["caged_at"] = state["run_since"]
        else:
            state["run_since"] = None
        entry = {"t": t, "safe": len(safe), "gates": len(gates)}
        if record:
            entry.update(
                {"safe_nodes": sorted(safe), "gate_nodes": sorted(gates), "assignment": assignment}
            )
        history.append(entry)
        return commands

    def stop_when(t):
        return state["caged_at"] is not None and t >= state["caged_at"] + PERSIST_S + 20.0

    run = run_plan(
        net,
        path,
        sc,
        Plan(),
        domain,
        SUMO,
        sigma=0.5,
        seed=seed,
        label=f"cg{map_id[:3]}{index}{strategy[0]}{int(speed * 10)}{seed}",
        controller=controller,
        evader_speed_factor=speed,
        stop_when=stop_when,
        stop_on_capture=False,
    )
    row = {
        "map_id": map_id,
        "index": index,
        "speed": speed,
        "strategy": strategy,
        "seed": seed,
        "caged": state["caged_at"] is not None,
        "caged_at": state["caged_at"],
        "min_safe": min((h["safe"] for h in history), default=None),
        "mean_safe_first_60s": round(
            sum(h["safe"] for h in history[:60]) / max(1, len(history[:60])), 2
        ),
        "contact_capture": run.verdict.verdict.value == "SUPPORTED",
        "collisions": len(run.collisions),
        "hard_braking": len(run.hard_braking),
        "end_s": run.trace[-1].time_s if run.trace else 0.0,
    }
    if record:
        return row, run, history, sc
    return row


def task(args):
    return run_one(*args)


def bootstrap(xs, reps=10000, seed=7):
    if not xs:
        return None, None, None
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(reps))
    return sum(xs) / len(xs), means[int(0.025 * reps)], means[int(0.975 * reps) - 1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--maps", nargs="+", required=True)
    parser.add_argument("--scenarios", type=int, default=20)
    parser.add_argument("--speeds", nargs="+", type=float, default=[1.0, 1.2])
    parser.add_argument("--strategies", nargs="+", default=["cut", "individual", "pursuit"])
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--salt", required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    tasks = [
        (m, i, sp, st, 7000 + k, args.salt)
        for m in args.maps
        for i in range(args.scenarios)
        for sp in args.speeds
        for st in args.strategies
        for k in range(1, args.seeds + 1)
    ]
    rows = []
    with (
        mp.get_context("spawn").Pool(args.workers) as pool,
        open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as out,
    ):
        for row in pool.imap_unordered(task, tasks, chunksize=4):
            if row is None:
                continue
            rows.append(row)
            out.write(json.dumps(row) + "\n")
    summary = {}
    for scope in [*args.maps, "POOLED"]:
        for sp in args.speeds:
            rs = [
                r for r in rows if r["speed"] == sp and (scope == "POOLED" or r["map_id"] == scope)
            ]
            entry = {}
            for st in args.strategies:
                x = [r for r in rs if r["strategy"] == st]
                entry[f"p_caged_{st}"] = round(sum(r["caged"] for r in x) / max(1, len(x)), 3)
                entry[f"p_contact_{st}"] = round(
                    sum(r["contact_capture"] for r in x) / max(1, len(x)), 3
                )
            for other in [s for s in args.strategies if s != "cut"]:
                diffs = []
                for key in sorted({(r["map_id"], r["index"]) for r in rs}):
                    a = [
                        r["caged"]
                        for r in rs
                        if (r["map_id"], r["index"]) == key and r["strategy"] == "cut"
                    ]
                    b = [
                        r["caged"]
                        for r in rs
                        if (r["map_id"], r["index"]) == key and r["strategy"] == other
                    ]
                    if a and b:
                        diffs.append(sum(a) / len(a) - sum(b) / len(b))
                mean, lo, hi = bootstrap(diffs)
                entry[f"delta_cut_minus_{other}"] = (
                    None if mean is None else [round(mean, 3), round(lo, 3), round(hi, 3)]
                )
            entry["runs"] = len(rs)
            summary[f"{scope}@{sp}"] = entry
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(summary, h, indent=2)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
