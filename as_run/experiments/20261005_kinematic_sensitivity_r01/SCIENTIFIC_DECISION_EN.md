# Scientific decision — sensitivity to the simulator's kinematic model (A-127 K)

**Status:** complete. Both primaries **met**.

## What was run

Fresh scenarios (salt PK1, seven non-TEST cities, 20 scenarios × 2 SUMO seeds × AVOIDANT/RANDOM × teams 3/5/7 ×
{PLB c2_15, pursuit}) under three kinematic variants on the same scenarios and seeds. 10,080 episodes scheduled;
252 failed scenario placement, in 42 conditions that fail identically for both controllers and all three variants;
9,828 completed (273 families and 819 cells per variant).

## Results (OC unless stated; family-clustered 95 % intervals)

| Variant | PLB | Pursuit | PLB − pursuit | City → family | Body gap 5 m − OC, pursuit |
|---|---|---|---|---|---|
| K0: Euler update, Krauss (the model used throughout) | 0.439 | 0.313 | +0.126 [0.090, 0.164] | [0.079, 0.180] | +0.619 [0.573, 0.665] |
| K1: ballistic update | 0.443 | 0.303 | **+0.140 [0.103, 0.177]** | [0.088, 0.198] | +0.631 [0.586, 0.676] |
| K2: IDM car-following | 0.449 | 0.331 | **+0.118 [0.079, 0.158]** | [0.071, 0.169] | +0.581 [0.531, 0.630] |

- **Primary, K1:** lower bound 0.103 > 0, met. **Primary, K2:** lower bound 0.079 > 0, met.
- OC relative to K0 (paired): K1 PLB +0.004 [−0.023, 0.031], pursuit −0.009 [−0.035, 0.017]; K2 PLB +0.010
  [−0.041, 0.061], pursuit +0.018 [−0.034, 0.070]. No detected shift.

## Reading

Neither the position-update rule nor the car-following model changes the two contrasts the article rests on: PLB
remains 12–14 points above pursuit, and the 5 m rule remains about 60 points above OC for the pursuit team.

## Limits

- Two alternatives inside one simulator. This does not test another simulator, lateral or tyre dynamics, or real
  vehicles.
- OC shifts are not shown to be zero; their intervals are a few points wide.

## Collisions

Eight episodes were flagged as collided: four under K0 and four under K1, none under K2. All eight are the same
scenario and SUMO seed (Sapporo, scenario 16, seed 9516, RANDOM evader, teams of 5 and 7), for both controllers. This
points to that start placement and not to a controller. None of them is a capture. They are kept in the analysis.

## Execution record

- Development check before the gated run: both options changed the evader's trajectory within 0.2 s in two cities
  (`DEVCHECK.json`).
- The run was started with 4 workers, stopped after 1,150 episodes and resumed with 10 workers once another study had
  finished. No episode was repeated or discarded, and no outcome had been read before the run completed.
- Sources were not changed while its workers ran. The evader source gained a new level (A-127 E) only after this run
  had finished.
- Arm K0 is also the paired reference of the background-traffic probe (A-127 T).
