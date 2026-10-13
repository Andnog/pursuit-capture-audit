# Mechanism diagnostics r01 (A-123, post hoc, descriptive)

**M1 — lane duplication.** Fresh scenarios, salt DGM1, 7 non-TEST cities × 5 scenarios × 3 evaders, team 5, 102
episodes per arm.

| | Planner steps | Steps with ≥ 2 pursuers on one lane | Lane targets duplicating a teammate's | OC |
|---|---|---|---|---|
| Coordinated PLB | 29,563 | 0.0 % | 0.0 % | 0.314 |
| Independent PLB | 29,882 | 25.3 % | 49.2 % | 0.275 |

Without joint assignment, half of the lane targets duplicate a teammate's. This supports the reading that the 7-point
ablation effect (A-122) comes from avoiding interference.

**M2 — behavioural identity of the dispatch fix.** 60 A-99 test episodes (PLB and pursuit) were run in legacy and in
checked mode, with 2 placement failures. **58/58 full traces (all vehicles, every 0.1 s) were identical.** The
correction changes bookkeeping only: no trajectory in these episodes moved.
