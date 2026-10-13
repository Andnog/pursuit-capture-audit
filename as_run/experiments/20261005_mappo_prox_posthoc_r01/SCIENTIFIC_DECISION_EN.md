# Post hoc contrasts on the proximity-trained MAPPO test set (note to A-129)

**Status:** post hoc, not registered. Computed by `scripts/posthoc_mappo_prox_contrasts.py` from the sealed results
of `experiments/20261005_mappo_prox_r01`, which is not modified.

## Why

The registered summary of A-125 does not report the OC-selected imitation controller against PLB. On this test set
their rates are 0.440 and 0.397, which is larger than the difference seen in A-116 and has to be reported.

## Result

- OC-selected MAPPO (an imitation checkpoint that holds each decision for 3 s) minus PLB: **+0.043**, family 95 %
  [0.016, 0.071], city → family [0.001, 0.092], on 273 families.
- PLB − pursuit: +0.123 [0.087, 0.159] under OC (city → family [0.075, 0.170]); −0.013 [−0.025, −0.004] under the
  5 m rule (city → family [−0.029, −0.003]).
- Final proximity-trained policies minus pursuit, OC: +0.003 [−0.009, 0.015] and +0.007 [−0.005, 0.018].

## Consequence for the manuscript

The same kind of controller has now been compared with PLB on four test sets:

| Test set | Imitation MAPPO (MLP) − PLB | Registered |
|---|---|---|
| First MAPPO study, own test | +0.047, interval above zero | yes (met) |
| Held-out TEST cities | −0.009 [−0.048, 0.030] | yes (secondary) |
| MAPPO-v2 test | +0.025, 97.5 % [−0.011, 0.059] | yes (not met) |
| This test set | +0.043 [0.016, 0.071] | no (post hoc) |

The statement "no advantage of the learned controllers over the planner was detected" is therefore too strong and is
replaced. What the evidence supports:
- policy-gradient fine-tuning lowered capture in every run and was discarded, so no gain comes from reinforcement
  learning;
- the retained controllers are imitation checkpoints, and their difference from PLB ranges from −0.009 to +0.047,
  with intervals above zero in two of four test sets, one of them post hoc;
- a registered test of one candidate cause, holding decisions for 3 s, was not confirmed (+0.010 [−0.012, 0.033]).

The cause of the small difference is not established.
