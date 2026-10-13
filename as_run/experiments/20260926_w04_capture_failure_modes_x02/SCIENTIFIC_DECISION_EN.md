# Findings — X02 (exploratory, no gate): why SUMO does not reproduce 16 of 60 model captures

**Modes** (open loop, sigma 0, DEVELOPMENT): SUMO's evader reaches the blocking edge before the finisher — 7;
SUMO's evader never reaches the blocking edge — 7; both on the edge in order without a dwell — 1; SUMO captures
at another time or by another pursuer — 1.

**Dominant mechanism: junction keep-clear.** In 6 of the 7 "never reaches" cases the finisher holds at 10.0 m
and the model's evader stops at 3.9 m — its rear (body 5 m) still **inside the junction**. SUMO's evader waits at
the stop line instead, because SUMO does not let a vehicle enter a junction it cannot clear. Across all 60
captures (post-hoc split, computed after the gate):

| Evader at the model's witness start | Reproduced in SUMO |
|---|---|
| rear inside the junction | **2 / 13** |
| clear of the junction | **42 / 47 (0.89)** |

The declared model lacks SUMO's keep-clear rule, and finisher holds at 6 or 10 m (below body length + evader
min_gap + body length ≈ 11 m) produce captures that exist only in the model. Among captures clear of the
junction the reproduction rate is above A-55's 0.80 threshold. **Post hoc; it does not change the sealed gate
verdict.** It identifies the fix: add keep-clear to the model and restrict finisher holds to ≥ 11 m.

The remaining 7 ("evader first") are timing: SUMO's evader faster or its finisher slower by several seconds.
