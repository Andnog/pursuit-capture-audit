# Protocol — is SUMO deterministic from a fresh start, and does a shared prefix stay coupled?

**Written before the runner was implemented.** Frozen at the time of writing.

## Why this package exists

`20260922_w04_traci_first_execution_r01` established that `saveState` / `loadState` **cannot** carry the
assistance audit: SUMO 1.21.0 writes a vehicle's `pos` and `speed` at a fixed two decimals, so a restored
prefix is quantised to 1 cm and diverges by construction (A-37).

The proposed replacement is replay by **re-execution**: rather than restoring a prefix, run it again from
the episode start. **That replacement rests on an assumption of its own, and this package tests it.**

## Two questions, not one

They are different, and the second can fail while the first passes.

**Q1 — Reproducibility.** Two fresh starts with the same seed, the same network, the same vehicle
definitions and the *same* command sequence: identical trajectories?

**Q2 — Prefix coupling.** Two fresh starts that are identical up to decision `k` and *differ afterwards*:
are the frames **before** `k` still exactly equal?

**Q2 is what the assistance audit actually needs.** The audit compares two arms from a shared prefix, so the
prefix must be identical even though the arms later issue different commands. A simulator can be perfectly
reproducible under identical input and still couple the future into the past — through command ordering,
through a random stream whose draw count depends on what was commanded, or through internal state a TraCI
call touches. **Q1 passing does not imply Q2 passes.**

## Method, fixed before implementing

1. `scripts/preflight.py` must pass.
2. One **TRAINING** map, read-only. **No TEST map is opened.** No map copied or modified.
3. Commands are a **scripted, deterministic schedule**, not a policy: at decision `i`, a fixed function of
   `i` sets the target speed. No learning, no selection, no evader.
4. **Arm A1** and **A2**: identical seed, identical schedule. Compare in full. *(Q1)*
5. **Arm B**: identical seed, schedule identical to A1 for the first `k` decisions, then a different target
   speed. Compare **frames before `k`** against A1. *(Q2)*
6. All comparisons by **exact equality**, never a tolerance.
7. Close every process; assert none is left running.

## Acceptance rule, frozen before running

| Verdict | Condition |
|---|---|
| `REPRODUCIBLE_AND_PREFIX_COUPLED` | A1 == A2 in full, **and** B's prefix == A1's prefix |
| `REPRODUCIBLE_PREFIX_NOT_COUPLED` | A1 == A2, but B's prefix differs |
| `NOT_REPRODUCIBLE` | A1 != A2 |
| `PROCESS_FAILED` | SUMO could not be started or did not terminate cleanly |

**Only `REPRODUCIBLE_AND_PREFIX_COUPLED` rescues replay by re-execution.** Any other verdict means the
assistance audit needs a different design, and the contrast bounds — which are *logical, not statistical* —
cannot absorb the difference by widening.

`NOT_REPRODUCIBLE` is a publishable result and must not be retried with a loosened comparison.

## Diagnostic arms, declared in advance

The previous package exceeded a limit of 2 because a failure pointed at a cause worth testing. That
headroom is declared here instead of taken later:

- **If Q1 fails under SUMO's defaults**, one further pair with deterministic car-following (`sigma = 0`)
  may run, to separate "SUMO is not reproducible" from "this configuration is stochastic".
- No other arm may be added without a recorded deviation.

## Prohibited

- Any TEST-split map.
- Any optimizer update, checkpoint load, learning, or evader policy.
- Any unattended or background run.
- Loosening the exact-equality comparison after seeing a result.
- Drawing any conclusion about capture, feasibility or assistance.

## Resource limits

| | |
|---|---|
| SUMO process starts permitted | 6 |
| Simulated seconds permitted | 300 |
| Optimizer updates permitted | 0 |
| Checkpoint loads permitted | 0 |
| TEST split accesses permitted | 0 |
