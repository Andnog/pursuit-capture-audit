# Scientific decision — pre-positioning ambush optimisation r01 (A-98)

## Search

- **Generation 1:** best `c1_14` beat the defaults by +0.026 on round 3 (breaker passed).
- **Generation 2:** best **`c2_15`**, +0.063 over the defaults on round 3.
- **Fresh validation** (192 episodes each): 0.476 vs defaults 0.422.

Selected parameters: depth 2, margin 0 s, slow 1.05, startup 5 s, hold 21.8 m, **chasers 0**, pre-positioning
targets 1–2 junctions ahead, pre_margin −1.0 s, no pre-positioning during an ambush. In words: **nobody chases;
every pursuer goes ahead to wait in the predicted exit lanes of the evader's next one or two junctions**, and a full
lane-level ambush is laid as soon as it becomes feasible.

## Test

Fresh salt PE11; 7 cities; 20 scenarios × 2 seeds; full 300 s; D06. 15,120 episodes; 418 failed placements;
1 collision.

**Primary: PASSED.** Optimised − A-95 ambush, pooled over 6 cells: **+0.050 [+0.023, +0.076]**.

| Cell | Optimised | Default pre-pos. | A-95 ambush | Pursuit | Opt − A-95 | Opt − pursuit | Single (opt) | Synergy |
|---|---|---|---|---|---|---|---|---|
| AVOIDANT, team 3 | 0.279 | 0.261 | 0.217 | 0.170 | +0.062 [-0.004, +0.127] | +0.109 [+0.040, +0.178] | 0.168 | -0.070 [-0.144, +0.005] |
| AVOIDANT, team 5 | 0.361 | 0.299 | 0.307 | 0.223 | +0.055 [-0.015, +0.124] | +0.139 [+0.066, +0.215] | 0.164 | -0.066 [-0.156, +0.021] |
| AVOIDANT, team 7 | 0.369 | 0.405 | 0.336 | 0.223 | +0.033 [-0.036, +0.102] | +0.146 [+0.073, +0.219] | 0.163 | -0.113 [-0.200, -0.026] |
| RANDOM, team 3 | 0.307 | 0.237 | 0.200 | 0.200 | +0.107 [+0.048, +0.170] | +0.107 [+0.052, +0.167] | 0.212 | -0.054 [-0.113, +0.006] |
| RANDOM, team 5 | 0.344 | 0.293 | 0.311 | 0.263 | +0.033 [-0.033, +0.100] | +0.081 [+0.015, +0.148] | 0.210 | -0.078 [-0.137, -0.022] |
| RANDOM, team 7 | 0.404 | 0.430 | 0.393 | 0.359 | +0.011 [-0.056, +0.078] | +0.044 [-0.019, +0.107] | 0.217 | -0.068 [-0.137, +0.001] |

## Reading

- **Gains.** The optimised planner raises capture over A-95 by +5 points pooled, and over pursuit by +4 to +15 points
  (CI > 0 in 5 of 6 cells). With 5–7 pursuers it reaches 0.36–0.43.
- **The gain comes from better individual behaviour, not cooperation.** One pursuer alone running the planner
  captures 0.16–0.22, versus ≈ 0.07 for single pursuit. Team synergy over independent planners is negative or zero in
  every cell (no cooperation detected).
- **The optimised parameters do not transfer to 7 pursuers.** They were tuned on teams of 3 and 5; with 7, the
  defaults score higher (0.405 / 0.430), with CIs including 0.
- **Overall:** the best strategy found is a simple per-pursuer rule: get ahead of the evader and block the lane it is
  predicted to take.
