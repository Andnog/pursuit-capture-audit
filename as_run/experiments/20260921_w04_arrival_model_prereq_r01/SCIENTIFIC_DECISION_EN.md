# Scientific decision — arrival-model diagnostic, revision r01

Experiment: `20260921_w04_arrival_model_prereq_r01`. Date: 21 September 2026.

**Decision: `CRITERION_INVALID_NO_CONCLUSION_DRAWN`.**

---

## 1. What this package does not conclude

The runner printed `PREDICTION_ONLY`. **That verdict is withdrawn and no conclusion about the arrival
model's approximation direction is drawn from this revision.**

Criterion A1, frozen before the diagnostic set was examined, was mis-specified in two independent ways
recorded in `DEVIATIONS_EN.md` D-18: its reasoning about direction was inverted, and the quantity it tested
is an unsigned magnitude from which the sign — the only thing that decides direction — cannot be recovered.
A criterion that cannot distinguish the two cases cannot declare either.

## 2. What this package does establish

The other four measurements are sound and are carried into `r02` unchanged:

| Criterion | Measured |
|---|---|
| A2 upper-bound existence | **0 of 5598** covered transitions carry a certified error bound; `certified_error_bound` is `None` on **all 5980** rows |
| A3 coverage | 0.93612 — 5598 covered, 382 `UNKNOWN` |
| A4 lane-change containment | 352 observed lane changes, **0** inside a covered prediction — no leakage |
| A5 braking containment | 309 observed braking events, **241** inside covered predictions |

A2 alone is decisive on one point, independent of A1: **the recorded model cannot be `UNDER`.** An
under-approximation asserts that every reported time is achievable, which requires a certified bound. There
is not one anywhere in the record.

A4 reproduces the historical O28 finding exactly: every observed lane change falls inside the `UNKNOWN`
set. The model does not silently cover behaviour it cannot predict.

A5 is the more uncomfortable number: **241 of 309 braking events sit inside covered predictions.** The
model issues point hypotheses for transitions in which the vehicle was braking, which is precisely where an
interaction-free profile is least trustworthy.

## 3. Why the package is retained rather than corrected

The master plan requires corrections to come as a new revision preserving the original frozen protocol and
results. Editing a criterion after seeing it fail — even toward something more correct — is
indistinguishable in the record from tuning a criterion until it yields a verdict. This package is the
record of the error; `r02` carries the corrected criteria.

## 4. Next step

`20260921_w04_arrival_model_prereq_r02`, with A1 replaced by a criterion that is actually decidable from the
available evidence, and with the limits of that evidence stated.

## 5. What this decision does not authorize

No SUMO episode, optimizer run, checkpoint load or TEST access. No claim about the arrival model's
direction. No claim that W4's prerequisites are met.
