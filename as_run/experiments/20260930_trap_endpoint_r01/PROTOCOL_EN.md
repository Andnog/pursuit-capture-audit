# Protocol — direct trapping endpoint r01 (A-84, option C)

Frozen before any episode. Approved by the Research lead (option C: a direct, observable trapping endpoint as the
primary outcome; the A-72 certificate is kept only as a training/diagnostic signal after it failed the A-83 audit).

Setting as pilot r03: SUMO, legal control interface, maps adelaide_cbd, toronto_downtown, washington_downtown
(TRAINING), 3 pursuers, evader AVOIDANT at 1.5×, sigma 0.5. **Fresh scenarios**: salt `PE4`, 60 per map = 180, one
SUMO seed each (9500 + index). Full 300 s episodes; no early stop at the certificate or at capture.

Policies: cut heuristic, individual heuristic, random-over-gates, and the four r03 final checkpoints (T seeds 1–2,
U seeds 1–2), greedy. No training.

Endpoints, evaluated at the 1 s controller steps:
- **immobilised**: evader ≤ 0.5 m/s for ≥ 10 s continuously with, at every step, a pursuer as its immediate leader
  within 15 m (SUMO leader gap) and no red/yellow signal within 30 m ahead;
- **contact capture**: the D06 predicate with A-57 alignment anywhere in the trace;
- **trapped (primary)** = immobilised or contact capture.

**Primary test (pass/fail):** paired Δ P(trapped) cut − individual over the 180 scenarios, bootstrap 95 % CI lower
bound > 0 ("coordination still matters under a direct endpoint").
Secondary (descriptive): each learned policy and random vs cut and vs individual; contact capture alone;
P(trapped | certificate fired) vs P(trapped | not fired); evader exits, collisions.
