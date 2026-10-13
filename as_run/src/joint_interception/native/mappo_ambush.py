"""Multi-agent ambush controller for MAPPO (A-103).

Every DECIDE_S seconds each pursuer (agent) chooses one of its tokens:
- a blocking SLOT: one passenger lane of one exit of one of the next `depth` junctions on the
  evader's predicted path (it drives there and stops HOLD m into the lane);
- CHASE: drive to the end of the evader's current edge;
- STAY: keep its current order.
Agents share one actor and decide SEQUENTIALLY, in sorted id order, within a decision step: the
targets chosen earlier in the step are visible to the agents that follow ("teammates_targeting",
"coverage_next"). This is not simultaneous decentralised execution. The global state of a step is
built after all agents have chosen. (Documentation corrected in A-133; the code is unchanged. The
fourth review showed that this global state must not be used as a critic baseline: see
`mappo_ambush_v3.py`.)

Modes: "teacher" executes the optimised A-99 planner (`AmbushPlusPlanner` with its parameters) and
records, for each agent, the slot the planner chose as a behaviour-cloning label; "sample",
"greedy" and "random" execute the actor (or a uniform choice). Records per agent decision:
tokens, agent context, chosen index, log-prob, teacher index; per tick: global state.
"""

from __future__ import annotations

import math
import random

import numpy as np

from .ambush_plus import AmbushPlusPlanner

DECIDE_S = 3.0
DEPTH = 4
MAX_SLOTS = 18


