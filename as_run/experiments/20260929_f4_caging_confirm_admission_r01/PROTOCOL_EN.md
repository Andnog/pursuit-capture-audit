# Protocol — F4: caging re-confirmation with the legal control interface (A-76)

Frozen before any F4 run. Identical to F3 (`20260929_f3_caging_confirm_real_r01`: 3 real TRAINING maps, teams 3–4,
evader 1.2×/1.5×, 40 scenarios per cell, salt `F3` so scenarios are paired with F3, seeds 8001–8003, sigma 0.5, cut vs
individual with hysteresis) **except** `admission=True` (A-76). **Primary:** pooled paired Δ P(physical cage) cut −
individual, bootstrap 95 % CI over scenario cells; passes iff lower bound > 0. Reported: runs with true emergencies,
collisions, per-map Δ, comparison with F3.
