# Scientific decision — ambush-planner study r01 (A-94)

6,720 episodes. 158 failed scenario placement and are excluded pairwise. 0 collisions. 7 cities, equal speeds, D06
primary, 2 seeds, 135–138 scenarios per cell.

| Cell | Ambush team | Pursuit team | Ambush − pursuit | Ambush single (mean) | Independent union | Synergy [95 %] | Bonferroni CI | Plan share |
|---|---|---|---|---|---|---|---|---|
| AVOIDANT, 3 | 0.246 | 0.180 | **+0.066 [0.029, 0.107]** | 0.109 | 0.256 | −0.009 [−0.072, 0.053] | [−0.090, 0.070] | 0.095 |
| AVOIDANT, 5 | **0.356** | 0.237 | **+0.119 [0.067, 0.174]** | 0.110 | 0.350 | +0.006 [−0.074, 0.086] | [−0.094, 0.110] | 0.183 |
| RANDOM, 3 | 0.275 | 0.236 | **+0.040 [0.011, 0.072]** | 0.110 | 0.208 | **+0.067 [0.025, 0.112]** | **[0.014, 0.125]** | 0.075 |
| RANDOM, 5 | 0.337 | 0.315 | +0.022 [−0.018, 0.062] | 0.112 | 0.266 | +0.071 [0.014, 0.128] | [0.000, 0.144] | 0.183 |

## S1 — Cooperation

**Detected in one cell:** RANDOM evader, team of 3. The 5-pursuer RANDOM cell is borderline (Bonferroni lower bound
0.000; the pre-registered rule requires > 0). Against the AVOIDANT evader, team capture equals the
independent-pursuer prediction. There, the planner's gain comes from better individual behaviour: a single pursuer
running the planner closes single-lane exits ahead of the evader, so single capture rises from ≈ 0.07 with pursuit to
0.11.

## S2 — Planner vs pursuit

The ambush planner beats pursuit in 3 of 4 cells. The largest gain is AVOIDANT with 5 pursuers: +0.119, which is
50 % more captures (0.356 vs 0.237).

## Mechanism

The rendered case `gifs/phoenix4_ambush_team3.gif` (AVOIDANT, team 3) shows the intended mechanism:
1. Two blockers stop in the north and south exits of a T-junction ahead of the evader.
2. The evader turns into one of them and stops 1 m behind.
3. Neither pursuit nor any single pursuer captured in this scenario.

A plan is feasible in only 8–18 % of steps, consistent with the structural blockability of real junctions: a team of
3 can close 30–56 % of them and a team of 5 64–93 % (`STRUCTURAL_junction_blockability.json`).

## Reading

An explicit lane-level ambush planner is the best tested strategy on real cities. It yields genuine cooperation
against a random-route evader with 3 pursuers, and, against an avoiding evader, gains that equal what independent
ambushers would achieve. Cooperation on real downtowns is possible but limited by how many lanes must be closed and by
timing.
