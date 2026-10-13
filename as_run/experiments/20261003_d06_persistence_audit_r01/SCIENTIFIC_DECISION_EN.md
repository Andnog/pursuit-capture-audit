# Scientific decision — D06 persistence audit r01 (A-108)

1,433 D06-positive episodes replayed twice (2,866 SUMO runs, 0 failures).

| | c2_15 planner | A-95 ambush | pursuit |
|---|---|---|---|
| D06 captures audited | 562 | 480 | 391 |
| Natural replay reproduces the sealed capture | 1.000 | 1.000 | 1.000 |
| **Escape within 60 s, pursuers frozen** | **0.000 [0, 0.007]** | **0.000 [0, 0.008]** | **0.000 [0, 0.010]** |
| Escape within 10 s, policy continues | 0.018 | 0.035 | 0.015 |
| Escape within 60 s, policy continues | 0.084 | 0.144 | 0.128 |
| Red/yellow signal within 40 m at capture | 0.020 | 0.027 | 0.031 |
| Another lane free of pursuers at capture | 0.016 | 0.015 | 0.020 |

Wilson 95 % intervals. Windows shorter than 60 s because of the 300 s horizon: 82 / 64 / 42 (no escape in any).

**Primary: PASSED for all three methods.** A D06 capture is a held capture: if the pursuers stay where they are, the
evader never moves more than 10 m in the next 60 s (0 of 1,433). Captures behind a vehicle that is only waiting at a
red light, or with a free adjacent lane, are rare (2–3 % and 1.5–2 %), and none of them escaped when frozen.

**Consequence rule: claims unchanged.** Persistent capture equals D06 capture in every test episode, so every A-99
estimate and interval is identical (c2_15 − pursuit +0.04 to +0.15 by cell, 5/6 cells CI > 0; c2_15 − A-95 pooled
+0.050 [0.023, 0.078]).

**Determinism.** All 1,433 sealed captures were reproduced exactly (same capture time) with the current sources, so
the source changes after A-99 (A-100 predictor options, A-101 pursuer speed, A-103 harness fix) did not alter the
behaviour of the audited controllers.

**Reading for the manuscript.** When the controllers keep running, 8–14 % of captured evaders are later released
because the planner moves the blocker on; an operational system would stop re-planning at capture. This is a
property of the controllers, not of the endpoint, and it is reported as such.
