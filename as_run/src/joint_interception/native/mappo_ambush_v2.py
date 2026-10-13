"""Multi-agent ambush controller, version 2 (A-116).

Differences from `mappo_ambush.MappoAmbush` (A-103), which is kept unchanged:
- a faithful teacher: a planner block whose lane is not among the slot tokens is still executed,
  and is labelled -1 (excluded from imitation) instead of being turned into CHASE;
- a larger slot cap (40), so that fewer planner blocks fall outside the token list;
- counters of represented / unrepresentable teacher blocks.
"""

from __future__ import annotations

import math

import numpy as np

from .ambush_plus import AmbushPlusPlanner
from .mappo_ambush import DECIDE_S, DEPTH, MappoAmbush

MAX_SLOTS_V2 = 40


class MappoAmbushV2(MappoAmbush):
    def __init__(self, params, model=None, mode="teacher", seed=0):
        super().__init__(params, model, mode, seed)
        self.represented = 0
        self.unrepresentable = 0

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
        return slots[:MAX_SLOTS_V2]

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
                        if idx:
                            label = 2 + idx[0]
                            self.represented += 1
                        else:
                            label = -1  # executed, but not imitable
                            self.unrepresentable += 1
                        self.targets[v], self.orders[v] = key, cmd
                    else:
                        self.targets[v], self.orders[v] = None, ("seg", ctx["e_pos"][0], None)
                    choice, logp = label, 0.0
                else:
                    if self.mode == "random" or self.model is None:
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


__all__ = ["MAX_SLOTS_V2", "MappoAmbushV2", "math"]
