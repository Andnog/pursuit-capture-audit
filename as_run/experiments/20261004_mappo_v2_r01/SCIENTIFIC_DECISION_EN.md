# Scientific decision — MAPPO v2 r01 (A-116)

Corrected design:
- all 16 city × setting pairs;
- OC objective, with episodes truncated at capture;
- faithful teacher (6.1 % of planner blocks unrepresentable and excluded from imitation);
- two seeds per head;
- unit-tested update.

## Training

| Run | Validation after BC | Validations every 512 episodes | Stop | Kept checkpoint |
|---|---|---|---|---|
| MLP s1 | 0.371 | 0.344, 0.280, 0.215, 0.199 | breaker at 2,048 | BC |
| KAN s1 | 0.355 | 0.355, 0.317, 0.247, 0.199 | breaker at 2,048 | BC |
| MLP s2 | 0.371 | 0.333, 0.328, 0.258, 0.220 | breaker at 2,048 | BC |
| KAN s2 | 0.360 | 0.355, 0.328, 0.231, 0.199 | breaker at 2,048 | BC |

Policy-gradient fine-tuning degraded validation capture in all four runs, as in A-105. With the sampler and objective
corrected and two seeds per head, the degradation replicates. The validation references were faithful teacher 0.344
and planner 0.355.

## Test

Salt PE17, seven non-TEST cities, AVOIDANT/RANDOM, teams 3/5/7. 15,120 scheduled episodes, with 432 placement failures
(48 per method, identical across methods). 8 collisions, one per method except the planner.

| Method | OC capture |
|---|---|
| PLB planner | 0.387 [0.357, 0.417] |
| Faithful teacher (PLB, 3-s decisions) | 0.411 |
| MAPPO-v2 MLP s1 / s2 | 0.414 / 0.411 |
| MAPPO-v2 KAN s1 / s2 | 0.415 / 0.403 |
| MAPPO A-105 MLP / KAN | 0.428 / 0.430 |
| Pursuit | 0.269 |

**Primary NOT PASSED** (97.5 %, family-clustered; best-validation checkpoint per head):
- MLP − PLB +0.025 [−0.011, 0.059];
- KAN − PLB +0.017 [−0.015, 0.048].

Secondary:
- v2 − teacher: MLP +0.001, KAN −0.007 (n.s.);
- KAN − MLP: −0.008 (n.s.);
- v2 − A-105: MLP −0.017 [−0.035, 0.001], KAN −0.027 [−0.044, −0.010];
- v2 − pursuit: +0.13 to +0.14.

## Reading

With the corrected design, learned controllers equal the planner they imitate (within ±0.06), and policy-gradient
fine-tuning never improved on imitation. No improvement from RL was detected for these controllers and this budget:
2,048 episodes per run, 2 seeds per head. This does not show that learning cannot help. KAN and MLP actors do not
differ.
