"""Audit of the physical-cage certificate (A-83): is a certified evader actually trapped?

Re-runs every certified cage of a sealed pilot evaluation in SUMO, continues 60 s past certification
under two conditions (hold: pursuers keep their last command; policy: the policy keeps deciding),
and records per controller step the evader's speed, leader, next signal and edge, and the
certificate. Measures and the pre-declared reading are in the package PROTOCOL_EN.md.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import multiprocessing as mp
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from train_caging_pilot import SPEED, SUMO, TEAM, _init_worker, _net, _paths  # noqa: E402

PURSUERS = tuple(f"p{k}" for k in range(1, 10))
STOP_MPS = 0.5
BLOCK_GAP_M = 15.0
SIGNAL_M = 30.0


def _run(
    net,
    map_id,
    sc,
    domain,
    policy,
    speed,
    seed,
    label,
    arm,
    post_cage_s,
    probe,
    extra_sumo_args,
    command_policy,
    reward_mode,
    pursuer_speed,
):
    from joint_interception.rl.rollout import run_episode

    return run_episode(
        net,
        _paths()[map_id],
        sc,
        domain,
        SUMO,
        policy,
        speed_factor=SPEED if speed is None else speed,
        seed=seed,
        label=label,
        arm=arm,
        keep_trace=True,
        post_cage_s=post_cage_s,
        probe=probe,
        extra_sumo_args=extra_sumo_args,
        command_policy=command_policy,
        reward_mode=reward_mode,
        pursuer_speed_factor=pursuer_speed,
    )


def replay(
    map_id,
    index,
    seed,
    salt,
    arm,
    weights,
    condition,
    post_cage_s,
    expected=None,
    kind=None,
    hold_on="junction",
    speed=None,
    active=None,
    level=None,
    team=None,
    extra_sumo_args=None,
    learner=None,
    reward_mode="certificate",
    pursuer_speed=1.0,
):
    """One episode; returns (episode, per-step records). Also used by the GIF renderer and the
    endpoint studies. `kind` (heuristics without weights): None/"cut", "individual", "random",
    "nearest" (A-88: each pursuer to the gate it reaches soonest), "pursuit" (A-88: all chase).
    `hold_on`: which certificate triggers the hold condition ("junction" A-72, "lane" A-88,
    "lane_nv" A-90: lane-level with at least one gate). `speed`: evader speed factor (default the
    pilots' 1.5). `active` (A-90): keep only these pursuers, at the same start positions.
    `level`, `team`, `extra_sumo_args` (A-92): evader level name, team size, extra SUMO args."""
    import torch

    from joint_interception.domain.contracts import load_domain
    from joint_interception.rl.policy import TokenPolicy, decide
    from joint_interception.rl.rollout import CHASE, HOLD, PERSIST_S, cut_policy
    from joint_interception.simulator.evader import EvaderLevel
    from joint_interception.world.construction import make_scenario

    domain = load_domain()
    net = _net(map_id)
    sc = make_scenario(
        net,
        map_id,
        EvaderLevel.AVOIDANT if level is None else EvaderLevel[level],
        # A-98: teams beyond the domain's 5 ids use p6, p7, ... (same placement rule, nested).
        [f"p{k}" for k in range(1, (TEAM if team is None else team) + 1)],
        f"{salt}s{index}",
    )
    if len(sc.pursuer_starts) != (TEAM if team is None else team):
        raise ValueError("scenario could not place the team")
    if active is not None:
        import dataclasses

        sc = dataclasses.replace(
            sc, pursuer_starts={k: v for k, v in sc.pursuer_starts.items() if k in active}
        )
    command_policy = None
    if kind == "learned_ambush":
        # A-96: learner = {"head", "weights" (bytes or None), "mode", "seed"}
        from joint_interception.native.ambush_learning import OptionAmbush
        from joint_interception.rl.option_policy import OptionScorer

        model = None
        if learner.get("weights") is not None:
            model = OptionScorer(learner["head"])
            model.load_state_dict(torch.load(io.BytesIO(learner["weights"]), weights_only=True))
            model.eval()
        command_policy = OptionAmbush(model, learner["mode"], learner.get("seed", 0))
        arm = "T"

        def base(obs):
            return {}
    elif kind in ("mappo_v2", "mappo_v3"):
        # A-116: corrected controller (faithful teacher, 40 slots); same learner dict as "mappo".
        # A-133: "mappo_v3" records the critic's state before the step's choices and samples
        # with the controller's own generator.
        from joint_interception.native.mappo_ambush_v2 import MappoAmbushV2
        from joint_interception.native.mappo_ambush_v3 import MappoAmbushV3
        from joint_interception.rl.mappo_policy import MappoActorCritic

        model = None
        if learner.get("weights") is not None:
            model = MappoActorCritic(learner["head"])
            model.load_state_dict(torch.load(io.BytesIO(learner["weights"]), weights_only=True))
            model.eval()
        controller_class = MappoAmbushV3 if kind == "mappo_v3" else MappoAmbushV2
        command_policy = controller_class(
            learner["params"], model, learner["mode"], learner.get("seed", 0)
        )
        arm = "T"

        def base(obs):
            return {}
    elif kind == "mappo":
        # A-103: learner = {"params", "head", "weights" (bytes or None), "mode", "seed"}
        from joint_interception.native.mappo_ambush import MappoAmbush
        from joint_interception.rl.mappo_policy import MappoActorCritic

        model = None
        if learner.get("weights") is not None:
            model = MappoActorCritic(learner["head"])
            model.load_state_dict(torch.load(io.BytesIO(learner["weights"]), weights_only=True))
            model.eval()
        command_policy = MappoAmbush(
            learner["params"], model, learner["mode"], learner.get("seed", 0)
        )
        arm = "T"

        def base(obs):
            return {}
    elif weights is None and kind == "ambush_plus":
        from joint_interception.native.ambush_plus import AmbushPlusPlanner

        command_policy, arm = AmbushPlusPlanner((learner or {}).get("params")), "T"

        def base(obs):
            return {}
    elif weights is None and kind == "ambush":
        from joint_interception.native.ambush import AmbushPlanner

        command_policy, arm = AmbushPlanner(), "T"

        def base(obs):
            return {}
    elif weights is None and kind == "nearest":
        arm = "T"

        def base(obs):
            return {
                v: (min(range(len(obs[v])), key=lambda i: obs[v][i][1][2]) if obs[v] else CHASE)
                for v in obs
                if not v.startswith("_")
            }
    elif weights is None and kind == "pursuit":
        arm = "T"

        def base(obs):
            return {v: CHASE for v in obs if not v.startswith("_")}
    elif weights is None and kind == "individual":
        arm = "T"

        def base(obs):
            return {
                v: (max(range(len(obs[v])), key=lambda i: obs[v][i][1][3]) if obs[v] else CHASE)
                for v in obs
                if not v.startswith("_")
            }
    elif weights is None and kind == "random":
        arm, rng = "T", random.Random(seed)

        def base(obs):
            return {
                v: (rng.randrange(len(obs[v])) if obs[v] and rng.random() < 0.8 else CHASE)
                for v in sorted(obs)
                if not v.startswith("_")
            }
    elif weights is None:
        base, arm = cut_policy(), "T"
    else:
        model = TokenPolicy()
        model.load_state_dict(torch.load(io.BytesIO(weights), weights_only=True))
        model.eval()

        def base(obs):
            return decide(model, obs, greedy=True)[0]

    records: list[dict] = []
    cert = {"since": None, "at": None}

    def probe(t, states, conn, info):
        flags = {
            "junction": info["caged_now"],
            "lane": info["caged_lane_now"],
            "lane_nv": info["caged_lane_now"] and len(info["gates"]) >= 1,
        }
        if flags[hold_on]:
            cert["since"] = t if cert["since"] is None else cert["since"]
            if cert["at"] is None and t - cert["since"] >= PERSIST_S:
                cert["at"] = t
        else:
            cert["since"] = None
        leader = None
        try:
            got = conn.vehicle.getLeader("e1", 60.0)
            if got and got[0]:
                leader = (got[0], round(got[1], 2))
        except Exception:  # noqa: BLE001 - evader momentarily off-road
            leader = None
        follower = None
        try:
            got = conn.vehicle.getFollower("e1", 60.0)
            if got and got[0]:
                follower = (got[0], round(got[1], 2))
        except Exception:  # noqa: BLE001
            follower = None
        signal = None
        try:
            tls = conn.vehicle.getNextTLS("e1")
            if tls:
                signal = (tls[0][0], round(tls[0][2], 1), tls[0][3])
        except Exception:  # noqa: BLE001
            signal = None
        ex, ey = conn.vehicle.getPosition("e1")
        records.append(
            {
                "t": round(t, 2),
                "v_e": round(states["e1"][3], 2),
                "edge": states["e1"][0],
                "xy": (round(ex, 1), round(ey, 1)),
                "leader": leader,
                "follower": follower,
                "signal": signal,
                "caged_now": info["caged_now"],
                "caged_lane_now": info["caged_lane_now"],
                "held_lane": sorted(info["held_lane"]),
                "safe": sorted(info["safe"]),
                "gates": sorted(info["gates"]),
                "held": sorted(info["held"]),
                "pursuers": {v: round(states[v][3], 2) for v in states if v in PURSUERS},
                "pursuer_edges": {v: states[v][0] for v in states if v in PURSUERS},
                "pursuer_lanes": {v: states[v][1] for v in states if v in PURSUERS},
                "pursuer_xy": {
                    v: tuple(round(c, 1) for c in conn.vehicle.getPosition(v))
                    for v in states
                    if v in PURSUERS
                },
                "evader_lane": states["e1"][1],
            }
        )

    def policy(obs):
        if condition == "hold" and cert["at"] is not None:
            return {v: HOLD for v in obs if not v.startswith("_")}
        return base(obs)

    label = f"au{condition[0]}{map_id[:3]}{index}_{seed}"
    try:
        ep = _run(
            net,
            map_id,
            sc,
            domain,
            policy,
            speed,
            seed,
            label,
            arm,
            post_cage_s,
            probe,
            extra_sumo_args,
            command_policy,
            reward_mode,
            pursuer_speed,
        )
    except Exception:
        # A-103: an exception inside the episode left the TraCI connection open, and every later
        # episode with the same label in that worker failed ("Connection ... is already active").
        import traci

        try:
            traci.switch(label)
            traci.close()
        except Exception:  # noqa: BLE001
            pass
        raise
    if command_policy is not None:
        ep.planner_stats = dict(command_policy.stats)
        ep.lead_log = list(getattr(command_policy, "lead_log", []))
        ep.mappo_ticks = list(getattr(command_policy, "ticks", []))
        ep.planner_history = list(command_policy.history)
        ep.learner_records = list(getattr(command_policy, "records", []))
        ep.choice_counts = dict(getattr(command_policy, "choice_counts", {}))
        # A-116: teacher fidelity counters of the v2 controller.
        ep.teacher_represented = getattr(command_policy, "represented", None)
        ep.teacher_unrepresentable = getattr(command_policy, "unrepresentable", None)
    return ep, records


def measures(ep, records, net, post_cage_s):
    from joint_interception.rl.rollout import PERSIST_S

    if ep.caged_at is None:
        return {"caged": False}
    t_cert = ep.caged_at + PERSIST_S
    at = min(records, key=lambda r: abs(r["t"] - t_cert))
    gates = set(at["gates"])
    window = [r for r in records if t_cert - 1e-6 <= r["t"] <= t_cert + post_cage_s + 1e-6]

    def blocked(r):
        return (
            r["v_e"] <= STOP_MPS
            and r["leader"] is not None
            and r["leader"][0] in PURSUERS
            and r["leader"][1] <= BLOCK_GAP_M
        )

    def red(r):
        return (
            r["v_e"] <= STOP_MPS
            and r["signal"] is not None
            and r["signal"][1] <= SIGNAL_M
            and r["signal"][2] in "rRyYu"
            and not blocked(r)
        )

    # r02: ENTERING a new edge whose origin was a gate. r01 also counted the edge the evader was
    # already on at certification (its rear junction is often a gate via a U-turn), void.
    escape_t, escape_gate = None, None
    edge0 = at["edge"]
    for r in window:
        e = r["edge"]
        if e == edge0 or e.startswith(":") or e not in net.edges:
            continue
        if net.edges[e].from_node in gates:
            escape_t, escape_gate = r["t"] - t_cert, net.edges[e].from_node
            break
        edge0 = e
    block_t, run_start = None, None
    for r in records:
        if r["t"] < ep.caged_at - 1e-6:
            continue
        if blocked(r):
            run_start = r["t"] if run_start is None else run_start
            if r["t"] - run_start >= 2.0 - 1e-6 and block_t is None:
                block_t = run_start - t_cert
        else:
            run_start = None
    x0 = at["xy"]
    return {
        "caged": True,
        "caged_at": ep.caged_at,
        "t_cert": t_cert,
        "window_s": round(window[-1]["t"] - t_cert, 1) if window else 0.0,
        "v_e_at_cert": at["v_e"],
        "state_at_cert": "blocked"
        if blocked(at)
        else ("red_light" if red(at) else ("stopped" if at["v_e"] <= STOP_MPS else "moving")),
        "escaped": escape_t is not None,
        "escape_after_s": escape_t,
        "escape_gate": escape_gate,
        "left_network": ep.evader_exited and escape_t is None,
        "blocked": block_t is not None and block_t <= post_cage_s,
        "block_after_cert_s": block_t,
        "cert_valid_share": round(sum(r["caged_now"] for r in window) / max(1, len(window)), 3),
        "cert_valid_at_end": bool(window and window[-1]["caged_now"]),
        "max_displacement_m": round(max((math.dist(x0, r["xy"]) for r in window), default=0.0), 1),
        "contact_capture": ep.contact_capture,
        "evader_exited": ep.evader_exited,
        "n_gates_at_cert": len(gates),
        "n_safe_at_cert": len(at["safe"]),
    }


def task(args):
    checkpoint, weights, arm, map_id, index, seed, salt, expected, condition, post = args
    try:
        ep, records = replay(map_id, index, seed, salt, arm, weights, condition, post)
        row = measures(ep, records, _net(map_id), post)
        if ep.caged_at is not None:
            row["records"] = [
                {k: v for k, v in r.items() if k != "safe"} | {"n_safe": len(r["safe"])}
                for r in records
                if r["t"] >= ep.caged_at - 10.0
            ]
    except Exception as error:  # noqa: BLE001
        row = {"failed": f"{type(error).__name__}: {str(error)[:160]}"}
    return {
        "checkpoint": checkpoint,
        "condition": condition,
        "map_id": map_id,
        "index": index,
        "seed": seed,
        "expected_caged_at": expected,
        **row,
        "reproduced": row.get("caged_at") == expected,
    }


def bootstrap(xs, reps=10000, seed=7):
    if not xs:
        return None
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(reps))
    return [round(sum(xs) / len(xs), 3), round(means[250], 3), round(means[9749], 3)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--pilot", required=True)
    parser.add_argument(
        "--checkpoints",
        nargs="+",
        default=["T_seed1_final", "T_seed2_final", "U_seed1_final", "U_seed2_final", "cut"],
    )
    parser.add_argument("--conditions", nargs="+", default=["hold", "policy"])
    parser.add_argument("--post-cage-s", type=float, default=60.0)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    package = os.path.join(ROOT, args.package)
    pilot = os.path.join(ROOT, args.pilot)
    with open(os.path.join(pilot, "inputs.json"), encoding="utf-8") as h:
        salt = json.load(h)["arguments"]["eval_salt"]
    with open(os.path.join(pilot, "eval.jsonl"), encoding="utf-8") as h:
        evals = [json.loads(line) for line in h]
    tasks = []
    for c in args.checkpoints:
        weights = None
        if c != "cut":
            with open(os.path.join(pilot, "checkpoints", f"{c}.pt"), "rb") as h:
                weights = h.read()
        for r in evals:
            if r["checkpoint"] == c and r["caged"]:
                for cond in args.conditions:
                    tasks.append(
                        (
                            c,
                            weights,
                            c[0],
                            r["map_id"],
                            r["index"],
                            r["seed"],
                            salt,
                            r["caged_at"],
                            cond,
                            args.post_cage_s,
                        )
                    )
    print(json.dumps({"stage": "start", "episodes": len(tasks)}), flush=True)
    with mp.get_context("spawn").Pool(args.workers, initializer=_init_worker) as pool:
        rows = pool.map(task, tasks, chunksize=1)
    import gzip

    with gzip.open(os.path.join(package, "records.jsonl.gz"), "wt", encoding="utf-8") as h:
        for r in rows:
            key = {k: r[k] for k in ("checkpoint", "condition", "map_id", "index")}
            h.write(json.dumps(key | {"records": r.pop("records", [])}) + "\n")
    with open(os.path.join(package, "results.jsonl"), "w", encoding="utf-8") as h:
        for r in rows:
            h.write(json.dumps(r) + "\n")
    summary = {"failed": sum("failed" in r for r in rows), "by_condition": {}}
    for cond in args.conditions:
        rs = [r for r in rows if r["condition"] == cond and r.get("caged")]
        block = {
            "certified_cages": len(rs),
            "reproduced_certification": round(
                sum(r["reproduced"] for r in rs) / max(1, len(rs)), 3
            ),
            "M1_escape": bootstrap([float(r["escaped"]) for r in rs]),
            "M1b_left_network_without_gate_crossing": bootstrap(
                [float(r["left_network"]) for r in rs]
            ),
            "cages_with_no_gate": sum(r["n_gates_at_cert"] == 0 for r in rs),
            "M2_blocked_within_window": bootstrap([float(r["blocked"]) for r in rs]),
            "M3_red_light_at_cert": bootstrap(
                [float(r["state_at_cert"] == "red_light") for r in rs]
            ),
            "M4_contact_capture": bootstrap([float(r["contact_capture"]) for r in rs]),
            "state_at_cert": {
                s: sum(r["state_at_cert"] == s for r in rs)
                for s in ("blocked", "red_light", "stopped", "moving")
            },
            "cert_valid_share_mean": round(
                sum(r["cert_valid_share"] for r in rs) / max(1, len(rs)), 3
            ),
            "by_checkpoint": {
                c: {
                    "n": len([r for r in rs if r["checkpoint"] == c]),
                    "escape": bootstrap([float(r["escaped"]) for r in rs if r["checkpoint"] == c]),
                    "blocked": bootstrap([float(r["blocked"]) for r in rs if r["checkpoint"] == c]),
                }
                for c in args.checkpoints
            },
        }
        if cond == "hold":
            upper = block["M1_escape"][2] if block["M1_escape"] else None
            block["certificate_adequate"] = upper is not None and upper <= 0.10
        summary["by_condition"][cond] = block
    with open(os.path.join(package, "summary.json"), "w", encoding="utf-8") as h:
        json.dump(summary, h, indent=2)
    print(json.dumps({"stage": "summary", **summary}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
