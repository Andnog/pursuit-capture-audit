"""Junction ambush planner (A-94): cooperative "hammer and anvil" with lane-level blocking.

At every controller step the planner predicts the evader's next junctions (greedy on the evader's
lead over the nearest pursuer, the quantity an avoiding evader maximises) and looks, nearest first,
for a junction J on that path where the team can occupy EVERY passenger lane of EVERY exit of J
before the evader reaches J. Blockers are sent to stop a few metres into those exits, in the lane
they are assigned (the evader, whichever exit it takes, then stops behind a pursuer). Pursuers
not needed as blockers keep chasing (drive to the end of the evader's edge) so the evader keeps
moving into the ambush. With no feasible junction every pursuer chases (= the pursuit baseline).

The plan is kept while J stays ahead on the predicted path, so blockers are not re-routed every
second. The planner knows the evader's general behaviour (it flees the nearest pursuer), not its
random draws.
"""

from __future__ import annotations

import itertools
import math

DEPTH = 4
MARGIN_S = 2.0
HOLD_M = 12.0
# Pursuer travel-time model: free-flow time is optimistic (start-up, yielding, signals). The first
# development check had every ambush late (0 of 21 junctions closed in time).
SLOW = 1.3
STARTUP_S = 3.0


class AmbushPlanner:
    def __init__(self, depth: int = DEPTH, margin_s: float = MARGIN_S, hold_m: float = HOLD_M):
        self.depth, self.margin_s, self.hold_m = depth, margin_s, hold_m
        self.plan: dict | None = (
            None  # {"junction", "arrival", "blockers": {vid: (edge, lane, hold)}}
        )
        self._lanes: dict[str, list[int]] = {}
        self.stats = {"plans": 0, "steps_with_plan": 0, "steps": 0}
        self.history: list[dict] = []  # diagnostics: one entry per step with a plan

    def _lanes_of(self, snet, edge):
        if edge not in self._lanes:
            self._lanes[edge] = [
                ln.getIndex() for ln in snet.getEdge(edge).getLanes() if ln.allows("passenger")
            ]
        return self._lanes[edge]

    def _predict(self, ctx):
        """[(arrival_edge, junction, evader_time_at_junction)] for the next `depth` junctions."""
        net, reach, per = ctx["net"], ctx["reach"], ctx["per"]
        edge, offset = ctx["e_pos"]
        sf = ctx["speed_factor"]
        info = net.edges[edge]
        t = max(0.0, info.length_m - offset) / (info.speed_cap_mps * sf)
        path, seen = [], {edge}
        for _ in range(self.depth):
            j = net.edges[edge].to_node
            path.append((edge, j, t))
            best, best_score, best_t = None, -math.inf, None
            for s in sorted(reach.succ.get(edge, ())):
                link = net.links[(edge, s)]
                ts = t + link.via_length_m / max(link.via_speed_mps * sf, 0.1)
                ts += net.edges[s].length_m / (net.edges[s].speed_cap_mps * sf)
                n = net.edges[s].to_node
                lead = min((p[0].get(n, math.inf) for p in per.values()), default=math.inf) - ts
                if lead > best_score:
                    best, best_score, best_t = s, lead, ts
            if best is None or best in seen:
                break
            seen.add(best)
            edge, t = best, best_t
        return path

    def _assign(self, ctx, arrival, junction, t_evader):
        net, reach, per, snet = ctx["net"], ctx["reach"], ctx["per"], ctx["snet"]
        lanes = [
            (s, idx) for s in sorted(reach.succ.get(arrival, ())) for idx in self._lanes_of(snet, s)
        ]
        pursuers = sorted(per)
        if not lanes or len(lanes) > len(pursuers):
            return None
        cost = {}
        for v in pursuers:
            pos = ctx["p_pos"][v]
            for s, idx in lanes:
                info = net.edges[s]
                hold = min(self.hold_m, 0.5 * info.length_m)
                if pos[0] == s:  # already on the exit: stop a little ahead of where it is
                    if pos[1] + 6.0 >= info.length_m - 1.0:
                        cost[(v, s, idx)] = (math.inf, hold)
                        continue
                    cost[(v, s, idx)] = (0.0, max(hold, pos[1] + 6.0))
                    continue
                d = per[v][1].get(s)
                if d is None:
                    cost[(v, s, idx)] = (math.inf, hold)
                    continue
                free = d - (info.length_m - hold) / info.speed_cap_mps
                cost[(v, s, idx)] = (SLOW * free + STARTUP_S, hold)
        best, best_slack = None, -math.inf
        for chosen in itertools.permutations(pursuers, len(lanes)):
            slack = min(
                t_evader - cost[(v, s, i)][0] for v, (s, i) in zip(chosen, lanes, strict=True)
            )
            if slack > best_slack:
                best_slack, best = slack, chosen
        if best is None or best_slack < self.margin_s:
            return None
        return {v: (s, i, cost[(v, s, i)][1]) for v, (s, i) in zip(best, lanes, strict=True)}

    def _late(self, ctx, path, key):
        """True if some blocker not yet stopped on its exit can no longer beat the evader."""
        t_ev = next(t for a, j, t in path if (a, j) == key)
        states, net = ctx["states"], ctx["net"]
        for v, (s, _i, hold) in self.plan["blockers"].items():
            st = states.get(v)
            if st is None or v not in ctx["per"]:
                return True
            if st[0] == s and st[3] <= 1.0:
                continue  # in place
            if st[0] == s:
                remaining = max(0.0, hold - ctx["p_pos"][v][1]) / net.edges[s].speed_cap_mps
                if SLOW * remaining > t_ev:
                    return True
                continue
            d = ctx["per"][v][1].get(s)
            if d is None:
                return True
            free = d - (net.edges[s].length_m - hold) / net.edges[s].speed_cap_mps
            if SLOW * free + 1.0 > t_ev:
                return True
        return False

    def __call__(self, ctx):
        self.stats["steps"] += 1
        path = self._predict(ctx)
        ahead = {(a, j) for a, j, _ in path}
        e_edge = ctx["e_pos"][0]
        if self.plan is not None:
            exits = {b[0] for b in self.plan["blockers"].values()}
            on_exit = e_edge in exits
            key = (self.plan["arrival"], self.plan["junction"])
            if not on_exit and key not in ahead or not on_exit and self._late(ctx, path, key):
                self.plan = None
        if self.plan is None:
            for arrival, junction, t_ev in path:
                blockers = self._assign(ctx, arrival, junction, t_ev)
                if blockers is not None:
                    self.plan = {"arrival": arrival, "junction": junction, "blockers": blockers}
                    self.stats["plans"] += 1
                    break
        commands = {}
        blockers = self.plan["blockers"] if self.plan else {}
        # A blocker already on its exit must stop beyond its braking distance, or the legal
        # admission interface refuses the order ("stop too close") and it drives on. Fixed once,
        # so the command stays identical from step to step.
        for v, (s, i, hold) in list(blockers.items()):
            st = ctx["states"].get(v)
            if st is None or st[0] != s or v not in ctx["p_pos"]:
                continue
            speed, pos = st[3], ctx["p_pos"][v][1]
            brake = speed * speed / (2 * 4.5) + speed * 0.1 + 5.0 + 1.0
            if pos + 1.0 > hold:  # only when it is already past its stop point
                length = ctx["net"].edges[s].length_m
                blockers[v] = (s, i, min(pos + brake + 2.0, length - 0.6))
        if blockers:
            self.stats["steps_with_plan"] += 1
            states = ctx["states"]
            self.history.append(
                {
                    "t": ctx["t"],
                    "junction": self.plan["junction"],
                    "arrival": self.plan["arrival"],
                    "evader_edge": e_edge,
                    "blockers": {
                        v: (
                            b[0],
                            b[1],
                            states[v][0] if v in states else None,
                            round(states[v][3], 1) if v in states else None,
                        )
                        for v, b in blockers.items()
                    },
                }
            )
        for v in ctx["per"]:
            if v in blockers:
                s, i, hold = blockers[v]
                commands[v] = ("seg", s, hold, i)
            else:
                commands[v] = ("seg", e_edge, None)
        return commands
