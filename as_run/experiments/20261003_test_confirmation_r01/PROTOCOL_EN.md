# Protocol — single-shot TEST confirmation r01 (A-110)

Pre-registered in `governance/AMENDMENTS_EN.md` (A-110) before launch; the analysis (`summarise` in
`scripts/run_test_confirmation.py`) was written and hashed before any TEST episode was run. The code path was smoke-tested
on a non-TEST city (adelaide_cbd, salt SMOKE) so that no TEST episode exists outside this package.

- TX: chicago_loop, melbourne_cbd, salt_lake_city, minneapolis_downtown; salt PT1; scenarios 0–19; SUMO seeds 9500+i and
  109500+i; evader RANDOM / AVOIDANT / OPTIMAL_ESCAPE; teams 3 / 5 / 7; methods c2_15 planner (A-99 final_params), A-95
  ambush, pursuit, MAPPO-KAN and MAPPO-MLP (A-105 BC checkpoints from `20261002_mappo_r01/state.pkl`, greedy).
  Measures: D06 (primary), trapped, body-gap ≤ 5 / 10 m, centre ≤ 5 m, certificate firing times. 7,200 episodes.
- TS: c2_15 singles p1…p7 (team-7 placement, nested). 3,360 episodes.
- OX / OS: OPTIMAL_ESCAPE on the 7 non-TEST cities, salt PE15, c2_15 / A-95 / pursuit, and singles. 4,480 episodes.
- CA: TX pursuit episodes with a fired certificate, replayed with the hold condition; escape within 60 s.
- H1, H2 (97.5 %), S1–S6 as in A-110. Results reported regardless of sign; no change of method after the run.
