# Protocol — F2: caging difficulty sweep with physical occupancy (A-72)

Frozen before any F2 run. Maps C2_grid6x6, C3_grid9x9, adelaide_cbd (TRAINING); team 3, 4, 5 pursuers (first n of
p1–p5); evader AVOIDANT (A-62 input) at 1.0, 1.2, 1.5×; strategies cut / individual / pursuit; 15 scenarios per cell
(salt `F2`); SUMO seeds 8001–8003, sigma 0.5. Certificates: time cage (safe region ≤ 2 junctions, connected, A-71) and
physical cage (time cage + every gate held: pursuer front ≤ 25 m from the gate, speed ≤ 2 m/s), each counted after 10 s.

**Coordination-regime cell:** physical-cage Δ = P(cut) − P(individual), paired by scenario, bootstrap 95 % CI lower
bound > 0.05, and 0.10 ≤ P(physical cage | cut) ≤ 0.95.
**F2 passes** iff ≥ 3 cells are coordination-regime cells, at least one on the real map. Then the question change
(A-70) is proposed for recording, with MARL to be developed in that regime. Otherwise: stop and decide.
Reported: time-cage results, cut − pursuit, contact captures, collisions, hard braking.
