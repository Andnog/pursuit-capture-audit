# Scientific decision — an evader tuned against PLB (A-127 E)

**Status:** complete. Primary **met**.

## What was run

A new evader level, TUNED: a weighted sum of seven features of the public state per continuation. Its weights were
searched on the TRAINING cities to minimise OC capture by PLB c2_15, and the selected evader was tested on fresh
scenarios of the seven non-TEST cities.

- Rung 1 (salt ES1): 33 candidates × 4 cities × 6 scenarios × team 5 = 792 episodes, 33 placement failures (one
  condition, identical for all candidates); candidates compared on 23 common cells.
- Rung 2 (salt ES2): 9 candidates × 4 cities × 20 scenarios × teams 3/5/7 = 2,160 episodes, no failure; 240 cells.
- Test (salt PE21): 4,200 episodes scheduled; 190 failed scenario placement, in 38 conditions that fail identically
  for all five arms; 4,010 completed (134 families). No collision.

## Search

| | PLB capture, rung 2 |
|---|---|
| Reference weights (reproduce OPTIMAL_ESCAPE) | 0.367 |
| Selected candidate `c05` | 0.271 |
| Other candidates kept from rung 1 | 0.288 – 0.375 |

Reference minus selected = 0.096 ≥ 0.02, so the breaker condition "a stronger evader was found" holds on the search
scenarios. Selected weights (d1, d2, branch, crowd, on_edge, predicted, noise):
(−0.871, +0.221, +0.273, −0.137, −0.889, +0.273, +0.866). Read literally: it avoids continuations that carry a
pursuer or lead to one, it is strongly randomised, and it does not seek distance from the nearest pursuer.

## Test (OC; family-clustered 95 % intervals)

| Evader | PLB | Junction ambush | Pursuit | PLB − pursuit |
|---|---|---|---|---|
| Tuned (`c05`) | 0.291 | 0.248 | 0.162 | **+0.128 [0.081, 0.178]** |
| Reference (OPTIMAL) | 0.324 | — | 0.152 | +0.172 [0.115, 0.232] |

- **Primary:** PLB − pursuit against the tuned evader, lower bound 0.081 > 0, met. City → family [0.061, 0.198].
  By team: +0.097 [0.045, 0.153], +0.127 [0.063, 0.194], +0.162 [0.090, 0.233].
- PLB against the tuned evader minus against the reference (paired): −0.034 [−0.099, 0.031]. Pursuit: +0.010
  [−0.039, 0.059].
- PLB − junction ambush against the tuned evader: +0.042 [0.003, 0.083].
- The evader left the network in 4–7 % of episodes, in every arm.

## Reading

1. The advantage of waiting ahead over chasing survives an evader whose decision rule was tuned against PLB with a
   search of the same kind that tuned PLB.
2. The tuned evader lowered PLB's capture by 9.6 points on the search scenarios and by 3.4 points on fresh
   scenarios, where the interval includes zero. Part of the search gain is selection optimism. The registered test
   is the fresh one.

## Limits

- The family has seven hand-chosen features and 33 candidates. It is a scripted family tuned by random search. It is
  not a learned evader and not a game-theoretic best response; a stronger evader may exist.
- The evader was tuned against PLB only. Its effect on pursuit is not an optimised quantity.
- The reference arm is the TUNED level with weights that reproduce OPTIMAL_ESCAPE (checked in 800 random states by a
  unit test), on the same scenarios.

## Record

- The four existing evader levels were re-run on 140 recorded episodes before and after the source change:
  140 of 140 identical both times (`LEVELS_CHECK_before.json`, `LEVELS_CHECK_after.json`).
- The source change was applied only after every worker of the earlier studies had finished. 398 unit tests pass.
- A two-episode end-to-end check of the new level (salt DEVE, not gated) ran before the study.
- The A-127 text gave 6,720 test episodes; the design has 4,200. This was corrected in the A-127 clarification before
  any run.
