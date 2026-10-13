# Decision — N01: native replication (A-59 revised prerequisite for W5)

**`W5_PREREQUISITE_NOT_MET`** — one TRAINING map of four yields a natively replicated construction; the rule
requires two. W5 stays locked.

| Map | Verdict | Model search | Native checks | Stopped by |
|---|---|---|---|---|
| adelaide_cbd | `CAPTURE_NOT_COORDINATED` | 17,307 exp; 120 not coordinated, 40 failed verification | 0 | CPU cap (1,800 s) |
| seattle_downtown | `NO_WITNESS_WITHIN_CAP` | 1 exp | 0 | candidate queue exhausted |
| toronto_downtown | **`NATIVE_CONSTRUCTED`** | 3,844 exp | 1 of 1 accepted | found |
| washington_downtown | `CAPTURE_NOT_COORDINATED` | 13,013 exp; 48 model constructions | **0 of 48 accepted** | CPU cap |

**toronto** — finisher p1, helper p2 (17.8 m at witness start), model witness 96.3 s; SUMO 96.6 s open and closed
loop; b1 and helper-never-acts REJECTED in both loops. Post-hoc: no emergency braking in any of the six arms.

**washington** — all 48 model constructions fail the first arm (factual, open loop) the same way: SUMO **does
capture** within the window (192.1 s vs the model's 190.5 s) but **by a different pursuer**. The capture is real
in SUMO; the attribution to the model's finisher, on which the coordination contrast rests, is not.

**seattle** — the n01 scenario's evader path offers no candidate target (single-lane edges ≥ 12 m with another
approach), so the search ended after its baseline; 1,800 CPU seconds went unused and, per protocol, are not
redistributed.

## Reported with it

- N02 (OPTIMAL_ESCAPE, reported only): two maps natively replicated (seattle, washington).
- seattle r03 (development): replicated natively (A-56).
Across all native checks this session, **4 distinct constructions replicate natively** (toronto N01; seattle and
washington N02; seattle r03) — none of them counts toward this AVOIDANT prerequisite except toronto.

## Reading

The binding obstacles are identifiable: (i) one scenario gave the generator nothing to work with; (ii) in
washington the model and SUMO disagree on **which** pursuer ends up in front of the evader. X02 found a third,
general one — the model lacks SUMO's junction keep-clear rule.
