# Protocol — O27: two complete offline assisted-capture constructions

**Written and frozen before the declared model or the search was implemented.**

## What W4 requires (master plan)

> *W4 — Two complete offline assisted-capture constructions. Original moving starts, full legal trajectories
> and helper alternatives; supported model throughout. Two CPU hours total; at most 100,000 search expansions
> per case.* — *"Passing W4 establishes feasibility only under the declared model."* — *"A failure to find a
> witness within a search budget is not proof that capture is impossible."*

And A-47: **O27 alone yields abstract feasibility.** It does not unlock native work.

## Decisions this rests on, all the Research lead's

| | |
|---|---|
| Capture (D06, unchanged) | separation 0.30–2.00 m, speeds ≤ 1.0 m/s, relative ≤ 1.0 m/s, orientation ≤ 0.2618 rad, held 2.0 s |
| Collision (A-46) | physical overlap only |
| min_gap (A-46) | pursuers 2.5 m, evader 1.0 m |
| Coordination (D06) | the configuration must be produced by more than one pursuer's decisions |
| Evader (D08) | scripted; **AVOIDANT primary**, **OPTIMAL_ESCAPE** on a separate budget share |
| Helper and time (D12) | nearest non-finisher at witness start; intervention 5 decisions before it; `b1` = shortest-path pursuit toward the evader's public position for 5 decisions, then return |

## The declared model

A deterministic world on the junction graph of a TRAINING map, **not SUMO**.

- **Edges** carry length, lane count, and a speed cap equal to the slowest lane on the edge.
- **Connections** carry the via internal lane's length and speed (A-42) and, where signalled, the fixed-time
  program read from the network (A-43).
- **Motion** at the 0.1 s physical step, decisions every 1.0 s. Acceleration 2.6 m/s², deceleration
  4.5 m/s² — SUMO's default passenger type. **D07 is still `PROPOSED_NOT_FROZEN`**; these are declared model
  parameters, not a frozen dynamics decision.
- **Following:** on a single-lane edge a vehicle may not close within its own class min_gap of the rear of
  the vehicle ahead, and brakes so that it can stop there.
- **Multi-lane edges: no blocking.** A stopped vehicle on an edge with two or more lanes is assumed passable.
  Whether it could actually be passed depends on lane-change behaviour the model does not represent, so
  **no capture is claimed from blocking a multi-lane edge.** Conservative for capture.
- **Signals** hold a vehicle at the line until its link is green. Yellow is not go.
- **Collision** is body overlap; the model never admits one.

**Declared approximation direction: optimistic** (A-43, and O28's "free-flow estimates are lower bounds").
A construction here is feasibility **under this model** and nothing more.

## Scenarios, fixed by rule before any search

Four cases per evader level, from the TRAINING split in manifest order, one per map. Per case a seed
`sha256(map_id + level)`. Evader start: a seeded edge reachable with at least two exits downstream. Five
pursuer starts: seeded edges at graph distance 100–800 m from the evader. **Moving starts**: every vehicle
begins at half its edge's speed cap. **Speed ratio 1.0** — the evader's cap equals the pursuers', the
hardest ratio D08 permits; declared with every result.

The O26 Condesa cases are **not** used: Condesa is not among the 12 audited maps (A-44's recorded deviation).

## Search

Deterministic. A **plan** assigns each pursuer a route and a hold point. One **expansion** is one full forward
simulation of a joint plan with the evader reacting under its level, up to the 300 s horizon. Counted, capped
at **100,000 per case**.

## A complete construction

1. **Factual.** The independent capture judge returns `SUPPORTED` on the model trace; no collision at any
   step; every vehicle legal throughout.
2. **Helper alternative.** Helper and intervention time chosen by D12 **from the factual trace only**. The
   helper runs `b1` for five decisions, then resumes its plan; everyone else reacts.
3. **Contrast.** The judge returns `REJECTED` on the counterfactual trace. That is a positive capture contrast
   for this helper and intervention — and the evidence that the capture was **coordinated**.
4. **Determinism.** Re-running the factual plan reproduces its trace exactly.

## Verdicts per case

| Verdict | Condition |
|---|---|
| `CONSTRUCTED` | all four hold |
| `CAPTURE_NOT_COORDINATED` | factual capture, but the helper contrast is not positive |
| `NO_WITNESS_WITHIN_CAP` | no factual capture within the expansion or time budget — **not** evidence of impossibility |

## Acceptance rule, frozen now

| Gate | Condition |
|---|---|
| **`W4_GATE_PASSED`** | at least **two** `CONSTRUCTED` among the four **AVOIDANT** cases |
| `W4_GATE_NOT_PASSED` | fewer than two |

OPTIMAL_ESCAPE cases are reported separately and **cannot** pass or fail the gate.

## Budget, fixed now

Two CPU hours total: **90 minutes** across the four AVOIDANT cases, **30 minutes** across the four
OPTIMAL_ESCAPE cases, evenly per case. Unused time is **not** redistributed after any outcome is seen.

## Prohibited

Changing any rule above after a search result is seen. Claiming impossibility from a failed search. Claiming
capture from multi-lane blocking. Any SUMO process, TEST map, optimizer or checkpoint — this is offline.
