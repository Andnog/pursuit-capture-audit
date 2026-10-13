"""Ambush with pre-positioning (A-98): the A-94 planner plus forward interceptors, parameterised.

The ambush planner chases with every pursuer it does not need as a blocker, so most of the time the
team trails the evader and a full lane-level ambush is rarely feasible (8-18 % of steps, A-95).
This planner keeps `chasers` pursuers chasing (the hammer) and sends the others ahead to wait in
the lanes of the exits the evader is predicted to take at junctions `pre_k_min..pre_k_max` steps
ahead, whenever they can get there `pre_margin` seconds before the evader (the anvils). When the
evader approaches a junction where the team can close every lane, the full ambush of A-94 takes
over. All parameters are exposed for gradient-free optimisation.
"""

from __future__ import annotations

import math

from .ambush import AmbushPlanner

DEFAULTS = {
    "depth": 4,  # junctions searched for a full ambush
    "margin_s": 2.0,  # required slack for a full ambush
    "slow": 1.3,  # pursuer travel-time inflation
    "startup_s": 3.0,
    "hold_m": 12.0,  # stop distance into the exit
    "chasers": 1,  # pursuers that keep chasing when no full ambush is active
    "pre_k_min": 2,  # pre-positioning targets: junctions ahead on the predicted path
    "pre_k_max": 5,
    "pre_margin": 1.0,  # required slack for a pre-positioning target
    "prepos_during_plan": 1,  # non-blockers pre-position (1) or chase (0) during an ambush
    # A-100: how the evader's next turns are predicted. "greedy": its lead over the nearest
    # pursuer (A-94). "oracle": a copy of the evader's own decision function with its seed (an
    # upper bound on what better opponent modelling could give; not a deployable method).
    # "model": a learned turn predictor (callable) passed as `turn_model`.
    "predictor": "greedy",
    # A-106: commitment. Re-plan blockers and pre-positioned pursuers only every `commit_s` seconds
    # and hold their lane orders in between (chasers still follow the evader every step). 1.0 =
    # re-plan at every controller step (the A-99 planner).
    "commit_s": 1.0,
    # A-121: coordination ablation. 1 = no joint assignment: no full (team) ambush, and each pursuer
    # chooses its pre-positioning lane as if alone (lanes chosen by teammates are not excluded).
    # Same prediction, same information and the same per-pursuer rule. 0 = the A-99 planner.
    "independent": 0,
}


