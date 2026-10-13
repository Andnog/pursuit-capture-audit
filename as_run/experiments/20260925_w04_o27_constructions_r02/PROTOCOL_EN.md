# Protocol — O27 r02: the pre-registered re-run of the W4 constructions

**Written and frozen before any r02 case was searched.** Authorised by the Research lead (A-51).
**r01 (`20260924_w04_o27_constructions_r01`, `W4_GATE_NOT_PASSED`) remains the recorded W4 outcome**; r02
is a separate, pre-registered attempt with its own verdict.

## What carries over from r01 unchanged

- The r01 `PROTOCOL_EN.md` and `PROTOCOL_AMENDMENT_EN.md`, except where this file says otherwise:
  D06 capture predicate, A-46 collision semantics and min_gap (pursuers 2.5 m, evader 1.0 m), D08 evader
  levels, speed ratio 1.0, the 300 s horizon, one TRAINING map per case in manifest order.
- **The criterion: both contrasts** (D12 `b1` positive **and** necessity). Verdict table as in r01's
  amendment.
- **Acceptance rule:** `W4_GATE_PASSED` iff at least **two** `CONSTRUCTED` among the four **AVOIDANT** cases.
  OPTIMAL_ESCAPE is reported separately and cannot pass or fail the gate.
- Offline only: no SUMO process, no TEST map, no optimizer, no checkpoint.

## What changes, all fixed before any r02 case

1. **Fresh scenario seeds.** `sha256(map_id + level + "r02")`. The r01 seeds are excluded: a development scan
   on them (fixed model, revised D12) already produced one `CONSTRUCTED` (AVOIDANT seattle), recorded in the
   ledger as development evidence only.
2. **Moving starts are admissible.** Half the edge's cap, as before, **capped** so the vehicle can stop by its
   start edge's end at ordinary deceleration (0.9 × √(2·4.5·(length − offset − 0.5))). The r01 rule placed a
   pursuer where it could not (r02-seed washington baseline). r01 seeds are unaffected by this change.
3. **The revised D12 (A-51):** the five-decision `b1` window ends at the helper's settling time (within 1.0 m
   of its witness-start position from then until the witness start; a helper still moving at > 0.1 m/s at the
   witness start settles there, which reduces exactly to r01's rule).
4. **Declared-model defects fixed since r01**, each found by an emergency-braking or overlap check on a
   scenario baseline and each covered by a regression test:
   chained internal lanes (A-42 follow-up; 0.0 m residual against SUMO on adelaide route 0);
   stop-line crossing; internal-lane anticipation; a moving leader treated as a wall; terminal-edge
   anticipation; the dilemma zone (proceed on yellow only when unable to stop ordinarily; red never);
   merges (yield at junction entry, same-link abreast merge from a multi-lane edge); signal-aware
   anticipation at every link of the known route; **the evader anticipates every continuation it might
   choose within its braking horizon**, not just one channel past its decided edge.
5. **Command admission.** A plan command the vehicle cannot follow at ordinary deceleration is refused and
   counted (`refused_commands`); r01 executed 238 such commands.
6. **Broadened candidate generator.** All admissible targets are candidates (unchosen first); the finisher
   ETA screen falls back to the nearest finisher instead of discarding the cover.

## Legality of the scenarios, checked before freezing

All 16 baselines (4 maps × 2 levels × r01 and r02 seeds, no plan, evader reacting) run 300 s with
**0 collisions and 0 safety failures** on the code whose hashes `inputs.json` records. Only baseline legality
was examined on the r02 seeds; **no search, no plan and no capture check** was run on them before launch.

## Budget, fixed now

What r01 left of W4's two CPU hours: **~62 CPU-minutes**, split 3 : 1 as in r01, evenly per case.

| Level | CPU seconds / case | Expansion cap / case |
|---|---|---|
| AVOIDANT | 706 | 8,000 |
| OPTIMAL_ESCAPE | 235 | 1,500 |

Expansion caps are set from a calibration on **r01 seeds** (AVOIDANT ≈ 63–66 ms/expansion; OPTIMAL
16–143 ms/expansion, the high end dominated by verification of many factual captures) so that expansions,
not CPU time, are expected to bind. If CPU time binds anyway it is recorded as `stopped_by: "CPU cap"` —
machine-dependent, and declared as such. Unused time is **not** redistributed after any outcome is seen.
Both caps are far below the plan's 100,000 expansions per case.

## Recorded per case

Verdict, tally of every factual capture's label, expansions, final CPU seconds, stop reason, refused
commands, and the reason every factual capture failed verification (collisions / safety failures /
judge / determinism).

## Interpretation, stated in advance

- `NO_WITNESS_WITHIN_CAP` is **not** evidence that capture is impossible.
- `NECESSARY_BUT_B1_NULL` is coordination the D12 instrument cannot certify, not absence of coordination.
- Passing establishes feasibility **under the declared, optimistic model only** (A-47): it does not unlock
  native work; the empirical model-validation gate stands between O27 and W5.
- If r02 does not pass: stop and decide. No r03 without a Research-lead decision; no budget extension.

## Prohibited

Changing any rule above after an r02 result is seen. Modifying any source listed in `inputs.json` while the
search runs. Claiming impossibility from a failed search. Claiming capture from multi-lane blocking.
