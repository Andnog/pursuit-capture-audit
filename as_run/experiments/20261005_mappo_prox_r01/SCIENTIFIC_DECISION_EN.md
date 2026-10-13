# Scientific decision — MAPPO trained on the proximity endpoint (A-125)

**Status:** complete. Primary **met**.

## What was run

The MAPPO controller of A-116 (MLP actor), from the same imitation start, fine-tuned for a fixed 2,048 episodes per
seed (two seeds, no early stop) with the literature's endpoint as reward: +1 at the first instant a pursuer is within
5 m (body gap) of the evader, with the episode truncated there.

Test on fresh scenarios (salt PE19, seven non-TEST cities, AVOIDANT/RANDOM, teams 3/5/7, 20 scenarios × 2 SUMO seeds).
11,760 episodes were scheduled for seven controllers; 294 failed scenario placement, in 42 conditions that fail
identically for all seven; 11,466 completed (1,638 per controller; 273 families, 819 cells). No collision.

## Results

| Controller | OC | Body gap ≤ 5 m | Centre ≤ 5 m |
|---|---|---|---|
| MAPPO selected on OC (A-116) | 0.440 | 0.925 | 0.860 |
| PLB | 0.397 | 0.921 | 0.840 |
| MAPPO trained on proximity, final policies | 0.278 | 0.933 | 0.858 |
| Pursuit | 0.274 | 0.934 | 0.861 |

- **Primary** (registered): (proximity − OC) of the final proximity-trained policies minus the same gap for the
  OC-selected controller = **+0.170**, family-clustered 95 % interval [0.135, 0.205]. Lower bound > 0: met.
- OC: proximity-trained − OC-selected = −0.162 [−0.197, −0.127]; − PLB = −0.118 [−0.153, −0.085]. Per seed:
  −0.164 and −0.160.
- Proximity (body gap): proximity-trained − OC-selected = +0.008 [−0.001, 0.020].
- Hand-written controllers: PLB − pursuit is **+0.123** [0.088, 0.160] under OC and **−0.013** [−0.025, −0.004]
  under the 5 m rule (−0.021 [−0.040, −0.002] with centre distance). The endpoint reverses their order.

## Reading

1. After 2,048 episodes of training on proximity, the controller's operational capture fell by 16 points, to the
   level of plain pursuit, while its proximity success did not change detectably. Proximity validation stayed at
   0.91–0.92 throughout training.
2. **This is not evidence that the proximity reward caused the loss.** In A-116 the same fine-tuning with OC as
   reward also lowered validation OC (0.36–0.37 to 0.20–0.22); there the breaker, which monitors OC, kept the
   imitation checkpoint. The design here compares a selected checkpoint with final policies, as registered.
3. What the study shows is that the proximity endpoint does not register the loss. A study that trains, validates and
   reports on proximity would describe the two learned controllers as equivalent (0.933 against 0.925), and would
   rank pursuit above PLB.

## Notes for the record

- The best-validation checkpoints of both proximity runs are their imitation checkpoints (best validation equals the
  value after behaviour cloning), because proximity success was saturated from the start. The registered primary
  therefore uses the final policies, as fixed in the A-125 clarification before any run. The secondary on the
  best-validation checkpoint is +0.007 [−0.010, 0.024].
- The best-validation checkpoint of seed 2 gives the same outcome as the OC-selected controller in all 1,638
  episodes: it is the same imitation checkpoint (same demonstrations and seed).
- The proximity-trained controller is our own implementation of a learner rewarded by proximity. It is not a
  published method. The audit of a published environment is A-126.
- The run was executed in three resumable blocks.