class MappoAmbush(AmbushPlusPlanner):
    def __init__(self, params, model=None, mode="teacher", seed=0):
        super().__init__(params)
        self.model, self.mode = model, mode
        self.rng = random.Random(seed)
        self.targets: dict[str, tuple | None] = {}  # vid -> (edge, lane) or None (chase)
        self.orders: dict[str, tuple] = {}
        self.last_t = -math.inf
        self.ticks: list[dict] = []  # {"global": np.array, "agents": [record, ...]}

    # -- features ---------------------------------------------------------------------------
    def _slots(self, ctx, path):
        snet = ctx["snet"]
        slots = []
        for k, (arrival, junction, t_ev) in enumerate(path[:DEPTH]):
            exits = self._exit_order(ctx, arrival, t_ev)
            total = sum(len(self._lanes_of(snet, s)) for s in exits)
            for rank, s in enumerate(exits):
                for lane in self._lanes_of(snet, s):
                    slots.append(
                        {
                            "edge": s,
                            "lane": lane,
                            "k": k,
                            "rank": rank,
                            "t_ev": t_ev,
                            "junction_lanes": total,
                            "n_exits": len(exits),
                            "junction": junction,
                        }
                    )
        return slots[:MAX_SLOTS]

    def _slack(self, ctx, v, slot):
        hold = min(self.p["hold_m"], 0.5 * ctx["net"].edges[slot["edge"]].length_m)
        c, _ = self._cost(ctx, v, slot["edge"], hold)
        return slot["t_ev"] - c if math.isfinite(c) else -60.0

    def _agent_inputs(self, ctx, v, slots, slack):
        clip = lambda x: max(-1.0, min(2.0, x / 20.0))  # noqa: E731
        others = [u for u in ctx["per"] if u != v]
        mine = self.targets.get(v)
        st = ctx["states"].get(v)
        toks = []
        # CHASE, STAY
        toks.append([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, float(mine is None), 0])
        toks.append([0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1.0, 0])
        for i, sl in enumerate(slots):
            key = (sl["edge"], sl["lane"])
            best_o = max((slack[(u, i)] for u in others), default=-60.0)
            n_tgt = sum(1 for u in others if self.targets.get(u) == key)
            in_place = float(st is not None and st[0] == sl["edge"] and st[3] <= 1.0)
            toks.append(
                [
                    0,
                    0,
                    sl["k"] / 4,
                    sl["rank"] / 3,
                    sl["lane"] / 3,
                    clip(slack[(v, i)]),
                    clip(best_o),
                    n_tgt / max(1, len(others)),
                    sl["junction_lanes"] / 6,
                    sl["n_exits"] / 4,
                    float(mine == key),
                    in_place,
                ]
            )
        try:
            ex, ey = ctx["conn"].vehicle.getPosition("e1")
            px, py = ctx["conn"].vehicle.getPosition(v)
            dist = math.dist((ex, ey), (px, py))
        except Exception:  # noqa: BLE001
            dist = 300.0
        cov = self._coverage(ctx, slots, k=0)
        actx = [
            len(ctx["per"]) / 7,
            ctx["t"] / 300,
            ctx["states"]["e1"][3] / 15,
            (st[3] if st else 0.0) / 15,
            min(dist / 300, 3.0),
            cov,
            float(mine is not None),
        ]
        return np.array(toks, dtype=np.float32), np.array(actx, dtype=np.float32), dist

    def _coverage(self, ctx, slots, k):
        lanes = [(s["edge"], s["lane"]) for s in slots if s["k"] == k]
        if not lanes:
            return 0.0
        held = {t for t in self.targets.values() if t is not None}
        return sum(1 for x in lanes if x in held) / len(lanes)

    # -- control ----------------------------------------------------------------------------
    def __call__(self, ctx):
        from ..rl.mappo_policy import act

        self.stats["steps"] += 1
        t = ctx["t"]
        if t - self.last_t >= DECIDE_S:
            self.last_t = t
            path = self._predict(ctx)
            slots = self._slots(ctx, path)
            agents = sorted(ctx["per"])
            slack = {(v, i): self._slack(ctx, v, sl) for v in agents for i, sl in enumerate(slots)}
            teacher_cmds = None
            if self.mode == "teacher":
                teacher_cmds = AmbushPlusPlanner.__call__(self, ctx)
            records, dists = [], []
            for v in agents:
                toks, actx, dist = self._agent_inputs(ctx, v, slots, slack)
                dists.append(dist)
                label = 0
                if teacher_cmds is not None:
                    cmd = teacher_cmds.get(v)
                    if cmd is not None and len(cmd) > 3:
                        key = (cmd[1], cmd[3])
                        idx = [i for i, sl in enumerate(slots) if (sl["edge"], sl["lane"]) == key]
                        label = 2 + idx[0] if idx else 0
                    if label >= 2:
                        self.targets[v] = (slots[label - 2]["edge"], slots[label - 2]["lane"])
                        self.orders[v] = cmd
                    else:
                        self.targets[v], self.orders[v] = None, ("seg", ctx["e_pos"][0], None)
                    choice, logp = label, 0.0
                else:
                    if self.mode == "random" or self.model is None:  # uniform control, no network
                        choice, logp = self.rng.randrange(len(toks)), 0.0
                    else:
                        choice, logp = act(self.model, toks, actx, self.mode, self.rng)
                    if choice == 0:
                        self.targets[v], self.orders[v] = None, ("seg", ctx["e_pos"][0], None)
                    elif choice >= 2:
                        sl = slots[choice - 2]
                        hold = min(self.p["hold_m"], 0.5 * ctx["net"].edges[sl["edge"]].length_m)
                        self.targets[v] = (sl["edge"], sl["lane"])
                        self.orders[v] = ("seg", sl["edge"], hold, sl["lane"])
                records.append(
                    {
                        "vid": v,
                        "tokens": toks,
                        "ctx": actx,
                        "idx": choice,
                        "teacher_idx": label,
                        "logp": logp,
                    }
                )
            g = np.array(
                [
                    len(agents) / 7,
                    t / 300,
                    ctx["states"]["e1"][3] / 15,
                    self._coverage(ctx, slots, 0),
                    self._coverage(ctx, slots, 1),
                    min(min(dists, default=300.0) / 300, 3.0),
                    min(sum(dists) / max(1, len(dists)) / 300, 3.0),
                ],
                dtype=np.float32,
            )
            self.ticks.append({"global": g, "agents": records, "t": t})
        commands = {}
        for v in ctx["per"]:
            order = self.orders.get(v)
            if order is None or self.targets.get(v) is None:
                commands[v] = ("seg", ctx["e_pos"][0], None)
                continue
            s, hold, lane = order[1], order[2], order[3]
            st = ctx["states"].get(v)
            if (
                st is not None
                and st[0] == s
                and v in ctx["p_pos"]
                and ctx["p_pos"][v][1] + 1.0 > hold
            ):
                spd = st[3]
                hold = min(
                    ctx["p_pos"][v][1] + spd * spd / 9.0 + spd * 0.1 + 8.0,
                    ctx["net"].edges[s].length_m - 0.6,
                )
                self.orders[v] = ("seg", s, hold, lane)
            commands[v] = ("seg", s, hold, lane)
        return commands
