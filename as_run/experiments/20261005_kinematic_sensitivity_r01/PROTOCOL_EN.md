# Sensitivity to the simulator's kinematic model (A-127 K)

**Registered in:** `governance/AMENDMENTS_EN.md`, A-127, before any gated run.

**Question.** Do the two main contrasts of the article depend on two modelling choices of the simulator: the
position-update rule and the car-following model?

**Design.**
- Fresh scenarios, salt `PK1`, the seven non-TEST cities.
- 20 scenarios × 2 SUMO seeds × AVOIDANT/RANDOM × teams 3/5/7 × {PLB c2_15, pursuit}.
- Three variants on the same scenarios and seeds:
  - `K0`: the model used throughout (Euler update, Krauss car-following);
  - `K1`: ballistic position update (`--step-method.ballistic true`);
  - `K2`: IDM car-following as the default model (`--default.carfollowmodel IDM`).
- 10,080 scheduled episodes, each scored under OC, body gap ≤ 5 m and centre distance ≤ 5 m.

**Primary** (K1 and K2 separately): PLB − pursuit pooled over evaders and teams, family-clustered 95 % lower
bound > 0.

**Secondary.** Body-gap 5 m − OC for the pursuit team under each variant; OC rates under K1 and K2 relative to K0.

**Development check** (`DEVCHECK.json`, salt `DEVK`, not gated). One pursuit episode per variant in one TRAINING and
one DEVELOPMENT city. Both options changed the evader's trajectory within the first 0.2 s in both cities, so both
variants are applicable.

**Scope.** These are two alternatives inside the same simulator. They do not test a different simulator, vehicle
dynamics beyond SUMO's longitudinal models, or real vehicles.
