# Protocol: arrival-model specification and falsification diagnostic (W4 prerequisite)

Experiment ID: `20260921_w04_arrival_model_prereq_r01`. Created: 21 September 2026.
Stage: **W4 prerequisite**, not W4 itself.
**Acceptance criteria are frozen in this document before the diagnostic set is examined.**

## 1. Why this task exists, and why it is independent of D06 and D08

Master plan §6 requires, *before* W4: *"validate the model on an independently selected,
contract-compatible diagnostic set… Freeze acceptable error/coverage criteria before examining that
diagnostic set; report all unsupported cases."*

W4's offline constructions additionally need D08 (the evader policy) and the D06 freeze, both of which
belong to the Research lead and are unresolved. **Model validation needs neither.** It is therefore the one
W4 prerequisite that can proceed now, and it attacks the load-bearing risk: W2 built the machinery that
consumes arrival sets and W3 built the generator that enumerates over them, but **nothing produces them.**

## 2. The question

Under `docs/METHOD_SPEC_EN.md` §2.3, every arrival set carries a mandatory direction:

- **Rule A** — a joint opportunity may be `SUPPORTED` only if every participating set is `UNDER`.
- **Rule B** — it may be `REJECTED` only if every participating set is `OVER`.

**Which direction can an implementable arrival model actually achieve on this domain?**

The historical O28 decision, `MODEL_INADEQUATE_FOR_COUNTERFACTUAL_INTERCEPTION`, recorded that free-flow
lane estimates are lower bounds with no attainable upper interacting-pursuer arrival bound. If that holds,
arrival sets derived from such a model are `OVER`-approximations, which **can never return `SUPPORTED`** —
and every opportunity this project can represent would be `UNKNOWN`.

## 3. The diagnostic set, and its limits

`/Volumes/SSD Mac/PHD/Union/urban_dynamic_containment_evidence/v2_20260907/recovery_20260919_28/corrected_transitions.jsonl`
— 5980 recorded one-second transitions from the historical O28 audit, read **read-only**, hashed in
`inputs.json`.

Master plan §6 sets the limit exactly: *"Historical TRAINING traces can reveal limitations but must retain
their original contract and cannot certify a changed model/domain automatically."*

So this diagnostic **can falsify** a claimed approximation direction and **cannot certify** one. A model
that survives it is not validated; a model that fails it is refuted. Only the second outcome is a
conclusion.

**Exposure already incurred, recorded before freezing:** the first two rows of the file were read to
establish its field names. No aggregate, no error statistic and no outcome was computed before this
protocol was written. This is recorded as deviation D-17 rather than left implicit.

## 4. Acceptance criteria — frozen before examining the set

Let a transition be *covered* when the model emits a non-`UNKNOWN` prediction for it.

| Id | Criterion | Frozen threshold |
|---|---|---|
| A1 | **Lower-bound soundness.** For a model declared `OVER`, the predicted station must never exceed the observed station beyond tolerance: predicting a vehicle *further along* than it got would mean the true reachable set is not contained in the reported one. | violations `= 0`, tolerance `0.05 m` |
| A2 | **Upper-bound existence.** For a model to be declared `UNDER`, it must supply a *certified* upper bound on arrival time. | a certified bound must be present on `≥ 99%` of covered transitions |
| A3 | **Coverage.** Fraction of transitions the model covers. | reported, with `< 0.90` recorded as inadequate coverage |
| A4 | **Lane-change containment.** Every observed lane change must fall inside the model's `UNKNOWN` set, or the model must predict it. | reported; leakage of an observed lane change into a *covered* prediction is a soundness failure |
| A5 | **Braking containment.** Same, for observed braking. | reported |

**Gate rule, fixed now:** the arrival model is `UNDER_APPROXIMATING` only if A1 and A2 both hold and
coverage `≥ 0.90`. It is `OVER_APPROXIMATING` if A1 holds and A2 fails. It is `PREDICTION_ONLY` — supporting
**neither** verdict — if A1 fails.

**The consequence is stated before the outcome is known:** if the verdict is `OVER_APPROXIMATING` or
`PREDICTION_ONLY`, then under Rule A **no joint opportunity in this project can ever be `SUPPORTED`** from
such a model, and W4 cannot establish feasibility by prediction. That is not a failure of this task; it is
the finding the task exists to obtain.

## 5. What is implemented

`opportunities/arrival.py`, with the direction as an explicit property of each model rather than an
annotation a caller may set:

- `FreeFlowArrivalModel` — earliest arrival from distance, speed limit and bounded acceleration.
- `ConstructiveArrivalModel` — arrival times backed by an executable schedule.
- `RecordedProfileModel` — replays the historical model's own point hypotheses, so its declared direction
  can be tested against its own recorded behaviour.

## 6. Resource limits

**0 SUMO process starts, 0 episodes, 0 optimizer updates, 0 checkpoint loads, 0 TEST accesses.** The
historical evidence package is opened read-only and is not modified.

**W4's two-CPU-hour cap is NOT consumed by this task.** This is a prerequisite recorded on its own
engineering line; W4's allowance remains fully available.

## 7. What a result does and does not establish

**Can establish:** that a claimed approximation direction is **refuted** on recorded behaviour; the
model's coverage; whether observed lane changes and braking leak into covered predictions.

**Cannot establish:** that any model is correct — the diagnostic cannot certify; that the model behaves
this way under the *new* contract, since these traces retain their original one; physical feasibility;
anything learned or comparative.

## 8. Outputs

`plan.json`, `inputs.json`, `domain.json`, `environment.json`, `events.jsonl`, `results.jsonl`,
`result.json`, `DEVIATIONS_EN.md`, `SCIENTIFIC_DECISION_EN.md`, `checksums.json`. Sealed after all writing.
