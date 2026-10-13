# Decision — A-47 empirical model-validation gate, r01

**Claim class: empirical coverage on a finite diagnostic set** (DEVELOPMENT maps; SUMO 1.21.0). Not a
guarantee. No optimizer, checkpoint or TEST map.

## Verdict

**`NOT_COVERED`** — M3 fails; M1, M2 and M4 pass with margin. W5 stays locked (A-47).

| Metric | Result | Threshold | Scored (UNKNOWN) | |
|---|---|---|---|---|
| M1 junction entry within 1.0 s | **0.939** | ≥ 0.90 | 2,776 (248) | pass |
| M2 hold rest within 1.0 m | **0.961** | ≥ 0.90 | 362 (4) | pass |
| M3 capture reproduced (same finisher, ±5 s) | **0.733** | ≥ 0.80 | 60 (0) | **fail** |
| M4 1-s longitudinal error, p95 | **0.97 m** | ≤ 2.0 m | 88,597 (2,441) | pass |

M3 by map: phoenix 14/20, portland 14/20, sapporo 16/20. Failures: 11 not captured in SUMO, 3 captured by a
different pursuer, 2 captured outside ±5 s.

90 scenarios (30 per map), 180 SUMO process starts, 302.6 s Python + 39.5 s SUMO CPU of 3,600 s. Model runs
excluded as illegal during selection: 48 of 518 scanned (15 phoenix, 5 portland, 28 sapporo) — the declared
model itself is not legal in about 9 % of plan-bearing scenarios.

## Reported, not gated

Closed loop: the evader's SUMO route matched the model's in 43 of 90 scenarios; model captures reproduced
closed-loop (same finisher, ±5 s) in 26 of 60.

## Reading

- The model predicts **motion** well: junction timing, hold positions and short-horizon position are within
  tolerance on independent maps. Its right-of-way rules were learned from SUMO on TRAINING maps (A-56) and
  transferred.
- It does not predict **captures** reliably enough: 1 in 4 model captures is not reproduced even when every
  vehicle follows the same routes and holds. Captures are knife-edge timing events, and open-loop agreement on
  routes is the best case; closed-loop agreement is lower (26/60).
- The result was predicted before the run (the protocol's stated expectation: M3 ≈ 0.50 on TRAINING). DEVELOPMENT
  did better than TRAINING on M3 (0.73), which is not evidence of overfitting to TRAINING.

## Consequence

Per A-47, W4's constructions establish **abstract feasibility only**; native work needs the missing physical
validation or an explicit revised prerequisite from the Research lead.
