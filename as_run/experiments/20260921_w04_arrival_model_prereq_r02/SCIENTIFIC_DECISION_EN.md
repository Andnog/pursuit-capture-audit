# Scientific decision — arrival-model direction (W4 prerequisite)

Experiment: `20260921_w04_arrival_model_prereq_r02`. Date: 21 September 2026.
Supersedes `…_r01`, retained sealed with its criterion error recorded.

**Decision: `DIRECTION_UNRESOLVED; UNDER REFUTED; NO OPPORTUNITY CAN EVER BE SUPPORTED FROM THIS MODEL.`**

---

## 1. The finding

Against 5980 recorded one-second transitions from the historical O28 audit:

| Criterion | Result |
|---|---|
| **B1** direction determinability | **`UNSIGNED`** — every recorded error is a magnitude (0 of 5598 negative) and the observed station is not stored. The sign is unrecoverable. |
| **B2** `UNDER` refutation | **`UNDER` REFUTED** — `certified_error_bound` is `None` on **all 5980** rows; **0 of 5598** covered transitions carry one. |
| **B3** coverage | 0.93612 — 5598 covered, 382 `UNKNOWN`. Adequate. |
| **B4** lane-change containment | **holds** — 352 observed lane changes, **0** inside a covered prediction. |
| **B5** braking containment | **241 of 309** observed braking events sit *inside* covered predictions. |

Two conclusions, of different strength.

**The weaker one: the direction cannot be established from this record.** Not "the model is bad" — the
*evidence* does not contain what deciding the question requires. Determining whether a model
under- or over-approximates needs to know whether it predicted arrival too early or too late. The record
stores only how far off it was, and the ground truth it was compared against is not retained. This is a
finding about the historical record, and it means any future model validation must retain signed errors.

**The stronger one, which does not depend on the first: `UNDER` is refuted.** An under-approximation
asserts that *every* reported time is achievable, and achievability requires a certified bound. There is
not one anywhere in 5980 rows. This holds regardless of B1.

## 2. The consequence, which was stated before the outcome was known

Rule A of [`docs/METHOD_SPEC_EN.md`](../../docs/METHOD_SPEC_EN.md) §2.3: a joint opportunity may be
`SUPPORTED` only if **every** participating arrival set is `UNDER`.

`UNRESOLVED` is not `UNDER`. `OVER` is not `UNDER`. So:

> **No joint opportunity in this project can ever be `SUPPORTED` from an arrival model of this kind.**

Everything W2 and W3 built — the compatibility predicate, the verdict algebra, the generator, the judge —
would return `UNKNOWN` for every opportunity, forever, on this model. Not because those components are
wrong, but because they are being fed sets that cannot carry the claim.

## 3. The structural point, which is the real result

This is **not** a problem better prediction solves, and that is worth stating plainly because the obvious
response — "improve the model" — does not work.

An `UNDER`-approximation asserts that every time in the set is **achievable**. Achievability is a claim
about what a vehicle can be *made to do*, not a forecast of what it *will* do. A more accurate predictor is
still a predictor: it narrows the error, it does not certify attainability. Under interaction a vehicle can
always be delayed, so no forecast supplies an attainable upper bound on arrival.

Only a **constructive schedule** — a trajectory that could actually be executed — asserts achievability.
This is implemented as `ConstructiveArrivalModel`, and its tests confirm the asymmetry end-to-end: free-flow
sets drive the real compatibility predicate to `UNKNOWN`, while schedule-backed sets reach `SUPPORTED`.

**This reframes W4.** The master plan's "two complete offline assisted-capture constructions" read as a
feasibility demonstration. They are more than that: **they are the only route to an `UNDER`-approximating
arrival set**, and therefore the only route to any `SUPPORTED` opportunity anywhere in this programme. The
historical O27 result — complete witnesses **0 of required 2** — is consequently not one unmet gate among
several. It is the gate everything else waits on.

## 4. What was implemented and verified

`src/joint_interception/opportunities/arrival.py`: three models whose direction is a **property of the
model**, not an annotation a caller may set — `FreeFlowArrivalModel` (`OVER`), `ConstructiveArrivalModel`
(`UNDER`, and only with a schedule), `RecordedProfileModel` (`PREDICTION`), plus `can_support` and
`can_reject` over a model set.

Verified: free-flow times match closed-form values (10.0 s and 12.5 s on hand-computed cases); free-flow
supplies **no** certified upper bound; the constructive model **refuses to guess** when no schedule is
supplied, rather than falling back to free flow and converting an unsupportable claim into a
supportable-looking one; a mixed direction set supports *and* rejects nothing; and end-to-end through the
real compatibility predicate, free-flow yields `UNKNOWN` while constructive yields `SUPPORTED`.

203 tests pass on both the pinned and a bare interpreter; lint clean.

## 5. Limits of this evidence

Master plan §6: historical traces *"can reveal limitations but cannot certify a changed model/domain"*.

**A refutation is a conclusion; survival would not have been.** B2 refutes `UNDER` for the recorded model.
Nothing here validates any model, and these traces retain their **original** contract, so they say nothing
directly about behaviour under the new one. B5 is a caution rather than a result: 78% of observed braking
sits inside covered predictions, which is where an interaction-free profile is least trustworthy — but
without signed errors, how badly it is wrong there cannot be measured.

## 6. Next permitted task

**Unchanged in identity, sharpened in priority: W4's two complete offline constructions.** They are now
understood as the prerequisite for `SUPPORTED` opportunities, not merely as a feasibility milestone.

W4 still requires, and this task does not supply:

1. **D08** — the evader policy. Unresolved; `simulator/evader.py` deliberately not written.
2. **D06 freeze** — the capture parameters, in particular `capture_speed_max_mps`.
3. **First execution of the TraCI surface**, which W3 left unexercised.

**A new requirement this task adds, recorded prospectively:** any future arrival-model validation must
retain **signed** prediction errors and the observed ground truth alongside them. The historical record
does not, and that alone made the direction question undecidable.

## 7. What this decision does not authorize

No SUMO episode, optimizer run, checkpoint load or TEST access. No claim that any arrival model is
validated. No claim that W4's prerequisites are met — they are not. No weakening of Rule A to admit
`OVER` or `PREDICTION` sets into a `SUPPORTED` verdict; that would delete the only mechanism preventing an
unsupportable feasibility claim, which is precisely the failure mode obligation O28 recorded.
