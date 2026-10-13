# Scientific decision — MAPPO for the multi-agent ambush r01 (A-103)

## Training

| | MLP, seed 1 | KAN, seed 1 |
|---|---|---|
| BC held-out accuracy on the teacher | 0.990 | 0.992 |
| Validation, BC checkpoint | 0.500 | 0.484 |
| Validation under MAPPO (512 → 2,048 episodes) | 0.479 → 0.436 → 0.330 → 0.314 | 0.463 → 0.404 → 0.314 → 0.324 |

Reference validation: planner 0.532; teacher mode 0.452.
- **MAPPO fine-tuning degraded both heads.** Policy entropy collapsed to ≈ 0.01–0.06. The run breakers stopped both
  heads at 2,048 episodes, and the global breaker skipped seeds 2–3.
- **The best checkpoints are therefore the BC (imitation) checkpoints.**

## Test

Salt PE13, 7 cities, 20 scenarios × 2 seeds, teams 3/5/7, D06. 10,080 episodes, 96 placement failures, re-run after a
harness defect (DEVIATIONS_EN.md).

| Policy | D06 [95 % CI] |
|---|---|
| Planner c2_15 (per-step re-planning) | 0.365 [0.335, 0.396] |
| Teacher mode (c2_15 decided every 3 s, orders held) | 0.403 [0.373, 0.434] |
| MAPPO-MLP, best = BC | 0.412 [0.382, 0.443] |
| MAPPO-KAN, best = BC | 0.417 [0.386, 0.447] |
| Pursuit | 0.254 |
| Random slot (control) | 0.135 |

**Primary: PASSED for both heads.** MAPPO − planner: MLP +0.047 [0.022, 0.072]; KAN +0.052 [0.028, 0.076].

**But the gain is not due to reinforcement learning.**
- MAPPO − teacher mode: MLP +0.009 [−0.008, 0.026], KAN +0.014 [−0.001, 0.029]. The deployed policies are the
  imitation checkpoints, and their teacher already scores 0.403.
- The improvement over the planner comes from the multi-agent controller's structure: decisions every 3 s with
  orders held in between, instead of re-planning every second. This adds commitment, so blockers are not re-routed
  while driving.
- By cell, the gain is largest with 7 pursuers (+0.08 to +0.13, CI > 0) and negative for AVOIDANT with 3 pursuers
  (−0.054 [−0.109, −0.004]).

**Reading.**
- A standard multi-agent RL method (MAPPO, parameter sharing, centralised critic) imitated the planner almost
  perfectly, but its policy-gradient fine-tuning made it worse.
- The KAN actor matches the MLP actor.
- Incidental finding: committing to orders for 3 s improves the planner by ≈ 4 points (0.365 → 0.403). This is a
  design finding (decision cadence), not a learning result; it should be confirmed with a pre-registered planner-only
  test if used as a claim.
