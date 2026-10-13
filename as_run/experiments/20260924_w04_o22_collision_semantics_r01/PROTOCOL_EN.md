# Protocol — what does SUMO call a collision, and can the frozen capture predicate be satisfied without one?

**Written before the probe was implemented.** O22's safety-admission part, authorised by the Research lead
on 2026-09-24.

## The question

The frozen capture predicate (D06) requires pursuer–evader separation in **[0.30, 2.00] m**, held for
2.0 s, and asserts that capture **cannot coincide with a collision** because 0.30 m is strictly positive. That
assertion assumes a collision means **physical overlap**.

SUMO's `--collision.mingap-factor`, left at its default, defers to the car-following model's
`collisionMinGapFactor`. If that is 1.0, SUMO reports a collision whenever a bumper gap falls below the
vehicle's **minGap, 2.5 m** in this domain — and the whole capture band would lie inside SUMO's collision
zone.

Historical O22 recorded a native collision at a **positive** reported gap and attributed it to arithmetic.
If SUMO's collision threshold is minGap, a correctly computed positive gap below 2.5 m would be a collision
too, and the attribution would be incomplete.

**This is tested, not assumed from documentation.**

## Method

Two vehicles, same lane, one TRAINING map, bodies and minGap from the domain contract. Both held stationary
with `setSpeed(0)`. Positions forced with `moveTo` so insertion checks cannot silently adjust them. After
one step, read SUMO's own collision report.

Bumper gaps: **3.0, 2.6, 2.4, 2.0, 1.0, 0.30** m — three inside the capture band, three around minGap.

| Arm | Setting |
|---|---|
| A | SUMO defaults |
| B | `--collision.mingap-factor 0`, i.e. collision = physical overlap |

## Acceptance rule, frozen before running

| Verdict | Condition |
|---|---|
| `CAPTURE_BAND_IS_COLLISION_FREE_BY_DEFAULT` | Arm A reports no collision at any gap in [0.30, 2.00] |
| `CAPTURE_BAND_IS_A_COLLISION_BY_DEFAULT` | Arm A reports a collision at gaps inside the capture band |
| `PROBE_FAILED` | positions could not be forced, or the report could not be read |

The measured gap is read back from the simulator and reported alongside the intended one; a probe whose
vehicles are not where it put them has not tested anything.

## What this decides, and what it does not

If the band is a collision by default, **D06 as frozen is unsatisfiable under SUMO's default collision
semantics**, and resolving it changes either the simulator configuration or the frozen predicate. **Both are
the Research lead's decision**, because D06 is theirs. This package measures; it does not choose.

## Prohibited

Any TEST map, optimizer, checkpoint. Changing D06. Choosing a remedy.

## Resource limits

SUMO process starts permitted: **6**.
