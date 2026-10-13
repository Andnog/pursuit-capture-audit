"""Episode rollout for the caging MARL study (docs/MARL_DESIGN_EN.md), in SUMO.

A policy is any callable `policy(obs) -> {pursuer: choice}` where `obs` holds, per pursuer, the
GATE TOKENS of the certificate (arm T). A choice is an index into that pursuer's tokens, or
`CHASE` (drive to the evader's edge) or `HOLD` (keep the current command). The episode runs in
SUMO with the legal control interface (A-76); the policy is called every decision.

Reward per decision: potential-based shaping Phi = -log(1 + |safe region|), minus a small time
cost; -1 and stop on a collision. Terminal +1 (`reward_mode`):
- "certificate" (A-72, up to r03): the physical cage has held PERSIST_S;
- "trap" (A-86, r04): the evader is TRAPPED - immobilised (<= 0.5 m/s) for IMMOBILE_S behind a
  pursuer leader within TRAP_GAP_M, with no red/yellow signal within TRAP_SIGNAL_M (A-84).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..native.caging import Reach, _edge_into, certificate, lane_held, vehicle_edge
from ..native.engine import run_plan
from ..world.construction import Plan

CHASE = -1
HOLD = -2
K_NODES = 2
MARGIN_S = 0.5
PERSIST_S = 10.0
HOLD_RADIUS_M = 25.0
HOLD_SPEED_MPS = 2.0
TIME_COST = 0.001
DECISION_PERIOD_S = 5.0
# A-84 trapping endpoint (same thresholds as scripts/run_trap_endpoint.py).
TRAP_STOP_MPS = 0.5
TRAP_GAP_M = 15.0
TRAP_SIGNAL_M = 30.0
IMMOBILE_S = 10.0
TOKEN_FEATURES = (
    "t_evader",
    "t_team_best",
    "t_own",
    "slack_own",
    "degree",
    "taken_by_other",
    "own_target",
    "urgency_rank",
    "own_minus_best_other",
)


@dataclass
class Transition:
    t: float
    obs: dict
    action: dict
    reward: float


@dataclass
class Episode:
    transitions: list[Transition] = field(default_factory=list)
    caged_at: float | None = None
    collided: bool = False
    emergencies: int = 0
    contact_capture: bool = False
    evader_exited: bool = False
    end_s: float = 0.0
    trapped_at: float | None = None
    trace: list | None = None
    overlays: list | None = None
    # A-137 (F5-1): every collision the engine reported, as {"t", "vehicles"}. `collided` alone
    # could not tell a collision inside a trained interval from one after it.
    collision_events: list = field(default_factory=list)

    @property
    def total_reward(self) -> float:
        return sum(tr.reward for tr in self.transitions)


U_CANDIDATES = 24


def candidate_tokens(candidates, t_e, per, degree, previous_targets):
    """Per pursuer: list of (junction, feature vector) over `candidates`, in the given (urgency)
    order. Features (same for both arms): evader arrival, team-best arrival, own arrival, own
    slack, junction degree, taken by another pursuer, IS MY CURRENT TARGET, urgency rank, own
    arrival minus the best other pursuer's (A-80: the last three let a policy represent the cut
    heuristic's keep-your-gate and fastest-free-pursuer rules, which BC could not imitate)."""
    obs = {}
    team_best = {g: min(per[v][0].get(g, math.inf) for v in per) for g in candidates}
    last = max(1, len(candidates) - 1)
    for vid in sorted(per):
        own = per[vid][0]
        tokens = []
        for rank, g in enumerate(candidates):
            te, tb, to = t_e.get(g, math.inf), team_best[g], own.get(g, math.inf)
            others = [per[v][0].get(g, math.inf) for v in per if v != vid]
            best_other = min(others) if others else math.inf
            taken = any(tgt == g for other, tgt in previous_targets.items() if other != vid)
            gap = to - best_other if math.isfinite(to) and math.isfinite(best_other) else 0.0
            tokens.append(
                (
                    g,
                    [
                        min(te, 300.0),
                        min(tb, 300.0),
                        min(to, 300.0),
                        max(-300.0, min(te - to, 300.0)),
                        float(degree.get(g, 0)),
                        float(taken),
                        float(previous_targets.get(vid) == g),
                        rank / last,
                        max(-300.0, min(gap, 300.0)),
                    ],
                )
            )
        obs[vid] = tokens
    return obs


