# Protocol — native ladder, stage B (A-64)

Frozen before any stage-B scenario. Maps C1_grid4x4, C2_grid6x6, C3_grid9x9, C4_grid10x4, C5_spider; evader
AVOIDANT (A-62 input), 8 scenarios each (salt `LBs<i>`); difficulty ladder on C2: RANDOM and OPTIMAL_ESCAPE, 8 each.
90 CPU s per scenario (Python + SUMO). Engine and judge as in `native/engine.py` (hashes in inputs.json).

**Rule:** continue to stage C iff ≥ 3 of the 5 AVOIDANT maps have ≥ 2 of 8 scenarios with ≥ 1 **robust** coordinated
construction. Otherwise report where coordination disappears (size / shape) and stop and decide.
Reported: capture, coordinated and robust shares per map; rates per 100 plans; GIFs of the best case per map.
