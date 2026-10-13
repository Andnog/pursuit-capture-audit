# Protocol — native ladder, stage B4 (A-67): pooled probabilistic test

Frozen before any B4 scenario. C1–C5, AVOIDANT, 30 fresh scenarios each (salt `LC`). Per scenario: deterministic
native search 40 CPU s; up to 2 helper-needing plans screened on seeds 2001–2010 (sigma 0.5), with and without the
helper; the best by (with − without) estimated on fresh seeds 5001–5020. **Primary:** pooled mean paired Δ over
contributing scenarios, bootstrap 95 % CI (10,000 reps). **Pass:** lower bound > 0 and ≥ 20 contributing scenarios.
Secondary: per-map Δ. If it passes → stage C (factors) then real maps; if not → stop and decide.
