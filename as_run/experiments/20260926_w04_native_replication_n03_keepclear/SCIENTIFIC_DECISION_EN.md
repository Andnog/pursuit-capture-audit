# Findings — N03 (EXPLORATORY): native replication under the keep-clear model variant

**Zero natively replicated constructions** (AVOIDANT, salt n03, 900 CPU s per map; every map stopped by the CPU cap).

| Map | Best model outcome | Model constructions | Rejected natively at |
|---|---|---|---|
| adelaide_cbd | `NO_WITNESS_WITHIN_CAP` | 0 | — |
| seattle_downtown | `CAPTURE_NOT_COORDINATED` (20 necessary-but-b1-null) | 0 | — |
| toronto_downtown | `B1_CONTRAST_WITHOUT_NECESSITY` | 10 (one factual situation, witness 127.8 s) | **closed-loop factual** (10/10) |
| washington_downtown | `NECESSARY_BUT_B1_NULL` | 55 (one factual situation, witness 259.7 s) | **closed-loop factual** (55/55) |

**What changed relative to N01.** Under the keep-clear variant every rejected model construction **passes the
open-loop factual arm** — SUMO reproduces the capture with the same finisher when the evader follows the model's
route (N01 washington: 0 of 48 passed it). All 65 now fail only in **closed loop**: SUMO's evader, deciding with
the same policy from SUMO's positions, takes a different continuation and is not captured.

**Reading.** The keep-clear fix removes the dynamics discrepancy X02 identified; the remaining obstacle to native
replication is **decision divergence** of the reactive evader: small timing differences change the pursuer
positions it reads at a decision, and its choice. Constructions whose capture survives the evader's own
re-decision are what native replication needs; the model search does not currently look for robustness to it.

Exploratory; cannot bear on W5. CPU 3,601 s Python, 36.6 s SUMO. TRAINING only.