def gate_tokens(safe, gates, t_e, per, net, previous_targets):
    """Arm T: the escape gates of the evader's safe region (the topological inductive bias)."""
    degree = {}
    for info in net.edges.values():
        degree[info.to_node] = degree.get(info.to_node, 0) + 1
    obs = candidate_tokens(
        sorted(gates, key=lambda g: (t_e.get(g, math.inf), g)), t_e, per, degree, previous_targets
    )
    obs["_safe_size"] = len(safe)
    return obs


def neighbourhood_tokens(reach, e_pos, speed_factor, safe, per, net, previous_targets):
    """Arm U: the U_CANDIDATES junctions the evader reaches soonest - same features, no gate set."""
    degree = {}
    for info in net.edges.values():
        degree[info.to_node] = degree.get(info.to_node, 0) + 1
    dist, _ = reach.from_edge(*e_pos, speed_factor=speed_factor)
    t_full = reach.node_times(dist)
    near = sorted(t_full, key=lambda n: (t_full[n], n))[:U_CANDIDATES]
    obs = candidate_tokens(near, t_full, per, degree, previous_targets)
    obs["_safe_size"] = len(safe)
    return obs


def run_episode(
    net,
    net_file,
    scenario,
    domain,
    sumo_binary,
    policy,
    speed_factor=1.2,
    sigma=0.5,
    seed=1,
    label="rl",
    arm="T",
    extra_u=False,
    extra_t=False,
    keep_trace=False,
    post_cage_s=0.0,
    probe=None,
    reward_mode="certificate",
    extra_sumo_args=None,
    command_policy=None,
    pursuer_speed_factor=1.0,
):
    """`post_cage_s` (audit, A-83): keep simulating this long after the cage is certified, with
    the policy still in control. `probe(t, states, conn, info)` is called at every controller
    step with the certificate (`safe`, `gates`, `held`, `caged_now`)."""
    import sumolib

    snet = sumolib.net.readNet(net_file)
    coords = {n.getID(): n.getCoord() for n in snet.getNodes()}
    lane_cache: dict[str, list[str]] = {}

    def lanes_of(edge_id):
        if edge_id not in lane_cache:
            lane_cache[edge_id] = [
                ln.getID() for ln in snet.getEdge(edge_id).getLanes() if ln.allows("passenger")
            ]
        return lane_cache[edge_id]

    reach = Reach(net)
    ep = Episode()
    state = {
        "since": None,
        "prev_phi": None,
        "targets": {},
        "pending_r": 0.0,
        "last_t": None,
        "last_gates": None,
        "imm_since": None,
    }

    def controller(d, t, states, conn):
        if "e1" not in states:
            return {}
        e_pos = vehicle_edge(states["e1"], conn, "e1", net)
        p_pos, fronts = {}, {}
        for vid in scenario.pursuer_starts:
            if vid in states:
                pos = vehicle_edge(states[vid], conn, vid, net)
                if pos is not None:
                    p_pos[vid] = pos
                    fronts[vid] = (conn.vehicle.getPosition(vid), states[vid][3])
        if e_pos is None or not p_pos:
            return {}
        approaches = None
        if probe is None:
            safe, gates, t_e, per = certificate(
                reach,
                e_pos,
                p_pos,
                speed_factor,
                MARGIN_S,
                pursuer_speed_factor=pursuer_speed_factor,
            )
        else:
            safe, gates, t_e, per, approaches = certificate(
                reach,
                e_pos,
                p_pos,
                speed_factor,
                MARGIN_S,
                with_approaches=True,
                pursuer_speed_factor=pursuer_speed_factor,
            )
        held = {
            g
            for g in gates
            if g in coords
            and any(
                math.dist(xy, coords[g]) <= HOLD_RADIUS_M and v <= HOLD_SPEED_MPS
                for xy, v in fronts.values()
            )
        }
        caged_now = len(safe) <= K_NODES and held == gates
        if probe is not None:
            # A-88: lane-level holding, recorded for the audit and endpoint studies only.
            lanes_held = lane_held(
                gates,
                approaches,
                {  # a pursuer parked off the lane (A-68) blocks nothing
                    v: states[v]
                    for v in scenario.pursuer_starts
                    if v in states and not conn.vehicle.isStoppedParking(v)
                },
                states["e1"],
                HOLD_SPEED_MPS,
                lanes_of,
            )
            info = {
                "safe": safe,
                "gates": gates,
                "held": held,
                "caged_now": caged_now,
                "held_lane": lanes_held,
                "caged_lane_now": len(safe) <= K_NODES and lanes_held == gates,
            }
            probe(t, states, conn, info)
        phi = -math.log(1 + len(safe))
        reward = -TIME_COST
        if state["prev_phi"] is not None:
            reward += phi - state["prev_phi"]
        state["prev_phi"] = phi
        if caged_now:
            state["since"] = t if state["since"] is None else state["since"]
            if ep.caged_at is None and t - state["since"] >= PERSIST_S:
                ep.caged_at = state["since"]
                if reward_mode == "certificate":
                    reward += 1.0
        else:
            state["since"] = None
        if reward_mode == "trap" and _immobile(conn, states["e1"][3], scenario.pursuer_starts):
            state["imm_since"] = t if state["imm_since"] is None else state["imm_since"]
            if ep.trapped_at is None and t - state["imm_since"] >= IMMOBILE_S - 1e-6:
                ep.trapped_at = state["imm_since"]
                reward += 1.0
        else:
            state["imm_since"] = None
        state["pending_r"] += reward
        if keep_trace:
            ep.overlays = ep.overlays or []
            ep.overlays.append(
                {
                    "t": t,
                    "safe": len(safe),
                    "safe_nodes": sorted(safe),
                    "gate_nodes": sorted(gates),
                    "assignment": dict(state["targets"]),
                }
            )
        if command_policy is not None:
            # A-94: a planner that issues engine commands directly, every controller step
            # (the token interface cannot express lane-level blocking positions).
            if ep.transitions:
                ep.transitions[-1].reward += state["pending_r"]
            state["pending_r"] = 0.0
            return command_policy(
                {
                    "t": t,
                    "states": states,
                    "conn": conn,
                    "e_pos": e_pos,
                    "p_pos": p_pos,
                    "per": per,
                    "reach": reach,
                    "speed_factor": speed_factor,
                    "net": net,
                    "snet": snet,
                    "evader": getattr(controller, "evader", None),
                    "decision_s": getattr(controller, "decision_s", 1.0),
                }
            )
        # A-80: decide only on an EVENT - the gate set changed, a pursuer's target stopped being
        # a gate, or DECISION_PERIOD_S elapsed. Same schedule for both arms. Rewards accrued
        # between decisions belong to the previous decision (they were misattributed one step
        # late before A-80).
        gate_set = frozenset(gates)
        event = (
            state["last_t"] is None
            or gate_set != state["last_gates"]
            or t - state["last_t"] >= DECISION_PERIOD_S
            or any(g not in gate_set for g in state["targets"].values())
        )
        if not event:
            return {}
        if ep.transitions:
            ep.transitions[-1].reward += state["pending_r"]
        state["pending_r"] = 0.0
        state["last_t"], state["last_gates"] = t, gate_set
        if arm == "T":
            obs = gate_tokens(safe, gates, t_e, per, net, state["targets"])
        else:
            obs = neighbourhood_tokens(reach, e_pos, speed_factor, safe, per, net, state["targets"])
        if extra_t and arm != "T":
            obs["_T"] = gate_tokens(safe, gates, t_e, per, net, state["targets"])
        if extra_u:
            obs["_U"] = neighbourhood_tokens(
                reach, e_pos, speed_factor, safe, per, net, state["targets"]
            )
        slacks = [tok[1][3] for vid in per for tok in obs[vid]] or [0.0]
        obs["_state"] = [
            math.log(1 + len(safe)),
            float(len(gates)),
            t / 300.0,
            speed_factor,
            float(len(per)),
            max(slacks) / 60.0,
            sum(slacks) / len(slacks) / 60.0,
        ]
        action = policy(obs)
        commands = {}
        for vid, choice in action.items():
            if choice == HOLD or vid not in per:
                continue
            if choice == CHASE or not obs[vid]:
                commands[vid] = ("seg", e_pos[0], None)
                state["targets"].pop(vid, None)
                continue
            g = obs[vid][choice][0]
            edge = _edge_into(g, per[vid][1], per[vid][2], net)
            commands[vid] = ("seg", edge, None) if edge else ("seg", e_pos[0], None)
            state["targets"][vid] = g
        ep.transitions.append(Transition(t, obs, dict(action), 0.0))
        return commands

    def stop_when(t):
        if reward_mode == "trap":
            return ep.trapped_at is not None
        return ep.caged_at is not None and t >= ep.caged_at + PERSIST_S + post_cage_s - 1e-9

    run = run_plan(
        net,
        net_file,
        scenario,
        Plan(),
        domain,
        sumo_binary,
        sigma=sigma,
        seed=seed,
        label=label,
        controller=controller,
        evader_speed_factor=speed_factor,
        stop_when=stop_when,
        stop_on_capture=False,
        admission=True,
        extra_sumo_args=extra_sumo_args,
        pursuer_speed_factor=pursuer_speed_factor,
    )
    if ep.transitions:
        ep.transitions[-1].reward += state["pending_r"]
    ep.collision_events = [dict(c) for c in run.collisions]
    if run.collisions:
        ep.collided = True
        if ep.transitions:
            ep.transitions[-1].reward -= 1.0
    last = {}
    for f in run.trace:
        for vid, v in f.vehicles.items():
            if vid in last and last[vid] - v.speed_mps > 0.7:
                ep.emergencies += 1
            last[vid] = v.speed_mps
    ep.contact_capture = run.verdict.verdict.value == "SUPPORTED"
    ep.evader_exited = bool(run.trace) and "e1" not in run.trace[-1].vehicles
    ep.end_s = run.trace[-1].time_s if run.trace else 0.0
    if keep_trace:
        ep.trace = run.trace
        ep.refused = run.refused  # A-94 diagnostics
        ep.events = run.events
    return ep


