# Decision — MARL pilot r02: NOT PASSED (acquisition in 2 of 4 runs; learned policies far below the cut heuristic)

| Policy (60 reserved scenarios, greedy) | P(physical cage) |
|---|---|
| cut heuristic | 0.733 |
| individual heuristic | 0.400 |
| random over gates | 0.317 |
| T seed 1: initial / BC / final | 0.467 / 0.317 / 0.383 |
| T seed 2: initial / BC / final | 0.150 / 0.367 / 0.367 |
| U seed 1: initial / BC / final | 0.250 / 0.217 / 0.333 |
| U seed 2: initial / BC / final | 0.183 / 0.250 / 0.500 |

Acquisition (final − initial): T1 −0.08 [−0.25, 0.08] ✗; T2 +0.22 [0.08, 0.35] ✓; U1 +0.08 [−0.05, 0.22] ✗;
U2 +0.32 [0.15, 0.47] ✓. Final − cut: −0.23 to −0.40, all CIs below 0. T − U: +0.05 [−0.07, 0.18], −0.13 [−0.28, 0.02].
0 failed episodes; 294 demonstration episodes (cut cages 0.69).

**Diagnosis (from the training log).** (1) BC does not reproduce the heuristic (BC policies 0.22–0.37 vs 0.73): the
token features lack "this is my current target", so the heuristic's keep-your-gate (hysteresis) decisions cannot be
imitated. (2) PPO does not improve: sampled caging rate flat over training while the joint entropy rises (T 2.6 → 5.2–5.7,
U 3.3 → 6.0–6.8): the summed entropy bonus dominates a weak advantage signal over ~300 decisions per episode.
These are method-implementation findings, not evidence about H1.
