# Decision — N05: native replication under the A-62 evader (prerequisite attempt 2)

**`W5_PREREQUISITE_NOT_MET`** — zero natively replicated constructions (two required). W5 stays locked.

| Map | Verdict | Model search | Native checks | Stopped by |
|---|---|---|---|---|
| adelaide_cbd | `CAPTURE_NOT_COORDINATED` | 37,849 exp; **7,314 captures not coordinated**, 84 necessary-but-b1-null, 2 model constructions | 0 of 2 (both fail the closed-loop factual) | CPU cap |
| seattle_downtown | `NO_WITNESS_WITHIN_CAP` | 1 exp | 0 | candidate queue empty |
| toronto_downtown | `CAPTURE_NOT_COORDINATED` | 14,921 exp; 2,365 not coordinated, 75 necessary-but-b1-null | 0 | CPU cap |
| washington_downtown | `NO_WITNESS_WITHIN_CAP` | 5,881 exp | 0 | candidate queue exhausted |

## Reading
- **Capture is plentiful; coordination is not.** Under the continuous-input evader the model captures thousands of
  times in adelaide and toronto, almost always with a single pursuer sufficing. Captures that need their helper exist
  (159 necessary-but-b1-null), but the D12 `b1` substitute rarely undoes them, and only 2 met both contrasts.
- **Seattle has no candidates, structurally.** The generator targets only single-lane edges ≥ 12 m (the model claims
  no capture by blocking a multi-lane edge); the n05 evader path runs entirely on 2–4-lane edges. Same outcome as N01.
- **One scenario per map decides each map.** The prerequisite as designed rests on four scenarios; a map's result is
  largely a property of its seeded scenario.

CPU 4,218 s wall; 1.2 s SUMO. TRAINING only.
