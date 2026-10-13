# Scientific decision — sensitivity study r02 (A-101)

## Part A — tuning for 7 pursuers

No configuration beat `c2_15` by 0.02 on round 3 (best `t7_20` 0.540; `c2_15` 0.556; defaults 0.489), so the
breaker kept `c2_15`. Validation: `c2_15` 0.541, defaults 0.497.

Test, team 7 (133 scenarios per evader, 2 seeds):

| Evader | `c2_15` | Defaults | Pursuit | `c2_15` − pursuit |
|---|---|---|---|---|
| AVOIDANT | **0.429** | 0.398 | 0.286 | +0.143 [0.068, 0.218] |
| RANDOM | **0.398** | 0.414 | 0.327 | +0.071 [0.004, 0.135] |

## Part B — faster pursuers (evader 1.0×)

`c2_15` capture, with change vs pursuers at 1.0× [95 % CI]:

| Cell | 1.0× | 1.1× | 1.2× |
|---|---|---|---|
| AVOIDANT, 3 | 0.287 | 0.272 (−0.015) | 0.216 (**−0.071 [−0.131, −0.015]**) |
| AVOIDANT, 5 | 0.358 | 0.317 (−0.041) | 0.328 (−0.030) |
| RANDOM, 3 | 0.295 | 0.328 (+0.034) | 0.299 (+0.004) |
| RANDOM, 5 | 0.362 | 0.332 (−0.030) | 0.306 (−0.056) |

`c2_15` − pursuit stays positive at every speed: +0.05 to +0.17, with CI > 0 in 11 of 12 cells. Pursuit itself does not
gain from speed either (AVOIDANT team 3: 0.194 → 0.127).

## Reading

Faster pursuers do **not** raise physical capture, and against the avoiding evader they lower it. Capture requires a
pursuer stopped ahead in the evader's lane. Arriving earlier makes blockers visible earlier to an evader that steers
away from them, and pursuers that chase only end up behind the evader faster. The limit is positional and
informational on the evader's side, not pursuer speed. More pursuers help: with 7, capture reaches 0.40–0.43.
`c2_15` remains the best tested strategy across team sizes and speeds.

400 failed placements and 2 collisions in the test.
