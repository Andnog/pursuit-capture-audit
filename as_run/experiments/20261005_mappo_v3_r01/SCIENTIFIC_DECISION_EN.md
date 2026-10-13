# Scientific decision — MAPPO-v3: the learning block repeated with a corrected implementation (A-133, R4-A)

**Status:** complete. **Primary 1 not met. Primary 2 not met.** The decline under fine-tuning reported by the earlier
studies did not recur.

## What was run

Fine-tuning from the four stored imitation checkpoints of A-116 with the corrected controller
(`native/mappo_ambush_v3.py`): the critic's state is recorded before the actions of the step, and sampling is seeded
per episode. Eight runs of 2,048 episodes each:

| Arm | Reward | Runs | Stop |
|---|---|---|---|
| W: fixes and critic warm-up (256 episodes) | OC | MLP, seeds 1 and 2 | breaker at 2,048; imitation start kept |
| F: fixes only | OC | MLP and KAN, seeds 1 and 2 | breaker at 2,048; imitation start kept |
| P: fixes, proximity reward | first body gap ≤ 5 m | MLP, seeds 1 and 2 | fixed budget of 2,048 |

Test on fresh scenarios (salt PE23, seven non-TEST cities): 23,520 episodes scheduled for 14 policies; 616 failed
scenario placement, in 44 conditions that fail identically for all 14; 22,904 completed (1,636 per policy; 273
families). No collision. All policies evaluated greedily.

## Training (validation on 190 scenarios every 512 episodes)

| Run | Start | 512 | 1,024 | 1,536 | 2,048 |
|---|---|---|---|---|---|
| W MLP s1 | 0.474 | 0.474 | 0.474 | 0.468 | 0.468 |
| W MLP s2 | 0.474 | 0.489 | 0.479 | 0.479 | 0.463 |
| F MLP s1 | 0.474 | 0.479 | 0.484 | 0.479 | 0.474 |
| F MLP s2 | 0.474 | 0.479 | 0.463 | 0.468 | 0.468 |
| F KAN s1 | 0.468 | 0.479 | 0.463 | 0.468 | 0.484 |
| F KAN s2 | 0.463 | 0.474 | 0.479 | 0.458 | 0.463 |
| P MLP s1 (proximity) | 0.937 | 0.937 | 0.937 | 0.932 | 0.932 |
| P MLP s2 (proximity) | 0.937 | 0.932 | 0.932 | 0.932 | 0.932 |

No run reached the registered gain of 0.02 on the two-point moving average, so every selected checkpoint is its
imitation start. In A-116, with the defective critic, the same schedule took validation from 0.36–0.37 to 0.20–0.22.

## Test (family-clustered 95 % intervals)

| Policy | OC | Body gap ≤ 5 m | Centre ≤ 5 m |
|---|---|---|---|
| PLB | 0.400 | 0.921 | 0.823 |
| Pursuit | 0.282 | 0.925 | 0.861 |
| Imitation start, MLP (two seeds) | 0.418 | 0.918 | 0.829 |
| Imitation start, KAN (two seeds) | 0.422 | 0.920 | 0.830 |
| Final, arm W, MLP | 0.433 | 0.919 | 0.828 |
| Final, arm F, MLP | 0.427 | 0.918 | 0.822 |
| Final, arm F, KAN | 0.424 | 0.919 | 0.829 |
| Final, arm P (proximity reward), MLP | 0.426 | 0.918 | 0.827 |

- **Primary 1** (arm W, selected checkpoint minus its imitation start, OC): **0.000**, because the breaker kept the
  start in both seeds. Not met: fine-tuning produced no validated improvement.
- **Primary 2** ((proximity − OC) of the final proximity-trained policies minus the same gap for their starts):
  **−0.009 [−0.022, 0.005]**. Not met: with the corrected learner, training on proximity did not widen the gap.
- Final minus start, OC (secondary): arm W +0.015 [0.003, 0.028] (seeds +0.017 [0.004, 0.031] and +0.013
  [−0.005, 0.033]); arm F MLP +0.009 [−0.005, 0.025] (seeds +0.026 [0.006, 0.048] and −0.007 [−0.030, 0.015]);
  arm F KAN +0.003 [−0.011, 0.017]; arm P +0.009 [−0.005, 0.022]. W minus F, final policies: +0.006 [−0.007, 0.019].
- Final proximity-trained policies: proximity success minus start 0.000 [−0.002, 0.002]; OC minus pursuit +0.145
  [0.107, 0.183].
- Against PLB (OC): imitation start MLP +0.017 [−0.014, 0.049], KAN +0.021 [−0.009, 0.051]; final arm W +0.033
  [0.003, 0.063]; final arm F MLP +0.027 [−0.004, 0.059]; final arm F KAN +0.024 [−0.006, 0.054].
- Hand-written controllers: PLB − pursuit is +0.119 [0.076, 0.160] under OC, −0.004 [−0.013, 0.004] under the
  body-gap rule and −0.038 [−0.059, −0.020] under the centre-distance rule.

## Reading

1. **The earlier decline was produced by the defect.** With the critic input and the sampling corrected, and
   nothing else changed (arm F), validation capture stayed within 0.02 of its start in every run and the final
   policies are not below their starts on fresh scenarios. The statement that fine-tuning degrades these controllers
   is withdrawn for all earlier studies.
2. **No validated gain from fine-tuning.** The registered criterion was not reached in any run. On fresh scenarios
   the final policies of arm W are 1.5 points above their starts with an interval above zero; this is a secondary
   contrast, small, and seen clearly in one of two seeds of arm F. It is reported, not claimed as an improvement.
3. **Proximity training did not lower OC.** The loss of 16 points reported in A-125/A-129 was obtained with the
   defective critic. With the corrected learner the proximity-trained policies keep their OC (+0.009
   [−0.005, 0.022]). The A-129 reading "the proximity endpoint does not register a 16-point loss" remains true of
   those two stored policies, but they are no longer evidence of what proximity rewards do, and the manuscript no
   longer presents them that way.
4. **The endpoint and the ranking of controllers.** The 12-point advantage of PLB over pursuit under OC is not
   visible under the 5 m body-gap rule (−0.004 here, −0.013 [−0.025, −0.004] on the A-125 test set) and is reversed
   under the centre-distance rule on both test sets. "Reverses the ranking" is correct for the centre-distance rule
   and for one of two test sets under the body-gap rule; the manuscript is worded accordingly.

## Limits

- Two seeds per arm describe these runs; they do not estimate variability between training runs.
- The imitation policies are nearly deterministic (mean policy entropy about 0.02 nat in sampled training
  episodes), so fine-tuning explored little at the registered entropy coefficient. The learner was not tuned
  further. The result is "no validated gain at this budget and these settings", not "learning cannot help".
- Differences that are not detected are not demonstrations of equivalence.
- The actor is sequential (agents decide in a fixed order and see earlier choices of the step); it is not a
  simultaneous decentralised MAPPO.

## Record

- Registered in A-133 before any run. The count "840 episodes per policy" in A-133 and in the protocol was an
  arithmetic error; the registered design gives 1,680, corrected in the amendments before any test result was read.
- An end-to-end check with a reduced configuration ran outside the evidence tree before the study; its 16 validation
  and 196 test episodes are a subset of the registered sets. Nothing was tuned on it.
- The run was stopped once after 768 training episodes of the first run and resumed with 10 workers instead of 8;
  the interrupted iteration was repeated from the saved state. Six resumable blocks in total.
- Sources were not modified while workers ran. 427 unit tests pass, including tests that reproduce both defects in
  the legacy controller and check their absence in the corrected one.
