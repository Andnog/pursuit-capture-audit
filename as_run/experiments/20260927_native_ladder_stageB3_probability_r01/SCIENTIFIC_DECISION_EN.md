# Decision — native ladder, stage B3 (coordination in probability)

**Rule not met: no map passes.** Only 14 of 56 scenarios yielded a plan whose deterministic capture needs the helper;
most maps have fewer than the 4 contributing scenarios the rule requires, and intervals are wide.

| Map : level | scenarios contributing | P(capture) with helper | helper removed | Δ | 95 % CI |
|---|---|---|---|---|---|
| C1 4×4 : AVOIDANT | 2 | 1.00 | 0.68 | +0.33 | [0.00, 0.65] |
| C2 6×6 : AVOIDANT | 2 | 0.62 | 0.47 | +0.15 | [−0.10, 0.40] |
| C3 9×9 : AVOIDANT | 1 | 0.00 | 0.00 | 0.00 | — |
| C4 10×4 : AVOIDANT | 3 | 0.48 | 0.53 | −0.05 | [−0.50, 0.45] |
| C5 spider : AVOIDANT | 4 | 0.28 | 0.21 | +0.06 | [−0.10, 0.28] |
| C2 : RANDOM | 1 | 0.85 | 0.50 | +0.35 | — |
| C2 : OPTIMAL_ESCAPE | 1 | 1.00 | 0.45 | +0.55 | — |

Estimated on 20 fresh seeds per scenario (sigma 0.5). Across the 14 contributing scenarios the mean Δ is about
+0.14 (AVOIDANT only, 12 scenarios: about +0.09): the helper raises capture probability on average, with large
scenario-to-scenario variation and some negative cases (C4 s0: 0/20 with vs 10/20 without).

**Reading.** The obstacle is now statistical power, not existence: the deterministic screen finds a helper-needing
plan in only 1 of 4 scenarios, so each map contributes few estimates.