class AmbushPlusPlanner(AmbushPlanner):
    def __init__(self, params: dict | None = None, turn_model=None):
        p = dict(DEFAULTS)
        p.update(params or {})
        p["pre_k_max"] = max(int(p["pre_k_max"]), int(p["pre_k_min"]))
        super().__init__(
            depth=int(max(p["depth"], p["pre_k_max"])), margin_s=p["margin_s"], hold_m=p["hold_m"]
        )
        self.p = p
        self.ambush_depth = int(p["depth"])
        self.pre: dict[str, tuple] = {}  # vid -> (exit edge, lane, hold, junction)
        self.stats.update({"steps_prepositioned": 0, "pred_hits": 0, "pred_total": 0})
        self.turn_model = turn_model
        self._clone = None
        self._last_edge = None
        self._last_pred = None
        self._pending_preds: list = []
        self.lead_log: list = []

    # -- prediction -------------------------------------------------------------------------
    def _pursuer_inputs(self, ctx):
        """Pursuer nodes and positions exactly as the engine gives them to the evader."""
        net, states, conn = ctx["net"], ctx["states"], ctx["conn"]
        nodes, positions = {}, {}
        for pid in sorted(ctx["per"]):
            ps = states.get(pid)
            if ps is None:
                continue
            if ps[0].startswith(":"):
                route = conn.vehicle.getRoute(pid)
                idx = conn.vehicle.getRouteIndex(pid)
                node = net.edges[route[min(idx + 1, len(route) - 1)]].from_node
                nodes[pid], positions[pid] = node, (node, node, 0.0)
            elif ps[0] in net.edges:
                info = net.edges[ps[0]]
                lane_len = conn.lane.getLength(ps[1]) if ps[1] else info.length_m
                nodes[pid] = info.to_node
                positions[pid] = (
                    info.from_node,
                    info.to_node,
                    min(1.0, ps[2] / max(lane_len, 1e-6)),
                )
        return nodes, positions

    def _predict(self, ctx):
        mode = self.p.get("predictor", "greedy")
        if mode == "oracle" and ctx.get("evader") is not None:
            path = self._predict_chain(ctx, self._oracle_choice)
        elif mode == "model" and self.turn_model is not None:
            path = self._predict_chain(ctx, self._model_choice)
        else:
            path = super()._predict(ctx)
        e_edge = ctx["e_pos"][0]
        if self._last_edge is not None and e_edge != self._last_edge and self._last_pred:
            self.stats["pred_total"] += 1
            self.stats["pred_hits"] += int(e_edge == self._last_pred)
            # diagnostics: hit/miss of every prediction made on the previous edge, by lead time
            for lead, pred in self._pending_preds:
                self.lead_log.append((round(lead, 1), int(pred == e_edge)))
            self._pending_preds = []
        if e_edge != self._last_edge:
            self._pending_preds = []
        self._last_edge = e_edge
        self._last_pred = path[1][0] if len(path) > 1 else None
        if len(path) > 1:
            self._pending_preds.append((path[0][2], path[1][0]))
        return path

    def _predict_chain(self, ctx, choose):
        net, sf = ctx["net"], ctx["speed_factor"]
        nodes, positions = self._pursuer_inputs(ctx)
        edge, offset = ctx["e_pos"]
        info = net.edges[edge]
        t = max(0.0, info.length_m - offset) / (info.speed_cap_mps * sf)
        path, seen = [], {edge}
        committed = None
        if choose == self._oracle_choice:
            # Once the evader has decided its next edge, SUMO holds it in its route (oracle only).
            try:
                route = ctx["conn"].vehicle.getRoute("e1")
                ridx = ctx["conn"].vehicle.getRouteIndex("e1")
                if route[ridx] == edge and ridx + 1 < len(route):
                    committed = route[ridx + 1]
            except Exception:  # noqa: BLE001
                committed = None
        for k in range(self.depth):
            path.append((edge, net.edges[edge].to_node, t))
            nxt = committed if (k == 0 and committed) else choose(ctx, edge, t, nodes, positions)
            if nxt is None or nxt in seen or (edge, nxt) not in net.links:
                break
            link = net.links[(edge, nxt)]
            t += link.via_length_m / max(link.via_speed_mps * sf, 0.1)
            t += net.edges[nxt].length_m / (net.edges[nxt].speed_cap_mps * sf)
            seen.add(nxt)
            edge = nxt
        return path

    def _oracle_choice(self, ctx, edge, t_to_end, nodes, positions):
        from ..simulator.evader import ScriptedEvader

        ev = ctx["evader"]
        if self._clone is None:
            self._clone = ScriptedEvader(ev.level, ev.seed, ev.topology, input_mode=ev.input_mode)
        t_dec = ctx["t"] + max(0.0, t_to_end - 1.5)  # the evader decides ~1.5 s before the end
        dec = self._clone.choose(int(round(t_dec / ctx["decision_s"])), edge, nodes, positions)
        self._clone.decisions.clear()
        return dec.chosen

    def _model_choice(self, ctx, edge, t_to_end, nodes, positions):
        return self.turn_model(ctx, edge, t_to_end, nodes, positions)

    # travel cost with the optimisable time model
    def _cost(self, ctx, v, s, hold):
        net = ctx["net"]
        info = net.edges[s]
        pos = ctx["p_pos"][v]
        if pos[0] == s:
            if pos[1] + 6.0 >= info.length_m - 1.0:
                return math.inf, hold
            return 0.0, max(hold, pos[1] + 6.0)
        d = ctx["per"][v][1].get(s)
        if d is None:
            return math.inf, hold
        free = d - (info.length_m - hold) / info.speed_cap_mps
        return self.p["slow"] * free + self.p["startup_s"], hold

    def _assign(self, ctx, arrival, junction, t_evader):
        # Same as A-94 but with the optimisable time model.
        import itertools

        net, reach, snet = ctx["net"], ctx["reach"], ctx["snet"]
        lanes = [
            (s, i) for s in sorted(reach.succ.get(arrival, ())) for i in self._lanes_of(snet, s)
        ]
        pursuers = sorted(ctx["per"])
        if not lanes or len(lanes) > len(pursuers):
            return None
        cost = {}
        for v in pursuers:
            for s, i in lanes:
                hold = min(self.p["hold_m"], 0.5 * net.edges[s].length_m)
                cost[(v, s, i)] = self._cost(ctx, v, s, hold)
        best, best_slack = None, -math.inf
        if len(pursuers) > 5:  # greedy (hardest lane first) instead of all permutations
            chosen, free = [], set(pursuers)
            order = sorted(lanes, key=lambda li: -min(cost[(v, *li)][0] for v in pursuers))
            pick = {}
            for li in order:
                v = min(free, key=lambda u: (cost[(u, *li)][0], u))
                pick[li] = v
                free.discard(v)
            chosen = tuple(pick[li] for li in lanes)
            best_slack = min(
                t_evader - cost[(v, s, i)][0] for v, (s, i) in zip(chosen, lanes, strict=True)
            )
            best = chosen
            if best_slack < self.p["margin_s"]:
                return None
            return {v: (s, i, cost[(v, s, i)][1]) for v, (s, i) in zip(best, lanes, strict=True)}
        for chosen in itertools.permutations(pursuers, len(lanes)):
            slack = min(
                t_evader - cost[(v, s, i)][0] for v, (s, i) in zip(chosen, lanes, strict=True)
            )
            if slack > best_slack:
                best_slack, best = slack, chosen
        if best is None or best_slack < self.p["margin_s"]:
            return None
        return {v: (s, i, cost[(v, s, i)][1]) for v, (s, i) in zip(best, lanes, strict=True)}

    def _exit_order(self, ctx, arrival, t_arrival):
        net, reach, per = ctx["net"], ctx["reach"], ctx["per"]
        sf = ctx["speed_factor"]
        scored = []
        for s in sorted(reach.succ.get(arrival, ())):
            link = net.links[(arrival, s)]
            ts = t_arrival + link.via_length_m / max(link.via_speed_mps * sf, 0.1)
            ts += net.edges[s].length_m / (net.edges[s].speed_cap_mps * sf)
            n = net.edges[s].to_node
            lead = min((q[0].get(n, math.inf) for q in per.values()), default=math.inf) - ts
            scored.append((-lead, s))
        return [s for _, s in sorted(scored)]

    def _chasers(self, ctx, free):
        """The `chasers` free pursuers closest (in time) to the evader's current edge end."""
        e_edge = ctx["e_pos"][0]
        ranked = sorted(free, key=lambda v: (ctx["per"][v][1].get(e_edge, math.inf), v))
        return set(ranked[: int(self.p["chasers"])])

    def _preposition(self, ctx, path, free):
        """Greedy: each free pursuer to the most useful lane it can reach in time."""
        net, snet = ctx["net"], ctx["snet"]
        kmin, kmax = int(self.p["pre_k_min"]), int(self.p["pre_k_max"])
        ahead = {j for _, j, _ in path}
        # keep valid previous targets
        out = {}
        for v, tgt in list(self.pre.items()):
            if v in free and tgt[3] in ahead:
                out[v] = tgt
        taken = {(t[0], t[1]) for t in out.values()}
        cands = []
        for k, (arrival, junction, t_ev) in enumerate(path):
            if k + 1 < kmin or k + 1 > kmax:
                continue
            for rank, s in enumerate(self._exit_order(ctx, arrival, t_ev)):
                for i in self._lanes_of(snet, s):
                    cands.append((k, rank, s, i, junction, t_ev))
        for v in sorted(free):
            if v in out:
                continue
            best, best_key = None, None
            for k, rank, s, i, junction, t_ev in cands:
                if (s, i) in taken and not self.p.get("independent", 0):
                    continue
                hold = min(self.p["hold_m"], 0.5 * net.edges[s].length_m)
                c, h = self._cost(ctx, v, s, hold)
                slack = t_ev - c
                if slack < self.p["pre_margin"]:
                    continue
                key = (rank, k, -slack)  # predicted exit first, then nearer junction
                if best_key is None or key < best_key:
                    best, best_key = (s, i, h, junction), key
            if best is not None:
                out[v] = best
                taken.add((best[0], best[1]))
        self.pre = out
        return out

    def __call__(self, ctx):
        commit = float(self.p.get("commit_s", 1.0))
        if commit > 1.0:
            t = ctx["t"]
            if getattr(self, "_held", None) is not None and t - self._held_t < commit - 1e-6:
                return self._held_commands(ctx)
            cmds = self._plan_step(ctx)
            self._held = {v: c for v, c in cmds.items() if len(c) > 3}
            self._held_t = t
            return cmds
        return self._plan_step(ctx)

    def _held_commands(self, ctx):
        self.stats["steps"] += 1
        out = {}
        for v in ctx["per"]:
            c = self._held.get(v)
            if c is None:
                out[v] = ("seg", ctx["e_pos"][0], None)
                continue
            s, hold, lane = c[1], c[2], c[3]
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
                self._held[v] = ("seg", s, hold, lane)
            out[v] = ("seg", s, hold, lane)
        return out

    def _plan_step(self, ctx):
        self.stats["steps"] += 1
        path = self._predict(ctx)
        amb_path = path[: self.ambush_depth]
        ahead = {(a, j) for a, j, _ in path}
        e_edge = ctx["e_pos"][0]
        if self.plan is not None:
            exits = {b[0] for b in self.plan["blockers"].values()}
            key = (self.plan["arrival"], self.plan["junction"])
            if e_edge not in exits and (key not in ahead or self._late(ctx, path, key)):
                self.plan = None
        if self.plan is None and not self.p.get("independent", 0):
            for arrival, junction, t_ev in amb_path:
                blockers = self._assign(ctx, arrival, junction, t_ev)
                if blockers is not None:
                    self.plan = {"arrival": arrival, "junction": junction, "blockers": blockers}
                    self.stats["plans"] += 1
                    break
        blockers = dict(self.plan["blockers"]) if self.plan else {}
        for v, (s, i, hold) in list(blockers.items()):
            st = ctx["states"].get(v)
            if st is None or st[0] != s or v not in ctx["p_pos"]:
                continue
            if ctx["p_pos"][v][1] + 1.0 > hold:
                spd = st[3]
                brake = spd * spd / (2 * 4.5) + spd * 0.1 + 6.0
                blockers[v] = (
                    s,
                    i,
                    min(ctx["p_pos"][v][1] + brake + 2.0, ctx["net"].edges[s].length_m - 0.6),
                )
                self.plan["blockers"][v] = blockers[v]
        if blockers:
            self.stats["steps_with_plan"] += 1
        free = [v for v in ctx["per"] if v not in blockers]
        chasers = self._chasers(ctx, free)
        pre = {}
        if not blockers or self.p["prepos_during_plan"]:
            pre = self._preposition(ctx, path, [v for v in free if v not in chasers])
        if pre:
            self.stats["steps_prepositioned"] += 1
        commands = {}
        for v in ctx["per"]:
            if v in blockers:
                s, i, hold = blockers[v]
                commands[v] = ("seg", s, hold, i)
            elif v in pre:
                s, i, hold, _j = pre[v]
                commands[v] = ("seg", s, hold, i)
            else:
                commands[v] = ("seg", e_edge, None)
        return commands
