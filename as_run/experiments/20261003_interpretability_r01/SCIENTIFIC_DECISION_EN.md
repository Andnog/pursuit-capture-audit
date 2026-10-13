# Scientific decision — KAN vs MLP vs regression explanations (A-113, post hoc, metrics fixed in advance)

Scripts: `scripts/interpretability_capture_law.py`, `scripts/interpretability_policy_heads.py`. No RL training was
restarted; the MAPPO actors are the sealed A-105 checkpoints.

## Part 1 — capture law (6 features; fit on 3,098 TRAINING episodes; held out 2,284 DEVELOPMENT + 936 TEST)

| | KAN (pykan) | Logistic | MLP (CV-selected, 8 units, L2 1.0) |
|---|---|---|---|
| AUC train / DEV / TEST | 0.665 / 0.573 / 0.597 | 0.622 / 0.566 / 0.646 | 0.635 / 0.553 / 0.647 |
| Parameters / fit time | 460 / 26.5 s | 7 / 0.1 s | 65 / 0.1 s |
| Top feature, native explanation | lanes to close | lanes to close | — |
| Top feature, permutation (held out) | lanes to close | lanes to close | lanes to close |
| Ranking stability over 20 refits (τ): native / permutation | 0.48 / 0.25 | 0.69 / 0.71 | — / 0.72 |
| Partial-dependence faithfulness to observed held-out capture, lanes to close (r) | **0.70** | 0.46 | 0.50 |
| Same, mean distance of pursuers (r) | **0.45** | 0.05 | 0.08 |

Ranking agreement (Kendall τ):
- KAN native vs its own permutation importance: 0.20;
- KAN native vs logistic coefficients: 0.73;
- KAN native vs MLP permutation importance: −0.07;
- KAN vs MLP permutation importances: 0.47.

**Symbolic extraction.** It succeeded once variables were named (pykan's default naming fails with
`NameError: x1`, the A-104 failure). The pruned KAN reduces to one hidden unit:

logit ≈ −0.74·lanes − 0.04·avoidant − 0.04·speed + 0.025·t_mean − 0.020·t_nearest + 0.0003·(4·team + 10)² − 0.50
(inputs scaled to [−1, 1]).

It is essentially a logistic regression dominated by lanes to close. It generalises better than the numeric KAN
(TEST AUC 0.635 vs 0.597) and close to logistic regression (0.646).

## Part 2 — MAPPO actors (19 inputs; 4,950 / 2,160 teacher decisions from 240 TRAINING episodes)

| | KAN actor | MLP actor | Conditional logit (linear) |
|---|---|---|---|
| Top-1 agreement with the teacher (held out) | 0.995 | 0.995 | 0.988 |
| Top-3 by permutation | is_stay, is_my_target, my_slack | same | is_my_target, is_stay, is_chase |
| Top-3 native | is_stay, my_slack, is_my_target | — | is_my_target, is_stay, my_slack (coef × s.d.) |
| Choices changed when the top-3 are set to median (random-3) | 0.395 (0.104) | 0.925 (0.104) | — |

Ranking agreement (Kendall τ, all features):
- KAN native vs KAN permutation: 0.11;
- KAN permutation vs MLP permutation: 0.71.

The KAN's native attribution ranks context inputs (evader speed, time, own speed) 4th–6th. Permutation shows they
change almost no choice, because the context is shared by every candidate and shifts all scores equally.

Partial-dependence shapes of the KAN and MLP actors agree closely for the features that matter:
- r ≥ 0.91 for my_slack, teammates_targeting, lane_index, depth and n_exits;
- r = 0.77–0.78 for exit_rank and best_other_slack;
- the minor junction_lanes feature disagrees (r = −0.34).

## Verdict, by the rule fixed in A-113

**The KAN's explanation is reproducible with standard tools.**
- The KAN, an equally accurate MLP and a regression single out the same drivers: lanes to close at the first
  junction for capture; slack and keeping the current plan for the policy.
- The KAN's native attribution is neither more faithful nor more stable:
  - it is the least stable ranking (τ 0.48 vs 0.69–0.72);
  - it disagrees with the KAN's own permutation importance (τ 0.11–0.20);
  - it credits inputs that do not change decisions.

**Where the KAN does help.**
1. Its univariate response shapes follow non-monotone held-out effects more closely than an MLP's or a regression's
   partial dependence (r 0.70 vs 0.46–0.50 for lanes to close).
2. Symbolic distillation yields a closed-form law that is compact, readable and better generalising than the numeric
   KAN.

**Costs.** About 7–65× more parameters, about 250× longer fitting, and fragile tooling: symbolic extraction needs named
variables, and the progress display hides training progress.

**Recommendation.** Use KANs as a *hypothesis generator*: shape discovery and symbolic distillation. Cross-check them
with model-agnostic tools. Do not use native KAN attributions as evidence of decision relevance.
