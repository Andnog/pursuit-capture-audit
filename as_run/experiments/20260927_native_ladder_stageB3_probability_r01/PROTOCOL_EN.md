# Protocol — native ladder, stage B3 (A-66): coordination in probability

Frozen before any B3 scenario. Same 56 scenarios as B/B2 (salt `LB`): C1–C5 AVOIDANT, C2 RANDOM and OPTIMAL_ESCAPE.
Per scenario: deterministic native search (60 CPU s, exact generator) collecting plans whose capture needs the helper;
up to 3 screened on selection seeds 2001–2010 (sigma 0.5), with and without the helper; the best by (with − without)
is kept and estimated on **fresh** seeds 5001–5020. Per map: mean paired Δ over contributing scenarios, bootstrap 95 %
CI (10,000 reps, scenario clusters). **Map passes:** CI lower bound > 0 and ≥ 4 contributing scenarios.
**Stage rule:** continue to stage C iff ≥ 3 of the 5 AVOIDANT maps pass. Code hashes in inputs.json.
