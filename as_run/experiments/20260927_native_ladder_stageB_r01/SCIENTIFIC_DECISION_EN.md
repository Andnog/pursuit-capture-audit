# Decision — native ladder, stage B

**Rule not met** (needed ≥ 3 of 5 AVOIDANT maps with ≥ 2 of 8 scenarios holding a robust coordinated construction):
**zero robust constructions anywhere.**

| Map : level | scenarios with capture | with coordinated | with robust | plans tried | coordinated / 100 plans |
|---|---|---|---|---|---|
| C1 grid 4×4 : AVOIDANT | 8 | 0 | 0 | 1,917 | 0.00 |
| C2 grid 6×6 : AVOIDANT | 4 | 2 | 0 | 1,381 | 0.14 |
| C3 grid 9×9 : AVOIDANT | 2 | 1 | 0 | 1,454 | 0.07 |
| C4 grid 10×4 : AVOIDANT | 7 | 1 | 0 | 1,480 | 0.07 |
| C5 spider : AVOIDANT | 7 | 1 | 0 | 1,400 | 0.14 |
| C2 : RANDOM | 8 | 0 | 0 | 2,160 | 0.00 |
| C2 : OPTIMAL_ESCAPE | 2 | 0 | 0 | 1,392 | 0.00 |

Labels over all captures judged: 6 COORDINATED, 35 necessary-but-b1-null, 10 b1-without-necessity, 196 not coordinated,
143 not clean (collision or hard braking), 5,443 duplicates of an already-judged capture situation.

**Reading.** In SUMO, on clean single-lane maps, coordinated capture exists (6 cases on 4 map types, GIFs) but is
rare — about 1 per 1,000 plans — and **none survives SUMO's default driver imperfection** (5 seeds, sigma 0.5).
Captures by a single pursuer are common (small grids: 8/8 scenarios). Difficulty behaves as expected at the capture
level (RANDOM 8/8 scenarios captured, AVOIDANT 4/8, OPTIMAL 2/8 on C2).

CPU 4,692 s (Python + SUMO), 8 workers. Controlled maps only; no TEST access.
