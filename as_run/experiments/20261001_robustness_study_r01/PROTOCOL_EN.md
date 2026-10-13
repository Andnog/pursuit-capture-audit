# Protocol — robustness study r01 (A-92, publication hardening)

Frozen before any episode. Approved by the Research lead (option A: harden for a Q1 submission; no learning).

**Primary endpoint (adopted for the publication, A-92): D06 contact capture** — body gap 0.3–2.0 m, both speeds
≤ 1 m/s, heading difference ≤ 15°, evader behind the pursuer with lateral offset ≤ 1 m, held 2 s. Secondary: trapped
(A-84) and trap type (A-89). Lenient endpoints for calibration: **body gap ≤ 5 m** (primary lenient), body gap ≤ 10 m,
and centre distance ≤ 5 m (as used in A-91), each at any instant of the 0.1 s trace.

Common setting: SUMO, legal control interface, equal speeds (evader 1.0×), sigma 0.5, 300 s, fresh scenarios (salt
`PR1`), **3 SUMO seeds per scenario** (9500 + index + 100000·rep). TEST cities closed.

**Block F (factorial, no background traffic).** 7 cities (TRAINING adelaide, toronto, washington, seattle;
DEVELOPMENT phoenix, portland, sapporo), 20 scenarios per city × 3 seeds. Evader level RANDOM / AVOIDANT /
OPTIMAL_ESCAPE × team size 2 / 3 / 5. Runs: pursuit team, cut team, and pursuit by each single pursuer alone (same
start; the others are not inserted).

**Block T (background traffic).** AVOIDANT, team 3, same scenarios and seeds as F, plus ≈ 300 random-trip passenger
cars per city (`assets/background_traffic`, randomTrips.py, one departure per second, fixed seed per city,
manifest-hashed). Background cars never count toward any endpoint.

**Block L (literature-like regime).** Controlled grids C2 (6×6) and C3 (9×9), RANDOM evader, team 5, pursuit and cut,
60 scenarios × 3 seeds.

**Estimands (seed-averaged per scenario, bootstrap 95 % CI over scenarios).**
- **R1 cooperation (primary):** synergy = P_team − [1 − Π_i (1 − p_i)], where p_i is the single-pursuer rate. Zero
  means the team behaves like independent pursuers. Cooperation is declared in a cell if the Bonferroni-adjusted CI
  (10 cells: 9 F cells + the T cell) has lower bound > 0. Also reported: team − best single, team − mean single.
- **R2:** pursuit − cut per cell.
- **R3 (calibration):** P(body gap ≤ 5 m) − P(D06) for the pursuit team per cell, and in block L for both policies.
- **R4 (traffic):** paired pursuit-team D06 with − without traffic (AVOIDANT, team 3).

Scenarios that cannot place the team are excluded; paired estimands use scenarios with every run present. Budget
≈ 20 CPU-h.