def _immobile(conn, speed, pursuers) -> bool:
    """A-84: stopped behind a pursuer leader, not waiting at a red/yellow signal."""
    if speed > TRAP_STOP_MPS:
        return False
    try:
        leader = conn.vehicle.getLeader("e1", 60.0)
        if not leader or leader[0] not in pursuers or leader[1] > TRAP_GAP_M:
            return False
        tls = conn.vehicle.getNextTLS("e1")
    except Exception:  # noqa: BLE001 - evader momentarily off-road
        return False
    return not (tls and tls[0][2] <= TRAP_SIGNAL_M and tls[0][3] in "rRyYu")


def random_policy(rng):
    def policy(obs):
        out = {}
        for vid, tokens in obs.items():
            if vid.startswith("_"):
                continue
            out[vid] = rng.randrange(len(tokens)) if tokens and rng.random() < 0.8 else CHASE
        return out

    return policy


def cut_policy():
    """The cut heuristic expressed through the arm-T interface (for plumbing checks and BC)."""
    assigned: dict[str, str] = {}

    def policy(obs):
        pursuers = sorted(v for v in obs if not v.startswith("_"))
        out, taken = {}, set()
        # keep a still-valid previous gate (hysteresis), then greedy by urgency and own time
        for vid in pursuers:
            names = [g for g, _ in obs[vid]]
            if assigned.get(vid) in names and assigned[vid] not in taken:
                idx = names.index(assigned[vid])
                if obs[vid][idx][1][2] <= obs[vid][idx][1][0]:
                    out[vid] = HOLD
                    taken.add(assigned[vid])
        gates = [g for g, _ in obs[pursuers[0]]] if pursuers and obs[pursuers[0]] else []
        for g in gates:
            if g in taken:
                continue
            free = [v for v in pursuers if v not in out]
            if not free:
                break
            vid = min(free, key=lambda v: (dict(obs[v])[g][2], v))
            out[vid] = [x for x, _ in obs[vid]].index(g)
            assigned[vid] = g
            taken.add(g)
        for vid in pursuers:
            out.setdefault(vid, CHASE)
        return out

    return policy


def cut_label(obs):
    """The cut heuristic as a STATELESS function of the arm-T tokens (A-80), for BC/DAgger labels:
    keep my current target if it is still a gate I can take first (feature `own_target`), then
    assign the remaining gates by urgency to the fastest free pursuer. Returns token indices (the
    kept target as its index, not HOLD, so the label is a function of what the learner sees)."""
    pursuers = sorted(v for v in obs if not v.startswith("_"))
    out, taken = {}, set()
    for vid in pursuers:
        for i, (g, f) in enumerate(obs[vid]):
            if f[6] > 0.5 and g not in taken and f[2] <= f[0]:
                out[vid] = i
                taken.add(g)
                break
    gates = [g for g, _ in obs[pursuers[0]]] if pursuers and obs[pursuers[0]] else []
    for g in gates:
        if g in taken:
            continue
        free = [v for v in pursuers if v not in out]
        if not free:
            break
        vid = min(free, key=lambda v: (dict(obs[v])[g][2], v))
        out[vid] = [x for x, _ in obs[vid]].index(g)
        taken.add(g)
    for vid in pursuers:
        out.setdefault(vid, CHASE)
    return out
