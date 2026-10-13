# Protocol — A-47 empirical model-validation gate, r01

**Written and frozen before any DEVELOPMENT-map scenario was generated.** Criteria decided by the Research
lead (A-55); D06 as amended by A-57. The model and harness are those whose hashes `inputs.json` records,
developed on TRAINING maps only (A-56).

## Claim class and label

A pass is **empirical coverage on a finite diagnostic set** — not a guarantee, not certification (A-47). A
failure is `NOT_COVERED`: the declared model's predictions are not adequate at the frozen tolerance on this set.

## Diagnostic set, fixed by rule

- Maps: the DEVELOPMENT split — `phoenix_downtown`, `portland_downtown`, `sapporo_grid`. TEST stays closed.
- Scenario `i` of a map: seed `sha256(map_id + "AVOIDANT" + "val%03d" % i)`, admissible moving starts; even `i`
  an interception plan (a seeded pick among the W4 search's candidates), odd `i` a seeded random plan with holds.
- Selection on **model outcomes only**: per map the first **20** legal scenarios with a model capture and the
  first **10** without, in index order, scanning at most **400** indices. Model runs with a collision or an
  emergency braking are excluded and counted.

## Replay

SUMO 1.21.0, contract arguments (collision = overlap), per-class min_gap, sigma 0, speed deviation 0,
`departLane=best`. **Open loop** (scored): each vehicle follows the edge sequence it realised in the model; each
pursuer's holds become SUMO stops placed and released at the decisions where the model's hold changed; every
vehicle stops at its route's end. **Closed loop** (reported only): the evader chooses with the scripted policy
from SUMO's positions at the model's lookahead.

## Metrics (A-55 thresholds), per `validation/metrics.py`

| | Item | Pass |
|---|---|---|
| M1 | each SUMO edge entry, predicted by the model re-initialised from SUMO's state at the decision ≥ 5 s before it | ≥ 90 % within 1.0 s |
| M2 | where a pursuer comes to rest while a hold is in force (model vs SUMO, same hold interval) | ≥ 90 % within 1.0 m |
| M3 | each model capture: SUMO's own trace, same judge (A-57), same finisher, witness start within ±5 s | ≥ 80 % reproduced |
| M4 | longitudinal advance over 1.0 s from every decision, model re-initialised from SUMO's state | p95 ≤ 2.0 m |

Items touched by a SUMO lane change of the vehicle concerned in the preceding 10 s are `UNKNOWN`, counted, not
scored. Minimum scored items: M1 100, M2 30, M3 20, M4 500; fewer → `INCONCLUSIVE_INSUFFICIENT_SAMPLE`.

## Verdict

`EMPIRICALLY_COVERED` iff all four pass with enough items; `NOT_COVERED` otherwise.

## Expectation stated in advance

On 40 TRAINING scenarios during development: M1 0.917, M2 0.965, M4 p95 0.97 m, **M3 0.50**. A `NOT_COVERED`
verdict driven by M3 is the expected outcome and is recorded here so it is not later read as a surprise. If it
occurs, W5 stays locked and the Research lead chooses a revised prerequisite (A-47).

## Budget

60 CPU-minutes (Python + SUMO). Stops early if exceeded; recorded.

## Prohibited

Changing any rule above after a DEVELOPMENT result is seen. Modifying hashed sources while it runs. Any TEST
map, optimizer or checkpoint.
