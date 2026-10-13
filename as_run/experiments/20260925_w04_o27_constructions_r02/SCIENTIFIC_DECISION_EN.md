# Decision — O27 r02

**Claim class: abstract feasibility under the declared model.** Offline: no SUMO process, no optimizer, no
checkpoint, no TEST map. r01 (`W4_GATE_NOT_PASSED`) remains the recorded first outcome.

## Verdict

**`W4_GATE_NOT_PASSED`.** One complete construction among the four AVOIDANT cases; the gate requires two.

| Level | Case | Verdict | Factual captures, by label | Expansions | Stopped by |
|---|---|---|---|---|---|
| AVOIDANT | adelaide_cbd | **`CONSTRUCTED`** | 1 constructed, 5 necessary-but-b1-null, 3 not coordinated | 69 | construction found |
| AVOIDANT | seattle_downtown | `NO_WITNESS_WITHIN_CAP` | none | 8,000 | expansion cap |
| AVOIDANT | toronto_downtown | `CAPTURE_NOT_COORDINATED` | 62 not coordinated, **36 failed verification** | 8,000 | expansion cap |
| AVOIDANT | washington_downtown | `CAPTURE_NOT_COORDINATED` | 200 not coordinated, **40 failed verification** | 8,000 | expansion cap |
| OPTIMAL_ESCAPE | adelaide_cbd | **`CONSTRUCTED`** | 1 constructed | 306 | construction found |
| OPTIMAL_ESCAPE | seattle_downtown | `CAPTURE_NOT_COORDINATED` | 80 not coordinated | 441 | queue exhausted |
| OPTIMAL_ESCAPE | toronto_downtown | `NO_WITNESS_WITHIN_CAP` | **54 failed verification** | 1,500 | expansion cap |
| OPTIMAL_ESCAPE | washington_downtown | `NO_WITNESS_WITHIN_CAP` | none | 1,500 | expansion cap |

CPU: 1,884.8 s of the 3,764 s allotted. Expansions, never CPU time, bound every capped case. Every failed
verification was a legality failure (emergency braking); none was a collision, a judge disagreement or
non-determinism.

## The two constructions

Both on adelaide_cbd, both with helper `p2` whose revised-D12 window ends at its settling time
(`reduces_to_original: false`): the construction is visible to the revised instrument, not the original one.

| | AVOIDANT | OPTIMAL_ESCAPE |
|---|---|---|
| Finisher / helper | p1 / p2 | p3 / p2 |
| Witness start | 25.9 s | 55.8 s |
| Helper settled / b1 decisions | 16.3 s / 11–16 | 34.5 s / 29–34 |
| Factual | SUPPORTED, 0 collisions, 0 safety failures, deterministic | same |
| b1 counterfactual | REJECTED | REJECTED |
| Helper never acts | REJECTED, legal | REJECTED, legal |

**Caveat.** Each b1 counterfactual contains **one emergency-braking step, after the factual witness window**
(38.6 s and 61.4 s), by the helper on its way back to its plan. Cause: a declared-model defect found after the
run — a hold on the edge after an internal lane is dropped from every constraint while the vehicle traverses
that internal lane (`diagnostics_counterfactual.json`). The frozen criterion does not require counterfactual
legality. The contrast holds on the legal prefix; after the failure step the counterfactual is not a legal
trajectory.

## The verdict is NOT robust to the model

Unlike r01, this verdict cannot be called robust. **130 factual captures failed verification for emergency
braking** (76 of them AVOIDANT, in toronto and washington). Their coordination labels were never computed.
The defect above is a candidate cause — factual captures come from plans, and plans routinely carry holds — but that is
**not established**: establishing it means re-running those searches, which is new search on r02 seeds.

What can be said:

- The gate is not passed under the frozen rules. **That stands.**
- Whether the declared model, with the defect fixed, would yield a second AVOIDANT construction is **unknown**.
- Coordination certified by both contrasts **exists under the declared model** (two cases, two evader levels,
  one map), where r01 had none. This is feasibility under an optimistic offline model, nothing more (A-47).

## Stop and decide

Per this package's protocol: no r03 without a Research-lead decision, and no budget extension. The W4 budget
has 31 CPU-minutes unspent that this protocol forbids redistributing after results are seen.
