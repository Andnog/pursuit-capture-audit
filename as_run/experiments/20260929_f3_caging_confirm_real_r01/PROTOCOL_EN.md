# Protocol — F3: confirmatory caging test on real maps (A-73)

Frozen before any F3 run. Maps adelaide_cbd, toronto_downtown, washington_downtown (TRAINING); team 3 and 4 pursuers
(p1–p3, p1–p4); evader AVOIDANT (A-62 input) at 1.2× and 1.5×; strategies cut and individual, both with gate hysteresis
(`plan_commands(..., previous=...)`); 40 scenarios per cell (salt `F3`); SUMO seeds 8001–8003, sigma 0.5. Physical cage
as in F2 (safe region ≤ 2 junctions, connected; every gate held by a pursuer ≤ 25 m away at ≤ 2 m/s; 10 s).

**Primary (pass/fail):** pooled over the 12 cells, paired Δ = P(physical cage | cut) − P(physical cage | individual)
per scenario cell, bootstrap 95 % CI (10,000 reps) over scenario cells; **passes iff lower bound > 0.**
Secondary: per-map and per-cell Δ; time-cage Δ; contact captures; collisions; true emergencies (> 7 m/s²).
If F3 passes: propose the research-question change (A-70) for recording and design the MARL study in this regime.
