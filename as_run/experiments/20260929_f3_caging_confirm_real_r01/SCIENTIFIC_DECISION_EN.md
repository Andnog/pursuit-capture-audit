# Decision — F3: confirmatory caging test on real maps — PASSED

**Primary:** pooled over 3 real TRAINING maps × teams {3, 4} × evader {1.2, 1.5}×, paired Δ = P(physical cage | cut) −
P(physical cage | individual) = **+0.225, 95 % CI [0.181, 0.268]**, 462 scenario cells → **passes**.

| Map | Δ phys [95 % CI] |
|---|---|
| adelaide_cbd | +0.215 [0.148, 0.283] |
| toronto_downtown | +0.183 [0.102, 0.267] |
| washington_downtown | +0.278 [0.212, 0.348] |

10 of 12 cells have CI lower bound > 0 (toronto team3 ×1.5 and team4 ×1.5 do not). Time-cage Δ positive in all 12 cells.
Contact captures rare (0–12 %): caging and contact capture are different outcomes.

**Physical quality.** 0 collisions. True emergencies (> 7 m/s²) in 39 % of runs, from the evader and from pursuers,
more under individual (48 %) than cut (30 %). **Sensitivity (post hoc):** restricted to emergency-free runs, Δ = +0.152
[0.095, 0.209]. The effect does not depend on emergency manoeuvres, but the control interface must be made legal before
any learning study.

**Reading.** On real road networks under microscopic traffic, distributing pursuers over the escape gates of the
evader's reachable region cages a faster evader substantially more often than individually greedy gate-taking. This is
the regime in which the proposed caging objective requires coordination.
