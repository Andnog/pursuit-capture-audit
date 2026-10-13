"""Multi-agent ambush controller, version 3 (A-133): corrected critic input and sampling.

Differences from `mappo_ambush_v2.MappoAmbushV2`, which is kept unchanged:
- the global state recorded for the critic is built BEFORE any agent of the decision step has
  chosen. Its coverage features describe the targets held from the previous step, so the value
  used as a baseline does not depend on the actions it is compared with (review finding F4-1);
- sampling uses the controller's own generator, seeded per episode (`act_seeded`), and nothing
  global (F4-2);
- the post-decision vector of v1/v2 is still recorded, as "global_post", for diagnostics only.

Unchanged and now stated explicitly (F4-5): the shared actor is SEQUENTIAL. Agents decide in sorted
id order within a step, and the targets chosen earlier in the step are visible to the agents that
follow. The joint log-probability of a step is the sum of these conditional log-probabilities, and
a baseline that depends only on the state before the step leaves the policy gradient unbiased.
"""

from __future__ import annotations

import math

import numpy as np

from .ambush_plus import AmbushPlusPlanner
from .mappo_ambush import DECIDE_S
from .mappo_ambush_v2 import MappoAmbushV2


class MappoAmbushV3(MappoAmbushV2):
    def _distance(self, ctx, v):
        try:
            ex, ey = ctx["conn"].vehicle.getPosition("e1")
            px, py = ctx["conn"].vehicle.getPosition(v)
            return math.dist((ex, ey), (px, py))
        except Exception:  # noqa: BLE001
            return 300.0

    def _global(self, ctx, slots, agents, dists):
        return np.array(
            [
                len(agents) / 7,
                ctx["t"] / 300,
                ctx["states"]["e1"][3] / 15,
                self._coverage(ctx, slots, 0),
                self._coverage(ctx, slots, 1),
                min(min(dists, default=300.0) / 300, 3.0),
                min(sum(dists) / max(1, len(dists)) / 300, 3.0),
            ],
            dtype=np.float32,
        )

    def __call__(self, ctx):
        from ..rl.mappo_policy import act_seeded

        self.stats["steps"] += 1
        t = ctx["t"]
        if t - self.last_t >= DECIDE_S:
            self.last_t = t
            path = self._predict(ctx)
            slots = self._slots(ctx, path)
            agents = sorted(ctx["per"])
            slack = {(v, i): self._slack(ctx, v, sl) for v in agents for i, sl in enumerate(slots)}
            # The critic's state: recorded here, before any target of this step is written.
            g_pre = self._global(ctx, slots, agents, [self._distance(ctx, v) for v in agents])
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
                        choice, logp = act_seeded(self.model, toks, actx, self.mode, self.rng)
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
            self.ticks.append(
                {
                    "global": g_pre,
                    "global_post": self._global(ctx, slots, agents, dists),
                    "agents": records,
                    "t": t,
                }
            )
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


__all__ = ["MappoAmbushV3"]
