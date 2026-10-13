# Scientific decision — robustness study r01 (A-92)

22,980 episodes, executed in seven resumable chunks (DEVIATIONS_EN.md). 534 failed scenario generation (the team could
not be placed, mostly with 5 pursuers) and are excluded pairwise. 1 collision (block T, background traffic). TEST
closed. Primary endpoint: D06 contact capture. Rates are seed-averaged (3 SUMO seeds), with bootstrap over 135–138
scenarios per cell.

## R1 — Is there cooperation? (team vs independent pursuers, 1 − Π(1 − p_i))

| Cell | Team | Single (mean) | Independent union | Synergy [95 % CI] | Bonferroni CI |
|---|---|---|---|---|---|
| RANDOM, 2 | 0.176 | 0.116 | 0.192 | −0.015 [−0.049, 0.019] | [−0.064, 0.033] |
| RANDOM, 3 | 0.275 | 0.122 | 0.246 | +0.029 [−0.011, 0.073] | [−0.029, 0.094] |
| RANDOM, 5 | 0.345 | 0.115 | 0.324 | +0.022 [−0.026, 0.072] | [−0.047, 0.096] |
| AVOIDANT, 2 | 0.102 | 0.068 | 0.127 | −0.025 [−0.071, 0.018] | [−0.089, 0.035] |
| AVOIDANT, 3 | 0.141 | 0.073 | 0.192 | −0.051 [−0.115, 0.011] | [−0.142, 0.040] |
| AVOIDANT, 5 | 0.206 | 0.068 | 0.259 | −0.053 [−0.122, 0.015] | [−0.152, 0.044] |
| OPTIMAL, 2 | 0.147 | 0.121 | 0.199 | −0.051 [−0.118, 0.007] | [−0.140, 0.037] |
| OPTIMAL, 3 | 0.180 | 0.123 | 0.284 | −0.104 [−0.183, −0.027] | [−0.217, 0.007] |
| OPTIMAL, 5 | 0.156 | 0.116 | 0.323 | **−0.168** [−0.252, −0.086] | **[−0.289, −0.052]** |
| AVOIDANT, 3, traffic | 0.129 | 0.082 | 0.208 | −0.079 [−0.139, −0.019] | [−0.170, 0.005] |

**No cell shows cooperation** (no Bonferroni lower bound > 0). Teams do capture more as they grow (RANDOM 0.18 → 0.35;
AVOIDANT 0.10 → 0.21), but no more than independent pursuers would. Against the smartest evader, large teams do
significantly worse than independent pursuers (interference).

## R2 — Pursuit vs cut

Indistinguishable against RANDOM and AVOIDANT evaders. Pursuit is better against OPTIMAL_ESCAPE with teams of 2–3:
+0.078 [0.012, 0.145] and +0.096 [0.022, 0.173].

## R3 — Lenient endpoint inflation

| Setting | Body gap ≤ 5 m | D06 capture |
|---|---|---|
| Real cities, pursuit team | 0.85–0.96 | 0.10–0.35 (3–9×) |
| Literature-like grids, pursuit | 0.631 | 0.364 |
| Literature-like grids, cut | 1.000 | 0.650 |

The centre-distance ≤ 5 m rule gives 0.242 (pursuit) and 0.806 (cut) on the grids. This shows that the rule's
meaning depends on how distance is measured.

## R4 — Background traffic (≈ 300 cars per city)

No effect on the pursuit team's D06 rate: −0.012 [−0.056, 0.029].

## Literature-like regime (controlled grids, team 5, RANDOM evader)

Here gate coordination clearly helps: cut − pursuit **+0.286 [0.192, 0.378]**.
- C2 6×6: cut 0.728 vs pursuit 0.394.
- C3 9×9: cut 0.572 vs pursuit 0.333.

The regime of small, closed grids with many pursuers is where exit-based coordination pays off. On real downtowns it
does not. Single-pursuer runs were not part of block L, so synergy is not tested there.

## Consequences for the manuscript

- "No cooperation beyond independent chances" holds across 3 evader levels, 3 team sizes, 7 cities, 3 seeds and with
  background traffic.
- Coordination by exits is regime-dependent: strong on small closed grids, absent on real city networks.
- Lenient endpoints inflate success 3–9× on real cities.
