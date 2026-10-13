# Scientific decision — commitment study r01 (A-106)

6,720 episodes on fresh scenarios (salt PE14, 7 cities, teams 3/5/7, AVOIDANT/RANDOM, D06); 208 placement failures.

| commit_s | D06 [95 % CI] | − commit 1 s |
|---|---|---|
| 1 s (A-99 planner) | 0.408 [0.378, 0.440] | — |
| 2 s | 0.437 [0.406, 0.469] | +0.029 [0.008, 0.050] |
| 3 s | 0.419 [0.389, 0.450] | **+0.010 [−0.012, 0.033]** |
| 5 s | 0.429 [0.398, 0.461] | +0.020 [−0.002, 0.043] |

**Primary: NOT PASSED.** Commit 3 s − 1 s = +0.010, CI includes 0.

By cell, 3 s − 1 s runs from −0.051 (AVOIDANT, 3) to +0.048 (RANDOM, 7; the only CI above 0).

**Reading.**
- The ≈ 4-point gap seen incidentally in A-105 (teacher mode vs planner) does not replicate as a commitment effect.
  Holding orders gives at most a small gain (+1 to +3 points; 2 s is the only significant secondary contrast). It
  helps large teams and hurts small teams against the avoiding evader.
- The A-105 gap therefore mixed a small commitment effect with differences between the controllers and with
  scenario-set variability. Note that the same planner scores 0.365 on PE13 and 0.408 on PE14: between-test-set
  variation of ≈ 4 points.
- No commitment claim will be made.
