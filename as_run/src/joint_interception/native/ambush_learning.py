"""Learned ambush selection (A-96): the ambush planner's decision made by a trainable scorer.

At each decision the controller enumerates OPTIONS:
- chase (every pursuer chases);
- keep the current plan;
- for each of the next junctions on the evader's predicted path, a FULL lane-level block (every lane
  of every exit) and PARTIAL blocks (the exit, or two exits, the evader is predicted to prefer),
  whenever the team has enough pursuers and the best assignment's slack is >= SLACK_FLOOR.

The rule (A-94 planner, the teacher for behaviour cloning) keeps a valid plan, else takes the
nearest full block with slack >= MARGIN_S, else chases. A learned scorer (rl/option_policy.py,
MLP or KAN head) may instead take riskier, partial or later options. Decisions are taken when no
plan is active (every 2 s), when the plan becomes invalid, or every 5 s with a plan; only
decisions with two or more options are recorded for learning.
"""

from __future__ import annotations

import itertools
import math
import random

import numpy as np

from .ambush import MARGIN_S, SLOW, STARTUP_S, AmbushPlanner

SLACK_FLOOR = -4.0
MAX_OPTIONS = 14
DECIDE_FREE_S = 2.0
DECIDE_PLAN_S = 5.0


class OptionAmbush(AmbushPlanner):
    def __init__(self, model=None, mode: str = "rule", seed: int = 0):
        super().__init__()
        self.model, self.mode = model, mode
        self.rng = random.Random(seed)
        self.records: list[dict] = []
        self.last_decision_t = -math.inf
        self.choice_counts = {"chase": 0, "keep": 0, "full": 0, "partial": 0}

    # -- options ----------------------------------------------------------------------------
    def _lanes_for(self, ctx, exits):
        return [(s, i) for s in exits for i in self._lanes_of(ctx["snet"], s)]

    def _exit_order(self, ctx, arrival, t_arrival):
        net, reach, per = ctx["net"], ctx["reach"], ctx["per"]
        sf = ctx["speed_factor"]
        scored = []
        for s in sorted(reach.succ.get(arrival, ())):
            link = net.links[(arrival, s)]
            ts = t_arrival + link.via_length_m / max(link.via_speed_mps * sf, 0.1)
            ts += net.edges[s].length_m / (net.edges[s].speed_cap_mps * sf)
            n = net.edges[s].to_node
            lead = min((p[0].get(n, math.inf) for p in per.values()), default=math.inf) - ts
            scored.append((-lead, s))
        return [s for _, s in sorted(scored)]

    def _assign_lanes(self, ctx, lanes, t_evader):
        net, per = ctx["net"], ctx["per"]
        pursuers = sorted(per)
        if not lanes or len(lanes) > len(pursuers):
            return None
        cost = {}
        for v in pursuers:
            pos = ctx["p_pos"][v]
            for s, idx in lanes:
                info = net.edges[s]
                hold = min(self.hold_m, 0.5 * info.length_m)
                if pos[0] == s:
                    if pos[1] + 6.0 >= info.length_m - 1.0:
                        cost[(v, s, idx)] = (math.inf, hold)
                    else:
                        cost[(v, s, idx)] = (0.0, max(hold, pos[1] + 6.0))
                    continue
                d = per[v][1].get(s)
                if d is None:
                    cost[(v, s, idx)] = (math.inf, hold)
                    continue
                free = d - (info.length_m - hold) / info.speed_cap_mps
                cost[(v, s, idx)] = (SLOW * free + STARTUP_S, hold)
        best, best_slack, best_mean = None, -math.inf, -math.inf
        for chosen in itertools.permutations(pursuers, len(lanes)):
            slacks = [
                t_evader - cost[(v, s, i)][0] for v, (s, i) in zip(chosen, lanes, strict=True)
            ]
            if min(slacks) > best_slack:
                best_slack, best, best_mean = min(slacks), chosen, sum(slacks) / len(slacks)
        if best is None or not math.isfinite(best_slack):
            return None
        blockers = {v: (s, i, cost[(v, s, i)][1]) for v, (s, i) in zip(best, lanes, strict=True)}
        return blockers, best_slack, best_mean

    def _options(self, ctx, path):
        opts = [{"kind": "chase"}]
        if self.plan is not None:
            opts.append({"kind": "keep", **self.plan.get("meta", {})})
        team = len(ctx["per"])
        for k, (arrival, junction, t_ev) in enumerate(path):
            exits = self._exit_order(ctx, arrival, t_ev)
            if not exits:
                continue
            cands = [("full", exits)]
            if len(exits) > 1:
                cands.append(("partial", exits[:1]))
            if len(exits) > 2:
                cands.append(("partial", exits[:2]))
            for kind, ex in cands:
                lanes = self._lanes_for(ctx, ex)
                if not lanes or len(lanes) > team:
                    continue
                r = self._assign_lanes(ctx, lanes, t_ev)
                if r is None or r[1] < SLACK_FLOOR:
                    continue
                opts.append(
                    {
                        "kind": kind,
                        "arrival": arrival,
                        "junction": junction,
                        "blockers": r[0],
                        "depth": k,
                        "lanes": len(lanes),
                        "min_slack": r[1],
                        "mean_slack": r[2],
                        "t_ev": t_ev,
                        "frac": len(ex) / len(exits),
                        "covers_pred": 1.0,
                        "n_exits": len(exits),
                    }
                )
        return opts[:MAX_OPTIONS]

    @staticmethod
    def _features(o):
        clip = lambda x, lo, hi: max(lo, min(hi, x))  # noqa: E731
        return [
            float(o["kind"] == "chase"),
            float(o["kind"] == "keep"),
            float(o["kind"] == "full"),
            float(o["kind"] == "partial"),
            o.get("depth", 0) / 4.0,
            o.get("lanes", 0) / 5.0,
            clip(o.get("min_slack", 0.0) / 20.0, -1.0, 2.0),
            clip(o.get("mean_slack", 0.0) / 20.0, -1.0, 2.0),
            clip(o.get("t_ev", 0.0) / 60.0, 0.0, 3.0),
            o.get("frac", 0.0),
            o.get("covers_pred", 0.0),
            o.get("n_exits", 0) / 4.0,
        ]

    def _context(self, ctx, n_opts):
        conn, states = ctx["conn"], ctx["states"]
        try:
            ex, ey = conn.vehicle.getPosition("e1")
            near = min(math.dist((ex, ey), conn.vehicle.getPosition(v)) for v in ctx["per"])
        except Exception:  # noqa: BLE001
            near = 200.0
        return [
            len(ctx["per"]) / 5.0,
            n_opts / MAX_OPTIONS,
            ctx["t"] / 300.0,
            float(self.plan is not None),
            min(near / 200.0, 3.0),
            states["e1"][3] / 15.0,
        ]

    def _rule(self, opts):
        for i, o in enumerate(opts):
            if o["kind"] == "keep":
                return i
        fulls = [(o["depth"], i) for i, o in enumerate(opts) if o["kind"] == "full"]
        for _, i in sorted(fulls):
            if opts[i]["min_slack"] >= MARGIN_S:
                return i
        return 0

    # -- control ----------------------------------------------------------------------------
    def __call__(self, ctx):
        from ..rl.option_policy import decide

        self.stats["steps"] += 1
        t = ctx["t"]
        path = self._predict(ctx)
        ahead = {(a, j) for a, j, _ in path}
        e_edge = ctx["e_pos"][0]
        invalidated = False
        if self.plan is not None:
            exits = {b[0] for b in self.plan["blockers"].values()}
            key = (self.plan["arrival"], self.plan["junction"])
            if e_edge not in exits and (key not in ahead or self._late(ctx, path, key)):
                self.plan, invalidated = None, True
        due = invalidated or (
            t - self.last_decision_t >= (DECIDE_PLAN_S if self.plan else DECIDE_FREE_S)
        )
        if due:
            opts = self._options(ctx, path)
            rule_idx = self._rule(opts)
            idx = rule_idx
            if len(opts) >= 2:
                tokens = np.array([self._features(o) for o in opts], dtype=np.float32)
                cvec = np.array(self._context(ctx, len(opts)), dtype=np.float32)
                logp, value = 0.0, 0.0
                if self.mode == "rule":
                    if self.model is not None:
                        _, logp, value = decide(
                            self.model, tokens, cvec, "forced", self.rng, rule_idx
                        )
                elif self.mode == "random":
                    idx = self.rng.randrange(len(opts))
                else:
                    idx, logp, value = decide(self.model, tokens, cvec, self.mode, self.rng)
                self.records.append(
                    {
                        "tokens": tokens,
                        "ctx": cvec,
                        "idx": idx,
                        "rule_idx": rule_idx,
                        "logp": logp,
                        "value": value,
                        "t": t,
                    }
                )
            chosen = opts[idx]
            self.choice_counts[chosen["kind"]] += 1
            if chosen["kind"] == "chase":
                self.plan = None
            elif chosen["kind"] != "keep":
                meta = {k: v for k, v in chosen.items() if k not in ("blockers",)}
                meta["kind"] = "keep"
                self.plan = {
                    "arrival": chosen["arrival"],
                    "junction": chosen["junction"],
                    "blockers": dict(chosen["blockers"]),
                    "meta": meta,
                }
                self.stats["plans"] += 1
            self.last_decision_t = t
        blockers = self.plan["blockers"] if self.plan else {}
        for v, (s, i, hold) in list(blockers.items()):
            st = ctx["states"].get(v)
            if st is None or st[0] != s or v not in ctx["p_pos"]:
                continue
            speed, pos = st[3], ctx["p_pos"][v][1]
            if pos + 1.0 > hold:
                brake = speed * speed / (2 * 4.5) + speed * 0.1 + 6.0
                blockers[v] = (s, i, min(pos + brake + 2.0, ctx["net"].edges[s].length_m - 0.6))
        if blockers:
            self.stats["steps_with_plan"] += 1
        return {
            v: (
                ("seg", blockers[v][0], blockers[v][2], blockers[v][1])
                if v in blockers
                else ("seg", e_edge, None)
            )
            for v in ctx["per"]
        }
