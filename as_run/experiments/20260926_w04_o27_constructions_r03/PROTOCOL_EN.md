# Protocol — O27 r03: the final W4 attempt, AVOIDANT only

**Written and frozen before any r03 case was searched.** Authorised by the Research lead (A-53) as the
**last** W4 attempt. r01 and r02 (both `W4_GATE_NOT_PASSED`) remain on record and are reported with r03.

## Unchanged from r02 (`20260925_w04_o27_constructions_r02/PROTOCOL_EN.md`)

Capture predicate, collision semantics, min_gap, evader level definitions, speed ratio 1.0, 300 s horizon,
one TRAINING map per case in manifest order, the admissible moving-start rule, the revised D12, command
admission, the candidate generator, **the criterion (both contrasts)**, the verdict table, the recorded
fields, and the interpretation stated in advance. Offline only: no SUMO process, TEST map, optimizer or
checkpoint.

## What changes

1. **Fresh seeds:** `sha256(map_id + level + "r03")`. The r01 and r02 seeds are excluded.
2. **The A-52 defect fixed:** a hold on the edge after an internal lane stays binding while the vehicle is on
   that internal lane. Regression test fails on r02's code and passes on this one.
3. **AVOIDANT only.** OPTIMAL_ESCAPE is not run (declared deviation; it cannot pass or fail the gate).

## Gate, unchanged

**`W4_GATE_PASSED`** iff at least **two** `CONSTRUCTED` among the four AVOIDANT cases; otherwise
`W4_GATE_NOT_PASSED`, **W4 closes**, and no r04 is possible (W4 CPU exhausted).

## Pre-launch checks, on the code whose hashes `inputs.json` records

- 20 baselines without plans (r01 and r02 seeds, both levels; r03 seeds, AVOIDANT): 0 collisions, 0 safety
  failures.
- Plan-bearing legality, **on r01 seeds only** (development seeds): six 1,500-expansion searches, 0 failed
  factual verifications. On r03 seeds only the four baselines were run: **no search, no plan, no capture
  check** before launch.

## Budget, fixed now

What remains of W4's two CPU hours: 7,200 − 3,432 (r01) − 1,885 (r02) ≈ **1,883 CPU seconds**, evenly:

| Level | CPU seconds / case | Expansion cap / case |
|---|---|---|
| AVOIDANT | 470 | 5,000 |

The expansion cap is set from r02's slowest AVOIDANT case (87 ms/expansion) so that expansions, not CPU
time, are expected to bind; a CPU stop is recorded as machine-dependent.

## Prohibited

Changing any rule above after an r03 result is seen. Modifying any source listed in `inputs.json` while the
search runs. Running more W4 search after r03.
