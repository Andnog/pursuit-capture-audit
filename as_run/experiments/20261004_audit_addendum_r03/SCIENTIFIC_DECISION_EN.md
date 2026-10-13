# Scientific decision — audit addendum r03 (A-121)

15,939 tasks; 100 scenario-placement failures, all in AB and identical for both arms. Summary data:
`ADDENDUM_R03_SUMMARY.json`. See `DEVIATIONS_EN.md` for the runner change.

## AB — coordination ablation (same prediction, information and per-pursuer rule)

| | Coordinated PLB | Independent PLB (no joint assignment) | Coordinated − independent (family 95 %) |
|---|---|---|---|
| All (4,940 episodes) | 0.349 | 0.278 | **+0.071 [0.054, 0.089]** |
| Avoidant | | | +0.081 [0.053, 0.113] |
| Random | | | +0.062 [0.035, 0.092] |
| Goal-directed | | | +0.070 [0.040, 0.103] |
| Team 3 / 5 / 7 | | | +0.050 / +0.078 / +0.085 (all lower bounds > 0.027) |

**Primary PASSED: joint assignment adds capture.** The gain grows with team size, as expected if coordination
mainly prevents pursuers from crowding the same lanes. This complements the independence reference, under which team
capture showed no statistically supported excess over independent solo worlds. Reading: coordination in PLB is
interference avoidance — deconflicting lanes and assigning full ambushes. It is not super-additive cooperation.

## AE — active escape after capture (pursuers held)

- All 1,433 captures reproduced and had 60 s of follow-up.
- From capture on, the evader actively tried, every second, to change to an adjacent lane with an onward link and to
  reroute.
- **15 of 1,433 escaped.**
  - All 15 had such a lane available. That was the case for 115 of 1,433 captures (8 %), of which 13 % escaped.
  - None of the 1,318 captures without one escaped.
  - The escapes come from 3 of 176 scenario–evader families (sapporo 11 RANDOM; sapporo 17 AVOIDANT; toronto 0
    AVOIDANT), which repeat across methods, teams and seeds.
- Reading: an OC capture is held against active lane changing unless an adjacent lane with an onward link is free. A
  stricter variant, OC with no free adjacent onward lane, had no observed escape. Reversing and U-turns remain outside
  SUMO's vehicle model.

## RC — the R9 defect at scale

8,966 episodes were re-run with checked dispatch: the A-99 test main cohort (6,536) and the goal-directed cohort
(2,430).
- **Outcome agreement with the sealed (legacy) results: 100 %** (0 changes).
- All recomputed contrasts are identical: PLB − pursuit +0.105 [0.068, 0.141]; PLB − ambush +0.050 [0.016, 0.084];
  goal-directed PLB − pursuit +0.105 [0.058, 0.156].
- The bookkeeping defect did not affect any OC outcome in these cohorts.

## RP — reproduction of sealed packages (legacy dispatch, own episode functions)

Robustness, sensitivity, commitment, goal-directed and MAPPO-v2: **100/100 each (500/500)**. Source files that
changed after launch cannot be recovered, but the sealed outcomes are reproduced by the current code in legacy mode.
