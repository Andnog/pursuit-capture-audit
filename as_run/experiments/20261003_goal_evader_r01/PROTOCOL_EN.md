# Protocol — goal-directed evader r01 (A-112)

Pre-registered in A-112 before launch. GOAL_DIRECTED evader (level 4; `simulator/evader.py`), destinations from the
outer 10 % band (`native/engine.py::_outer_nodes`). Development check (salt DEVG, not gated): old levels reproduce
sealed captures exactly (6/6); 95 % of goal-directed decisions take the shortest safe route to the destination.
Seven non-TEST cities, salt PE16, 20 scenarios × 2 seeds × teams 3/5/7 × {PLB, A-95, pursuit} + PLB singles.
Primary: PLB − pursuit pooled over teams, 95 % lower bound > 0. Script `scripts/run_goal_evader_study.py`.
