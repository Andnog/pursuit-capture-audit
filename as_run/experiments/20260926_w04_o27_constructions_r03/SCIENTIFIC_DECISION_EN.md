# Decision — O27 r03 (final W4 attempt)

**Claim class: abstract feasibility under the declared model.** Offline: no SUMO process, no optimizer, no
checkpoint, no TEST map.

## Verdict

**`W4_GATE_PASSED`** — two `CONSTRUCTED` among the four AVOIDANT cases, the gate's minimum.

| Case | Verdict | Factual captures, by label | Expansions | Stopped by |
|---|---|---|---|---|
| adelaide_cbd | **`CONSTRUCTED`** | 1 constructed, 57 necessary-but-b1-null, 461 not coordinated | 3,056 | construction found |
| seattle_downtown | **`CONSTRUCTED`** | 1 constructed, 6 not coordinated, **198 failed verification** | 3,421 | construction found |
| toronto_downtown | `CAPTURE_NOT_COORDINATED` | 9 necessary-but-b1-null, 12 not coordinated | 5,000 | expansion cap |
| washington_downtown | `NO_WITNESS_WITHIN_CAP` | none | 3,561 | queue exhausted |

CPU 1,020.9 s of 1,880 s. No case was stopped by CPU time.

## Must be reported together — multiplicity

This is the **third** pre-registered attempt (A-53). r01: 0 of 4. r02: 1 of 4. r03: 2 of 4. Each ran on fresh
seeds under a protocol frozen before its cases, and the criterion and gate never changed. Between attempts
the declared model was corrected only for defects that produced **illegal** trajectories (emergency braking,
overlap). Those corrections change capture opportunities in both directions, and one of them (A-52) was found
by examining r02's constructed cases. A pass on the third attempt, at exactly the threshold, after
result-informed model corrections, is weaker than a first-attempt pass and is reported as such.

## The two constructions

| | adelaide_cbd | seattle_downtown |
|---|---|---|
| Finisher / helper | p4 / p2 | p3 / p1 |
| Witness start | 96.8 s (10 evader decisions) | 73.3 s (2 evader decisions) |
| Helper distance at witness start | 14.7 m | 98.6 m |
| Helper settled / b1 decisions | 90.5 s / 85–90 | 61.8 s / 56–61 |
| Factual | SUPPORTED; 0 collisions, 0 safety failures; deterministic | same |
| b1 counterfactual | REJECTED; legal | REJECTED; legal |
| Helper never acts | REJECTED; legal | REJECTED; legal |

**Every trajectory involved is legal** under the declared model — unlike r02, where the counterfactuals were
not. Both need the revised D12 (`reduces_to_original: false`).

**Mechanism, checked after the run** (`diagnostics_post_run.json`): in both, the finisher is stopped at its hold
on a **single-lane** edge and the evader is stopped 1.0 m behind it (its min_gap). No signal, merge yield or
route end is involved. This is physical blocking, the capture the model is designed to represent — not the
multi-lane blocking the protocol forbids claiming.

In seattle the helper is 98.6 m from the evader at the witness start: it covers an escape route rather than
closing in. That is coordination by positioning, the form A-50 predicted.

## What this does and does not establish

- **Does:** two captures on two TRAINING maps where, under the declared model, the capture exists with the
  helper's plan and fails both with the helper replaced by `b1` pursuit and with the helper never acting.
- **Does not:** anything about SUMO or reality. The model is offline and declared **optimistic** (A-43, O28).
  **A-47: O27 alone does not unlock native work.** The empirical model-validation gate stands between O27 and
  W5.
- **Does not:** anything about OPTIMAL_ESCAPE, which r03 did not run (A-53).

## Known defect found after the run

198 seattle factual captures failed verification, all at one event: a pursuer braking for a red light is
asked by a merge yield to stop 0.5 m before the stop line and needs ≈ 5.05 m/s² against 4.5. The merge
priority's "can still stop" test measures to the junction entry, not to the yield point. It can only
**block** verification, never create a construction; it did not touch the two constructed traces. To be fixed
before the model is used again.
