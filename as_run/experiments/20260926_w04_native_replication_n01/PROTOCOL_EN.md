# Protocol — N01: native-replication search (A-58 revised prerequisite)

**Written and frozen before any N01 case was searched.** Prerequisite chosen by the Research lead after the A-47
gate returned `NOT_COVERED` (A-58); budget 120 CPU-minutes, decided by the Research lead; the seattle r03
replication is reported, **not counted**.

## Rule

**`W5_PREREQUISITE_MET`** iff at least **two** TRAINING maps yield a **natively replicated construction**:
a model `CONSTRUCTED` (both contrasts, revised declared model as hashed in `inputs.json`, D06 with A-57) that in
SUMO 1.21.0, **open loop and closed loop**, (i) captures with the same finisher, witness start within ±5 s of
the model's, no SUMO collision; (ii) does **not** capture under the D12 `b1` counterfactual (same helper and
window); (iii) does **not** capture with the helper never acting. Otherwise `W5_PREREQUISITE_NOT_MET`.

## Search

Per map (adelaide_cbd, seattle_downtown, toronto_downtown, washington_downtown), AVOIDANT, fresh seeds
`sha256(map_id + "AVOIDANT" + "n01")`, the W4 candidate search; a model `CONSTRUCTED` that fails native
replication is logged (`CONSTRUCTED_NOT_ACCEPTED`, with the first failing arm) and the search continues.
**1,800 CPU seconds per map** (Python), expansion cap 100,000 (the plan's). The CPU cap is expected to bind:
machine-dependent, declared. SUMO CPU is recorded separately.

## Development checks before launch (not evidence)

Positive control: the seattle r03 construction passes all six native arms. The acceptance path was exercised
on the r03 seattle seed (5 model constructions rejected natively, 1 accepted). No N01 seed was searched.

## Interpretation stated in advance

`NO_WITNESS_WITHIN_CAP` and `NOT_MET` are not evidence of impossibility. A pass unlocks W5 **for the protocols
that use these replicated constructions**; it is native evidence on TRAINING maps, not DEVELOPMENT coverage.

## Prohibited

Changing any rule after an N01 result. Modifying hashed sources while it runs. TEST maps, optimizer, checkpoints.
