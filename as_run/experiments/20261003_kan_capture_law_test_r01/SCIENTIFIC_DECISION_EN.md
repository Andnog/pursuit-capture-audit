# KAN capture law on TEST (A-110 S7, post hoc, descriptive)

Script `scripts/kan_capture_law_test.py` (sha256 recorded below). The A-104 models were refitted exactly (same data,
features, seeds) and scored on the PLB planner's TEST episodes (AVOIDANT/RANDOM, 936 episodes, base rate 0.343).

| Model | TEST AUC | Brier |
|---|---|---|
| KAN (pykan, A-104 settings) | 0.597 | 0.222 |
| Logistic regression | 0.646 | 0.214 |

Observed capture by lanes to close at the evader's first junction: 0.428 (≤ 4 lanes, n = 456), 0.319 (5–6, n = 342),
0.123 (≥ 7, n = 138).

Reading: the factor the KAN singled out (lanes to close at the first junction) is confirmed on unseen cities, and its
effect is larger than on DEVELOPMENT cities. As a predictor, the KAN is not better than logistic regression. The KAN
is used here for interpretation, not prediction. Training was verified: pykan's progress bar shows only the first step
when `log` exceeds `steps`, but the fitted model's training AUC (0.67 in A-104) and a toy check (BCE 0.70 → 0.01)
confirm that parameters are updated.
script sha256: 56d43a320fe787ac65cb32e31297ae28c9b91f707fdc0556e474bf35702f2120
