# Scientific decision — MAPPO-v4: the learning block repeated with the corrected training loop (A-143)

**Run:** 6 October 2026, 07:05 to 15:56 local time, 9 workers, chunks of 25 minutes relaunched until the end. No
deviation from the protocol: no chunk failed, nothing was changed during the run, and the run was completed without
reading the test results before the end. Analysis: `scripts/analyse_mappo_v4.py` → `ANALYSIS.json`.

## Integrity checks fixed in the protocol

| Check | Result |
|---|---|
| Validation value of every imitation start equals the one MAPPO-v3 logged | 8 of 8 runs (90/190 for the MLP start under OC, 178/190 under proximity, 89/190 and 88/190 for the KAN starts) |
| First batch of every run has the counts of the reconstruction of MAPPO-v3's first batches | 8 of 8 runs |
| Source hashes of `inputs.json` unchanged at the end | 73 of 73 |
| Unresolved episodes (invalid trace, or judge and extractor in disagreement) | 0 in training, validation and test |

## Training ledger

- Fine-tuning: 16,384 attempted episodes, 358 placement failures, **16,026 valid, all used**; 970,931 transitions.
  Critic warm-up of arm W: 512 attempted, 503 valid. Validation: 7,680 episodes, 80 placement failures.
- Ends of the 16,529 valid sampled episodes: 8,869 by the training objective, 5,833 at the horizon, 1,827 by evader
  exit. **No collision** in any training, warm-up, validation or test episode.
- What the earlier contract would have done with these episodes: it would have trained 1,012,162 decisions, of
  which **6,281 (0.62 %) had no future inside the episode, in 6,281 episodes (38 %)**. In the runs rewarded on OC,
  5,747 episodes ended at the horizon and 315 of 5,140 captures (6.1 %) fell on a decision tick. The corrected loop
  trained none of those decisions.
- In 9 sampled episodes a vehicle was absent inside its record (92 frames in all), in one of them the pursuer that
  completes the capture. The earlier helper and the corrected extractor give the same capture instant in all 6,762
  captures of training and in all 8,521 of the test.
- Breakers: in the six runs rewarded on OC, validation capture stayed between 86 and 92 of 190 (start: 88 to 90); no
  run reached the registered gain of 0.02, and every selected checkpoint is its imitation start. The two proximity
  runs ran their fixed 2,048 attempts; validation proximity stayed at 177 or 178 of 190.

## Test (salt PE24, new scenarios)

23,520 scheduled episodes for 14 policies; 1,204 placement failures, in 86 conditions that fail identically for all
policies; **22,316 completed** (1,594 per policy; 267 families, 797 cells).

**Primary 1 — not met.** Arm W, selected checkpoint minus its imitation start, OC: 0.000 [0.000, 0.000]. The breaker
kept the start in both seeds.

**Primary 2 — not met.** Gap between body-gap proximity and OC of the final proximity-trained policies minus that of
their starts: +0.003 [−0.008, 0.014].

Secondary, family-clustered 95 % (OC unless stated):

| Contrast | MAPPO-v4 | MAPPO-v3, for reference |
|---|---|---|
| Final minus start, arm W (MLP) | +0.011 [−0.005, 0.026] | +0.015 [0.003, 0.028] |
| Final minus start, arm F (MLP) | 0.000 [−0.012, 0.013] | +0.009 [−0.005, 0.025] |
| Final minus start, arm F (KAN) | +0.010 [−0.001, 0.021] | +0.003 [−0.011, 0.017] |
| Final minus start, arm P (MLP) | −0.004 [−0.014, 0.007] | +0.009 [−0.005, 0.022] |
| Final W minus final F (MLP) | +0.010 [−0.002, 0.022] | +0.006 [−0.007, 0.019] |
| Imitation start (MLP) minus PLB | +0.017 [−0.012, 0.046] | +0.017 [−0.014, 0.049] |
| Imitation start (KAN) minus PLB | +0.011 [−0.016, 0.040] | +0.021 [−0.009, 0.051] |
| PLB minus pursuit, OC | +0.128 [0.084, 0.170] | +0.119 [0.076, 0.160] |
| PLB minus pursuit, body gap ≤ 5 m | −0.004 [−0.011, 0.003] | −0.004 [−0.013, 0.004] |
| PLB minus pursuit, centre ≤ 5 m | −0.021 [−0.038, −0.006] | −0.038 [−0.059, −0.020] |

Rates (OC / body gap ≤ 5 m / centre ≤ 5 m): PLB 0.376 / 0.893 / 0.815; pursuit 0.248 / 0.897 / 0.836; imitation
start MLP 0.392 / 0.896 / 0.821; KAN 0.387 / 0.896 / 0.823; final W 0.403 / 0.895 / 0.824; final F (MLP)
0.393 / 0.894 / 0.822; final F (KAN) 0.397 / 0.896 / 0.824; final P 0.389 / 0.895 / 0.822.

The two test sets differ (PE23 and PE24), so the columns are not paired.

## Decision, under the reading fixed in the protocol

1. **No validated gain from fine-tuning with the corrected loop either.** Primary 1 is not met; no contrast of final
   policies has an interval above zero. The interval of arm W that was above zero in MAPPO-v3 (+0.015) is not above
   zero here (+0.011 [−0.005, 0.026]); neither study claimed it as an improvement.
2. **No claim about proximity rewards.** Primary 2 is not met; the proximity-trained policies keep their OC
   (−0.004 [−0.014, 0.007]) and their proximity score.
3. **No deterioration.** Validation and test stay within about one point of the imitation starts in every arm.
4. **The conclusions of MAPPO-v3 are unchanged by the correction of the loop.** This is a statement about the two
   registered outcomes, not an equivalence: a difference that is not detected is not a demonstration of equivalence,
   two seeds per arm do not estimate the variability between training runs, and a difference between the two studies
   is not attributed to a cause.
5. **A third independent test set for the endpoint finding.** PLB minus pursuit is +0.128 under OC, −0.004 under the
   body-gap rule and −0.021 under the centre-distance rule, as on the two earlier sets.
6. MAPPO-v3 is not replaced. Both are reported; MAPPO-v3 stays labelled as trained with a loop that had the two
   defects.

## Limits

- Two seeds per arm; one budget; no hyperparameter was tuned. The sampled policies are nearly deterministic (mean
  entropy 0.02–0.03 nat), so fine-tuning explored little, as in MAPPO-v3.
- The corrected loop has unit tests for the cases the fifth review listed and a complete ledger. That is not a proof
  that no other defect exists.
- The test scenarios are new and the training and validation scenarios are those of MAPPO-v3, as registered.
