# Scientific decision — MARL pilot r03 (A-81)

**Verdict: PASSED (pre-registered primary rule).** All four arm × seed runs: final − initial P(physical cage) on 120
fresh reserved scenarios (salt `PE3`), CI lower bound > 0 — T1 +0.333 [0.233, 0.433], T2 +0.425 [0.317, 0.533],
U1 +0.342 [0.233, 0.450], U2 +0.567 [0.467, 0.667]. 0 failed episodes, 0 collisions.

**What the pass does and does not show.** As stated in the protocol, the primary rule is expected to pass after BC;
it shows that the pipeline acquires the caging behaviour, not that reinforcement learning adds value.

Pre-registered secondary (descriptive):

| Run | initial | BC | final | final − BC | final − cut |
|---|---|---|---|---|---|
| T seed 1 | 0.350 | 0.700 | 0.683 | −0.017 [−0.083, 0.050] | −0.017 [−0.092, 0.058] |
| T seed 2 | 0.283 | 0.667 | 0.708 | +0.042 [−0.025, 0.117] | +0.008 [−0.042, 0.067] |
| U seed 1 | 0.383 | 0.650 | 0.725 | +0.075 [−0.017, 0.167] | +0.025 [−0.058, 0.108] |
| U seed 2 | 0.175 | 0.683 | 0.742 | +0.058 [−0.017, 0.133] | +0.042 [−0.042, 0.133] |

Baselines: cut 0.700, cut_label 0.700, individual 0.317, random-over-gates 0.400.
T − U (final): seed 1 −0.042 [−0.133, 0.050]; seed 2 −0.033 [−0.125, 0.058].

Post-hoc (not pre-registered; `POSTHOC_ANALYSIS.json`): pooled final − BC +0.040 [0.000, 0.081]; pooled T − U
−0.037 [−0.117, 0.037]; pooled final − individual +0.398 [0.306, 0.487]; at least one of the 16 evaluated policies
cages in 94 % of scenarios (single SUMO seed each, so this headroom figure is inflated by noise). Per-map direction
differs: T ≥ U on adelaide, U > T on toronto and washington.

**Interpretation.** (1) Learned team policies cage at the level of the hand-designed cut heuristic and far above
individual pursuit; PPO fine-tuning adds at most a few points over imitation, not individually significant.
(2) The pilot gives no support to the hypothesis that the topological candidate set (arm T) outperforms the
unstructured one (arm U); the point estimates favour U. Two seeds cannot settle this; any confirmatory T vs U test
must be powered for differences of a few points. (3) Classification: implementation adequacy and pilot-scale
descriptive evidence; no confirmatory claim.

Source files hashed in `inputs.json` were not modified during the run. No TEST data.
