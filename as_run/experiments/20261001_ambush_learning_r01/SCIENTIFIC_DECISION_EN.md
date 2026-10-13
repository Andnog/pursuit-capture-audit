# Scientific decision — learned ambush selection r01 (A-96)

## Training (circuit breakers worked as designed)

| | MLP, seed 1 | KAN, seed 1 |
|---|---|---|
| BC held-out accuracy on the rule | 0.993 | 0.990 |
| Validation, BC checkpoint | 0.395 | 0.405 |
| Validation, best | 0.395 | 0.405 |
| Run stopped by breaker at | 2,048 episodes | 2,048 episodes |

The rule's validation score was 0.411 (A-95 planner 0.389). PPO policy entropy collapsed quickly (0.02–0.06), and
neither head improved on the cloned rule. The **global breaker** therefore fired: no seed-1 head beat the rule by 0.02,
so seeds 2–3 were skipped. This saved about 4 h of compute.

## Test (fresh salt PE9, 7 cities, 20 scenarios × 2 seeds × 4 settings, D06)

6,744 episodes, 264 failed placements, 0 collisions.

| Policy | D06 capture [95 % CI] |
|---|---|
| Rule (ambush) | 0.277 [0.243, 0.311] |
| Learned MLP (best = BC) | 0.277 |
| Learned KAN (best = BC) | 0.277 |
| A-95 ambush planner | 0.273 |
| Random option (control) | 0.231 [0.200, 0.264] |
| Pursuit | 0.200 [0.170, 0.231] |

- **Primary: NOT PASSED** for both heads. Learned − rule = 0.000 [−0.004, 0.004]; KAN − MLP 0.000.
- **Secondary (replications):**
  - ambush − pursuit **+0.077 [0.055, 0.100]**, pooled over 4 settings and 7 cities: confirms A-95 on new scenarios;
  - learned − random option +0.046 [0.020, 0.071]: the choice of ambush matters.

## Interpretability (`KAN_ANALYSIS.json`, 3,000 decisions, 10 permutations)

| Model | Agreement with rule | Top permutation importance |
|---|---|---|
| Trained KAN | 0.993 | is_partial 0.22, min_slack 0.10, is_keep 0.09 |
| Random-initialised KAN (control) | 0.748 (= majority class "chase", 0.758) | unrelated features |

- **Edge amplitudes:** the trained KAN's first-layer amplitudes rank the same features.
- **Partial dependence:**
  - preference rises monotonically with the blockers' time slack and saturates near 15–18 s;
  - it falls for partial blocks and rises for keeping a plan.
- **Faithfulness:** this is the rule's known logic (never partial, keep valid plans, require positive slack). The KAN
  faithfully exposes the decision logic it learned, which here can be checked against a known ground truth.

## Reading

Reinforcement learning on top of the ambush rule, in this budget and with these breakers, did not find a better
policy. The rule appears to be a local optimum for the option space offered. The KAN head matches the MLP's
performance and makes the policy readable, with an interpretation validated against the known rule.
