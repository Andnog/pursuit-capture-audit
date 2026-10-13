# MAPPO-v4: the learning block repeated with the corrected training loop (A-143; design fixed in A-139)

**Registered before launch, 6 October 2026.** The design below was fixed in A-139 on 5 October, before the decision to
run it and before any result of the corrected loop existed.

**Research lead's decision.** On 6 October the Research lead was asked whether to retrain the learning block with the
corrected code, with its cost (about eight hours of computation) and the design fixed in A-139, and answered "Si".
This reopens learning for this study only.

## Why

The fifth independent review found that the training loop shared by every learning study, MAPPO-v3 included,

- trained the decision taken at the end of an episode, which has no future inside it: at the 300 s horizon whenever
  the objective was not reached, and at the capture instant when it fell on a 3 s decision tick (F5-1);
- applied the collision penalty from an episode-level flag, so that a collision after the cut would penalise a
  finished prefix (F5-1);
- cut training episodes at an instant computed by a helper that did not reset when a pursuer was absent (F5-2);
- kept a log that cannot reconstruct the denominators and events of training (F5-6).

A-142 measured the first of these on the batches that can be replayed (0.64 % of trained decisions, in 40 % of the
episodes) and did not measure its effect on the trained policies. Only a repetition can.

## What is identical to MAPPO-v3 (A-133)

- Controller `native/mappo_ambush_v3.py` (critic state recorded before the step's choices; sampling seeded per
  episode; sequential actor) and the PLB parameters it uses (c2_15).
- Imitation starts: the four stored checkpoints of A-116; the script refuses to start if one is not its imitation
  start.
- Arms, heads, seeds and order: `W_mlp` (critic warm-up of 256 sampled episodes, then fine-tuning), `P_mlp`
  (proximity reward, fixed 2,048 episodes, no early stop), `F_mlp`, `F_kan`; seeds 1 and 2; order W, P, F.
- Hyperparameters: learning rate 3e-4, entropy 0.01, clip 0.2, 4 epochs, 64 attempted episodes per update,
  GAE (0.99, 0.95), minibatches of 512 agent decisions, gradient clipping 0.5; warm-up 10 epochs at 1e-3.
- Validation and breakers: every 512 attempted episodes on 192 scenarios; for F and W at least 1,536 and at most
  4,096 attempted episodes, patience 4, minimum gain 0.02 on the two-point moving average.
- **Training scenarios, SUMO seeds and sampling seeds** (salts `PT23…`) and **validation scenarios** (salt `PV23`).
  The first batch of every run is therefore the batch that MAPPO-v3 sampled, and the validation value of every
  imitation start must equal the one MAPPO-v3 logged.
- Evaluation: greedy; every episode scored under OC, body gap ≤ 5 m and centre distance ≤ 5 m.
- Budgets are counted in attempted episodes, as in MAPPO-v3. The ledger gives the valid and used ones.

## What differs

1. **Transitions** (`rl/transitions.py`). A decision is trained only if it is taken strictly before the end of the
   trained interval (objective reached, horizon, or evader exit). A decision at or after the end is a terminal
   observation: recorded, never trained. The +1 of the objective goes to the transition in whose interval the event
   occurs.
2. **Time cost** proportional to the duration of the interval: −0.005 × duration / 3 s. A full interval costs what a
   decision cost before; the interval cut short by the event or by an evader exit costs less.
3. **Collision penalty** applied once, to the transition in which the first collision inside the trained interval
   occurred. Collisions after the end or before the first decision are recorded with their time and not penalised.
4. **Capture instant** from `evaluation/capture_time.earliest_capture`.
5. **Unresolved episodes.** An episode whose trace is irregular or contains an invalid value, or for which the
   extractor and the engine's judge disagree, is excluded from training and from every rate, like a placement
   failure, and is counted by reason. None is expected.
6. **Ledger.** One row per attempted episode (training, warm-up and validation), counts per update, statistics
   averaged over every minibatch, and the weights of every iteration.
7. **Test scenarios are new** (salt `PE24`): 7 non-TEST cities × 20 scenarios × 2 SUMO seeds × AVOIDANT/RANDOM ×
   teams 3/5/7 = **1,680 scheduled episodes per policy**. Policies: PLB, pursuit, the four imitation starts, the
   selected and final policy of every F and W run, the final policies of P. A selected checkpoint that is its own
   start is not run twice.

Nothing else differs. Given the rewards of the earlier contract, the update of this loop reproduces the earlier
update exactly (`tests/test_mappo_v4.py::TestUpdate`).

## Primaries (those of A-133)

- **Primary 1.** Arm W: selected checkpoint minus its imitation start, OC, averaged over the two seeds per cell;
  family-clustered 95 % lower bound > 0. If the breaker keeps the start, the difference is zero and the primary is
  not met.
- **Primary 2.** (Body-gap proximity − OC) of the final P policies minus the same gap for their imitation starts,
  averaged over seeds per cell; family-clustered 95 % lower bound > 0.

## Secondary and descriptive

Primary 1's contrast for arm F (MLP, KAN); final minus start for every arm and run; validation curves; W against F;
learned controllers against PLB; PLB against pursuit under each endpoint; the ledger summary (attempted, failed,
valid, used, exclusions, end reasons, timed collisions) and the incidence of what the earlier contract would have
done with the same episodes.

## Integrity checks fixed now (reported whatever they show; they do not stop the run)

- The validation value of every imitation start equals the one MAPPO-v3 logged (same weights, same scenarios):
  0.4737 for the MLP start under OC, 0.9368 under proximity, 0.4684 and 0.4632 for the two KAN starts.
- The first batch of every run has the success, OC and proximity counts of
  `experiments/20261005_v3_first_batch_reconstruction_r01`.
- The hashes of `inputs.json` are unchanged at the end.

## Reading fixed in advance

- MAPPO-v3 is not replaced. Both studies are reported, and MAPPO-v3 stays labelled as trained with a loop that had
  the two defects.
- A difference between MAPPO-v3 and MAPPO-v4 is not attributed to a cause: the two differ by the whole bundle above,
  their test scenarios differ, and two seeds do not estimate the variability between training runs.
- If Primary 1 is met, the claim is a validated gain of fine-tuning over imitation for arm W at this budget. If it is
  not met, the claim is that no validated gain was obtained with the corrected loop either. A contrast of final
  policies with an interval above zero is a secondary result and is not called a validated improvement.
- If Primary 2 is met, the claim concerns these proximity-trained policies and this learner. If not, the article
  keeps making no claim about what proximity rewards do to a learner.
- A difference that is not detected is not a demonstration of equivalence.
- The run is completed whatever the interim logs show. Placement failures are not replaced. Any deviation is written
  to `DEVIATIONS_EN.md` in this package.

## Execution

`scripts/train_mappo_v4.py --package experiments/20261006_mappo_v4_r01 --budget-min 25 --workers 9`, relaunched until
the log shows `"stage": "done"`. MAPPO-v3 used 8 workers; the number of workers enters no result (an episode is
determined by its scenario, SUMO seed, weights and sampling seed, and results are collected in task order).

Before registration the script was executed end to end outside the evidence tree with a reduced configuration and
**salts of its own** (`SMT24`, `SMV24`, `SME24`), so no registered training, validation or test scenario was touched.
Nothing was tuned on it.

**Label.** The docstring of `scripts/train_mappo_v4.py` says "A-139, pre-registered": A-139 fixed the design; A-143
records the decision to run it.
