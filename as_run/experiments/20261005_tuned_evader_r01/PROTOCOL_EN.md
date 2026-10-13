# An evader tuned against PLB (A-127 E)

**Registered in:** `governance/AMENDMENTS_EN.md`, A-127 and its clarification, before any gated run.

**Question.** Does the advantage of predictive lane blocking over pursuit survive an evader whose decision rule has
been tuned against PLB, with the same kind of search that tuned PLB?

**Evader family (`EvaderLevel.TUNED`).** At each decision the evader scores every continuation by a weighted sum of
seven features of the public state and takes the best:
- `d1`, `d2`: road distance from the end of the continuation to the nearest and second-nearest pursuer, capped at
  1,000 m and divided by 1,000;
- `branch`: onward continuations, capped at 4, divided by 4;
- `crowd`: share of pursuers within 300 m of its end;
- `on_edge`: a pursuer is on the continuation or on one of its continuations;
- `predicted`: the continuation is the one a distance-greedy predictor expects;
- `noise`: a keyed uniform number, reproducible per seed and decision.

It uses only current pursuer positions, is deterministic given its seed, is never faster than the pursuers, and logs
every decision. A cul-de-sac ranks last while an alternative exists. The reference weights (`d1` = 1, others 0)
reproduce OPTIMAL_ESCAPE.

**Search** (TRAINING cities; objective: lowest OC capture by PLB c2_15).
- Candidates: the reference plus 32 weight vectors, uniform in [−1, 1], generator seed 20261005.
- Rung 1 (salt `ES1`): 4 cities × 6 scenarios × team 5. The 8 sampled candidates with the lowest PLB capture advance.
- Rung 2 (salt `ES2`): 4 cities × 20 scenarios × teams 3/5/7, for those 8 and the reference. The lowest is selected.
- Breaker: if the selected candidate does not lower PLB capture by at least 0.02 relative to the reference, the
  search is reported as having found no stronger evader. The test runs in either case.

**Test** (salt `PE21`, seven non-TEST cities): 20 scenarios × 2 SUMO seeds × teams 3/5/7; PLB, junction ambush and
pursuit against the selected evader; PLB and pursuit against the reference, on the same scenarios. 4,200 scheduled
episodes.

**Primary.** PLB − pursuit against the tuned evader, pooled over teams, family-clustered 95 % lower bound > 0. A
failure is reported as a limit of the claim that waiting ahead beats chasing.

**Secondary.** PLB capture against the tuned evader minus against the reference (paired); pursuit likewise; by team;
PLB − junction ambush; share of episodes in which the evader leaves the network.

**Development check (not gated).** `scripts/verify_evader_levels_unchanged.py` re-runs a fixed sample of 140
recorded episodes (OPTIMAL_ESCAPE, GOAL_DIRECTED, AVOIDANT, RANDOM) before and after the evader source changes and
compares outcomes. Unit tests check that the reference weights make the same choice as OPTIMAL_ESCAPE in 800 random
states.

**Scope.** The evader is tuned against PLB and not against pursuit, which is the unfavourable case for the claim. It
is a scripted family with 33 candidates, not a learned or game-theoretic best response.
