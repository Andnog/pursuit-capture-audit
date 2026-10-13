# Scientific decision — goal-directed evader r01 (A-112)

4,480 episodes (160 scenario-placement failures, balanced; 0 collisions). Seven non-TEST cities, salt PE16.

| Team | PLB | A-95 ambush | Pursuit | PLB − pursuit | PLB − A-95 | PLB single (mean) | Synergy (Bonferroni) |
|---|---|---|---|---|---|---|---|
| 3 | 0.196 | 0.115 | 0.074 | +0.122 [0.063, 0.189] | +0.081 [0.030, 0.137] | 0.057 | +0.052 [−0.026, 0.133] |
| 5 | 0.237 | 0.196 | 0.148 | +0.089 [0.022, 0.156] | +0.041 [−0.019, 0.104] | 0.049 | +0.078 [−0.019, 0.174] |
| 7 | 0.248 | 0.230 | 0.144 | +0.104 [0.037, 0.170] | +0.019 [−0.044, 0.081] | 0.048 | +0.056 [−0.044, 0.156] |

**Primary PASSED:** PLB − pursuit, pooled over teams, +0.105 [0.067, 0.143].

**Reading.**
- A fugitive that heads for a destination and only swerves away from pursuers within 150 m is harder to catch:
  PLB 0.20–0.25 here, against 0.28–0.40 for the avoiding evader.
- PLB still beats pursuit at every team size. Its advantage does not depend on the evader belonging to the family its
  predictor assumes.
  - The predictor's next-turn hit rate is 0.57, similar to the other evaders.
  - Against this evader a single PLB pursuer is weak (0.05 vs 0.16–0.20).
- The team's gain over independent pursuers is positive in every team size (+0.05 to +0.08; team 5 unadjusted
  [0.000, 0.156]). It is not significant after Bonferroni.
  - This is the only evader against which PLB shows a consistent sign of cooperation.
  - It is reported as suggestive, not as a finding.
- The evader leaves the network in 6–8 % of episodes.
