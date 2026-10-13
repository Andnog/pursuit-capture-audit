# Findings — X01 (exploratory, no gate)

All 60 gate capture scenarios regenerated identically (seed and model capture match the sealed gate).

**Driver imperfection.** Under SUMO's default Krauss sigma 0.5 with three SUMO seeds, 127 of 180 replays
reproduce the model capture (70.6 %), against 44 of 60 (73.3 %) at sigma 0; **42 of 60 captures reproduce under
all three seeds**. Captures that SUMO reproduces deterministically are, almost all, robust to stochastic driving;
the non-reproduction is a model-vs-SUMO discrepancy, not noise sensitivity.

**Timing margin.** The hypothesis that failures concentrate at small margins (finisher settling shortly before
the evader arrives) is **not supported** by this measure: 6/6 reproduced at negative margin, 5/7 at 0–2 s, 13/16
at ≥ 15 s. The measure is crude — the margin is undefined for 27 of 60 captures (the finisher's first rest is not
on the evader's path) — so the hypothesis is not rejected either.

CPU: 48.6 s Python, 30.8 s SUMO. 180 SUMO process starts. DEVELOPMENT maps; no TEST access.
