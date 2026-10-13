# Scientific decision — audit addendum r02 (A-119)

## W — witness for the 188 extended persistence cases (second review, point 4)

All 188 replays were run with legacy dispatch (0 failures). In every case:
- the OC capture reproduced at the sealed time with the same finisher, in the natural and in the frozen run;
- the vehicle states at t_c were identical in the two runs, so the intervention starts from the historical state;
- the follow-up was a complete 60 s, with 0 escapes.

The r01 extensions are confirmed and are not counted again. Overall, the 1,433 audited captures come from 176
scenario–evader families in seven cities, and no escape was observed. No i.i.d. bound is reported, because captures
share families across methods, teams and seeds.

## S — sensitivity to the R9 dispatch defect (second review, point 3)

600 paired A-99 test episodes: 200 each for PLB, junction ambush and pursuit. Legacy dispatch reproduces the sealed OC
outcome in 600 of 600.

| Method | Episodes with any non-accepted dispatch | OC changed (checked vs legacy) | OC legacy / checked |
|---|---|---|---|
| PLB | 156 / 200 | 0 | 68 / 68 |
| Junction ambush | 115 / 200 | 0 | 55 / 55 |
| Pursuit | 66 / 200 | 0 | 52 / 52 |

Non-accepted dispatches (all episodes):

| Mode | Rejected | Fallback | No route |
|---|---|---|---|
| Legacy | 15,543 | 998 | 1 |
| Checked | 15,914 | 3,821 | 23 |

Reading:
- Non-accepted dispatches are common. Most are admission refusals ("stop too close"), which were always handled
  correctly.
- Under legacy bookkeeping, the defective branches were "fallback" (TraCI stop errors) and "no route". They recorded an
  order as applied, so an identical request was suppressed. With checked bookkeeping these orders are retried, which
  produces more fallback events.
- No OC outcome changed in this sample, so the PLB − pursuit contrast in these 600 episodes is identical.
- This bounds the defect's effect for these three controllers and this sample. It is not a proof for every historical
  cohort.

## Offline (second review, points 1 and 4)

KAN inference recomputed with true families (386: 230 DEVELOPMENT, 156 TEST), each split separately, observed estimate
and interval reported separately.
- TEST AUC: KAN 0.597; spline 0.645; MLP 0.647; logistic 0.646. KAN − each ≈ −0.05, family 95 % intervals about
  [−0.11, 0.01].
- DEVELOPMENT: all KAN-difference intervals include 0.
- Bin correlations (lanes to close):
  - TEST: 0.68 / 0.80 / 0.65 / 0.63;
  - DEVELOPMENT: 0.28 / 0.29 / 0.10 / 0.02;
  - KAN − spline observed −0.12 (TEST) and −0.01 (DEVELOPMENT), intervals include 0.
- No KAN advantage detected.

Family-clustered intervals:
- null team: OC 3.1 % [1.5, 5.1], body ≤ 5 m 33.2 % [28.5, 38.1], centre ≤ 5 m 23.4 % [19.2, 27.7],
  ≤ 10 m 42.3 % [37.4, 47.5];
- lane indicator joint escape: TEST 7.9 % [1.7, 15.8], A-91 8.4 % [4.7, 12.9];
- junction indicator: 72.5 % [66.0, 78.5] and 82.0 % [79.1, 84.8].
