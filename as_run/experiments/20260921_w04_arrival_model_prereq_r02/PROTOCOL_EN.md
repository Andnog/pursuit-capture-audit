# Protocol: arrival-model direction, revision r02 (W4 prerequisite)

Experiment ID: `20260921_w04_arrival_model_prereq_r02`. Created: 21 September 2026.
Stage: **W4 prerequisite**. Supersedes `…_r01`, which is retained sealed.

## 1. What changed from r01, and why

`r01` froze criterion A1 as: the predicted station must never exceed the observed station. That was wrong
twice over, as recorded in `../20260921_w04_arrival_model_prereq_r01/DEVIATIONS_EN.md` D-18:

- **The reasoning was inverted.** Predicting a vehicle *further along* means predicting it arrives
  *earlier*, which makes the reported set a **superset** of achievable arrivals — that is what `OVER`
  means, not a violation of it.
- **The quantity cannot decide it.** `station_error_m`, `position_error_m` and `speed_error_m_s` are
  unsigned magnitudes; no value is negative across 5598 covered transitions and the observed station is not
  recorded. The sign, which is the only thing that determines direction, is **unrecoverable**.

`r02` therefore replaces A1 with a criterion that is decidable from the available evidence, and states
plainly what the evidence cannot decide.

**The r01 measurements of A2–A5 are carried over unchanged.** They were sound; only A1 was defective.

## 2. Corrected criteria, frozen before this revision runs

| Id | Criterion | Threshold |
|---|---|---|
| **B1** | **Direction determinability.** Can the approximation direction be established from the record at all? It can only be established if the sign of the prediction error is recoverable. | `SIGNED` or `UNSIGNED`; `UNSIGNED` means direction is `UNRESOLVED_FROM_THIS_EVIDENCE` |
| **B2** | **`UNDER` refutation.** An under-approximation asserts every reported time is achievable, which requires a certified bound. | `UNDER` is refuted if certified bounds are present on `< 99%` of covered transitions |
| **B3** | **Coverage.** | reported; `< 0.90` recorded as inadequate |
| **B4** | **Lane-change containment.** An observed lane change inside a *covered* prediction is a soundness failure. | leakage `= 0` required |
| **B5** | **Braking containment.** Reported, because an interaction-free profile is least trustworthy exactly where braking occurs. | reported |
| **B6** | **Rule-A consequence.** Whatever the direction turns out to be, can a `SUPPORTED` verdict ever follow from this model? | derived, not measured |

**Gate rule, fixed now:**

- `UNDER_APPROXIMATING` requires B2 to pass **and** B1 to be `SIGNED` **and** B3 adequate.
- `OVER_APPROXIMATING` requires B1 `SIGNED` with no late-arrival violations, and B2 failing.
- `DIRECTION_UNRESOLVED` when B1 is `UNSIGNED`: the record does not contain what would be needed.
- `PREDICTION_ONLY` when B1 is `SIGNED` and late-arrival violations exist.

**The consequence under Rule A is stated before the outcome is known:** `SUPPORTED` requires every
participating set to be `UNDER`. So unless the verdict is `UNDER_APPROXIMATING`, **no joint opportunity in
this project can ever be `SUPPORTED` from this model** — and that conclusion holds even when the direction
itself is unresolved, because `UNRESOLVED` is not `UNDER`.

## 3. Diagnostic set and its limits

Unchanged from r01: the historical O28 transition record, 5980 rows, read **read-only** and hashed.
Master plan §6: historical traces *"can reveal limitations but cannot certify a changed model/domain"*. A
refutation is a conclusion; survival is not.

## 4. Resource limits

**0 SUMO process starts, 0 episodes, 0 optimizer updates, 0 checkpoint loads, 0 TEST accesses.** W4's
two-CPU-hour cap is **not** consumed.

## 5. Outputs

The standard package set. Sealed after all writing has finished.
