# Protocol — N05: native replication under the continuous-input evader (A-59 prerequisite, A-62 evader)

**Frozen before any N05 case.** Option B chosen by the Research lead (A-62); budget 120 CPU-minutes (1,800 s per map),
the ceiling of the range presented with the option.

## Rule (unchanged from N01)
**`W5_PREREQUISITE_MET`** iff at least **two** TRAINING maps yield a natively replicated construction: a model
`CONSTRUCTED` (both contrasts) that in SUMO, open **and** closed loop, captures with the same finisher within ±5 s
and no collision, and does not capture under the `b1` counterfactual nor with the helper never acting.

## What differs from N01
- Evader: **AVOIDANT with interpolated input** (A-62); SUMO's closed-loop evader uses the same input from SUMO's
  positions.
- Declared model: with keep-clear and SUMO right of way for merges (A-60).
- Seeds: `sha256(map_id + "AVOIDANT" + "n05")`.

## Multiplicity, declared
Second pre-registered attempt at the prerequisite (N01 first), the first under the A-62 evader. N02–N03 were reported
only. A pass here is reported with N01's failure and with the evader change that preceded it.

## Development checks before launch (not evidence)
350 tests pass (continuity of the new input; steerability control; information boundary). TRAINING development:
closed-loop capture reproduction 7/20 (node) → 12/20 (interpolated). No N05 seed was simulated.

## Prohibited
Changing any rule after an N05 result. Modifying hashed sources while it runs. TEST maps, optimizer, checkpoints.
