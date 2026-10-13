# Findings — X03 (exploratory): the closed-loop evader diverges on what it reads, not on when

For the two factual situations N03 rejected in closed loop:

| Map | Split after edge | Evader on it: model / SUMO | Model's choice | SUMO's choice |
|---|---|---|---|---|
| toronto_downtown | 34545779#0 | 16.5 s / 16.4 s | 30327576#0 | -34545779#1 |
| washington_downtown | 297401519 | 38.8 s / 38.2 s | -1343949708#2 | 1343949707#0 |

The evaders arrive within 0.1–0.6 s of each other and still choose differently, long before the witness
(127.8 s, 259.7 s). Re-evaluating the policy at decision indices −1/0/+1 with the pursuer positions removed gives
the same choice at all three, so the divergence is **not** the decision-index-keyed sampling: it comes from the
**pursuer node positions** the evader reads. A pursuer a fraction of a second earlier or later is at a different
"current node" (the end of its edge, or the start of the next once inside a junction), which changes the
distance scores. The evader's input is a discontinuous function of time; the model search optimises constructions
without regard to it.

**Implication.** Native replication needs constructions robust to that discontinuity: e.g. accept a model
construction only if it survives perturbed evader decision times (±0.5 s) in the model itself, or give the evader
a continuous input (distance along the network instead of the node reached). The second changes D08's evader and
would be the Research lead's decision.
