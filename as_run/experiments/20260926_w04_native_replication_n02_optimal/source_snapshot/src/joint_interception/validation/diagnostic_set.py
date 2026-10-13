"""The A-47 diagnostic set: plan-bearing scenarios, generated and selected by a seeded rule.

Everything here runs the declared model only. Selection looks at MODEL outcomes (legality, whether a
capture happened) and never at SUMO, so the set is fixed before any comparison exists.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..evaluation.capture_judge import judge_capture
from ..opportunities.types import Verdict
from ..simulator.evader import EvaderLevel
from ..world.construction import (
    FINISHER_HOLDS_M,
    RELEASE_OFFSETS,
    Constructor,
    Plan,
    Scenario,
    Segment,
    make_scenario,
)
from ..world.network import GraphNetwork
from ..world.simulation import World


@dataclass
class ModelRun:
    """One declared-model run, recorded at every physical step."""

    scenario: Scenario
    plan: Plan
    kind: str
    world: World
    # states[k][vid] = (edge, (from, to) or None, offset, speed, odometer); k = step index
    states: list[dict[str, tuple]] = field(default_factory=list)
    # holds[decision][vid] = the pursuer's hold after that decision's commands
    holds: dict[int, dict[str, tuple[str, float] | None]] = field(default_factory=dict)
    routes: dict[str, list[str]] = field(default_factory=dict)
    capture: dict | None = None

    @property
    def end_s(self) -> float:
        return round(self.world.time_s, 6)


def _snapshot(world: World, odometer: dict[str, float]) -> dict[str, tuple]:
    out = {}
    for vid, v in world.vehicles.items():
        link = (v.in_link.from_edge, v.in_link.to_edge) if v.in_link else None
        out[vid] = (v.edge, link, v.offset, v.speed, odometer[vid])
    return out


def run_model(
    net: GraphNetwork,
    scenario: Scenario,
    plan: Plan,
    domain: dict,
    kind: str = "",
    b1: tuple[str, int, int] | None = None,
) -> ModelRun:
    c = Constructor(net, scenario, domain, 10**9, 1e12)
    world = c.world(record=True)
    control = c.controller(plan, b1)
    run = ModelRun(scenario, plan, kind, world)
    odometer = {vid: 0.0 for vid in world.vehicles}

    def controller(w: World, decision: int) -> None:
        control(w, decision)
        run.holds[decision] = {vid: v.hold for vid, v in w.vehicles.items() if v.klass == "pursuer"}

    def recorder(w: World) -> bool:
        for vid, v in w.vehicles.items():
            odometer[vid] += v.speed * w.step_s
        run.states.append(_snapshot(w, odometer))
        return False

    run.states.append(_snapshot(world, odometer))
    world.run(c.horizon_s, controller, recorder)
    for vid in world.vehicles:
        # While a vehicle is in a link, `edge` stays the link's FROM edge.
        seq: list[str] = []
        for state in run.states:
            if not seq or seq[-1] != state[vid][0]:
                seq.append(state[vid][0])
        last = run.states[-1][vid][1]
        if last is not None:
            seq.append(last[1])
        run.routes[vid] = seq
    verdict = judge_capture(world.trace, "e1", c.params, c.step_s)
    if verdict.verdict is Verdict.SUPPORTED:
        run.capture = {
            "finisher": verdict.finisher,
            "witness_start_s": verdict.witness_start_s,
        }
    return run


def _interception_plan(c: Constructor, rng: random.Random) -> Plan | None:
    baseline = c.simulate(Plan())
    candidates = list(c.candidates(c.evader_path(baseline)))
    if not candidates:
        return None
    step, target, alternatives, approach, hold = rng.choice(candidates)
    pursuers = sorted(c.sc.pursuer_starts)
    finisher = min(pursuers, key=lambda p: (c.eta_s(p, approach), p))
    helpers = [p for p in pursuers if p != finisher]
    plan = Plan()
    release = max(0, step["decision"] + rng.choice(RELEASE_OFFSETS))
    plan.segments[finisher] = [Segment(0, approach, None), Segment(release, target, hold)]
    for helper, alt in c.assign_cover(helpers, alternatives).items():
        plan.segments[helper] = [Segment(0, alt, 12.0)]
    return plan


def _random_plan(c: Constructor, rng: random.Random) -> Plan | None:
    baseline = c.simulate(Plan())
    edges = sorted(
        {d.current_edge for d in baseline.evader.decisions}
        | {d.chosen for d in baseline.evader.decisions if d.chosen}
    )
    if not edges:
        return None
    plan = Plan()
    for vid in sorted(c.sc.pursuer_starts):
        target = rng.choice(edges)
        hold = rng.choice((*FINISHER_HOLDS_M, None))
        segments = [Segment(0, target, hold)]
        if rng.random() < 0.5:
            segments.append(
                Segment(
                    rng.randint(20, 120), rng.choice(edges), rng.choice((*FINISHER_HOLDS_M, None))
                )
            )
        plan.segments[vid] = segments
    return plan


def generate(
    net: GraphNetwork, map_id: str, index: int, domain: dict, pursuers: list[str]
) -> ModelRun | None:
    """Scenario `index` of a map: even indices get an interception plan, odd a random one."""
    scenario = make_scenario(net, map_id, EvaderLevel.AVOIDANT, pursuers, f"val{index:03d}")
    if len(scenario.pursuer_starts) != len(pursuers):
        return None  # the start rule found no admissible start for some pursuer
    rng = random.Random(scenario.seed)
    c = Constructor(net, scenario, domain, 10**9, 1e12)
    kind = "interception" if index % 2 == 0 else "random"
    plan = _interception_plan(c, rng) if kind == "interception" else _random_plan(c, rng)
    if plan is None:
        return None
    return run_model(net, scenario, plan, domain, kind)


def select(
    net: GraphNetwork,
    map_id: str,
    domain: dict,
    pursuers: list[str],
    captures_wanted: int,
    others_wanted: int,
    max_index: int,
) -> tuple[list[tuple[int, ModelRun]], dict]:
    """First `captures_wanted` legal scenarios with a model capture and first `others_wanted`
    legal ones without, in index order. Illegal model runs are excluded and counted."""
    chosen: list[tuple[int, ModelRun]] = []
    tally = {"scanned": 0, "no_plan": 0, "illegal": 0, "capture": 0, "other": 0}
    n_cap = n_other = 0
    for index in range(max_index):
        if n_cap >= captures_wanted and n_other >= others_wanted:
            break
        tally["scanned"] += 1
        run = generate(net, map_id, index, domain, pursuers)
        if run is None:
            tally["no_plan"] += 1
            continue
        if run.world.collisions or run.world.safety_failures:
            tally["illegal"] += 1
            continue
        if run.capture is not None and n_cap < captures_wanted:
            n_cap += 1
            tally["capture"] += 1
            chosen.append((index, run))
        elif run.capture is None and n_other < others_wanted:
            n_other += 1
            tally["other"] += 1
            chosen.append((index, run))
    return chosen, tally
