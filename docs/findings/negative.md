# What did not help

Negative results are part of the record, with the same audits as the positive ones.

## Learning: no validated gain over imitation

A learned controller lets each pursuer choose a blocking lane, chase or stay every 3 s. It is cloned from
predictive lane blocking and then fine-tuned by multi-agent reinforcement learning, with operational capture as
the reward. It is our own adaptation, not a published method run as released.

Fine-tuning gave no validated gain, in three successive implementations:

1. In the first, fine-tuning lowered validation capture in all four runs. An audit then found that its critic
   received a state that depended on the actions it was meant to judge.
2. With that corrected, the decline did not recur, and no gain appeared either.
3. A further audit found two defects in the training loop that both shared: the last decision of an episode was
   trained although it has no future inside the episode, and the collision penalty came from a flag of the whole
   episode. With both corrected, and the registered study repeated with the same arms, seeds and budgets, the
   outcome did not change: on 22 316 fresh episodes the final policies differ from their imitation starts by
   +0.011 [−0.005, 0.026], 0.000 [−0.012, 0.013] and +0.010 [−0.001, 0.021] in the three arms.

The imitation controllers themselves do not lag the planner that they copy: they differ from it by −0.009 to
+0.047 across six test sets. So the negative result is specific: for this controller and these budgets,
reinforcement learning did not improve on the imitation of the planner. It is not evidence that learned controllers
cannot match or exceed a planner; richer action spaces, more exploration, longer training or adversarial evaders
may change it.

Some of the defects were found after results had been reported. Negative results about learning need the same
audit as positive ones.

## An earlier claim that we withdrew

An earlier version of this study reported that a controller trained with the 5 m rule as its reward lost 16 points
of operational capture while its proximity score did not change. With corrected training code the loss did not
recur: no detected change in operational capture (−0.004 [−0.014, 0.007]) and no detected widening of the gap
between the endpoints (+0.003 [−0.008, 0.014]). We make no claim about what proximity rewards do to a learner.

## A better predictor, faster pursuers

An oracle that knows the evader's decision function predicts its next turn with 95–98 % accuracy, against about
50 % for the predictor in use. It changes capture by +0.03 to +0.04, with intervals that include zero. Pursuers
1.1 or 1.2 times faster change capture by −0.07 to +0.03. Neither result establishes equivalence; neither
indicates a large gain.

## Kolmogorov–Arnold models

Fitted to predict capture from six features of the start of an episode, a Kolmogorov–Arnold network reached an
area under the curve of 0.597 on TEST, against 0.645 to 0.647 for a spline-additive model, a multilayer perceptron
and a logistic regression. No advantage was detected; this is exploratory and post hoc, and it does not establish
equality.
