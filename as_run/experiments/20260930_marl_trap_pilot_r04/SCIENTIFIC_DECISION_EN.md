# Scientific decision — MARL trap pilot r04 (A-86)

**Verdict: NOT PASSED — the MARL line is closed (pre-registered rule).** Neither arm's best-validation policy traps
the evader more often than the cut heuristic on 176 fresh test scenarios (salt `PE5`; 4 of 180 scenarios could not be
generated and are absent for every policy):

| Arm | best − cut (pooled over 2 seeds) | passes |
|---|---|---|
| T (gate tokens) | +0.011 [−0.031, 0.051] | no |
| U (nearest-junction tokens) | +0.020 [−0.040, 0.080] | no |

P(trapped) on test: cut 0.142, random-over-gates 0.136, individual 0.034; learned best 0.136–0.188, last 0.142–0.182,
BC 0.119–0.171. Secondary: best − BC +0.003 (T) and +0.017 (U), both CIs include 0; T − U −0.009 [−0.062, 0.045];
cut − individual +0.108 [0.057, 0.165] (replicates A-85 on new scenarios). 0 failed episodes, 0 collisions; the evader
left the map in 14.5 % of test episodes. 8.7 h wall, ≈ 70 CPU-h.

**Training dynamics.** All four runs used the full 8,000 episodes. The sampled trapping rate did not rise during PPO
(first vs last ten iterations: T1 0.149→0.162, T2 0.155→0.136, U1 0.174→0.150, U2 0.167→0.149). The validation gains of
the T runs (best 0.200 and 0.211 vs cut 0.122 on 90 scenarios) did not transfer to the test set: they are consistent
with noise plus selection of the maximum over 16 validations.

**Circuit breaker.** It never fired. For U, the best validation score was an early noisy peak (0.156 at 512 episodes,
3 scenarios above the cut), which by rule exempted the run from stopping. Lesson for future protocols: compare the
breaker against a smoothed or confidence-bounded validation score.

**Reading.** With a reward aligned to the direct endpoint, the same architecture, BC initialisation and 8,000 PPO
episodes per run, learning does not improve on imitation of the cut, and neither candidate set does better than the
heuristic. Together with A-85 (random ≈ cut), the evidence indicates little headroom for policy optimisation in this
regime: trapping is limited by the network and the evader's speed advantage, not by the assignment rule.
