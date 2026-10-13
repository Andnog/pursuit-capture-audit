# Deviations

Experiment: `20260921_w04_arrival_model_prereq_r01`. Stage: W4 prerequisite.

**This package's headline verdict is NOT a valid conclusion.** Criterion A1 was mis-specified before it was
frozen, and the package is retained as the record of that error rather than corrected in place. The valid
conclusion is issued in revision `r02`.

---

## D-17 — Field names were read before the criteria were frozen

**What happened.** The first two rows of the diagnostic file were read to establish its field names, before
`PROTOCOL_EN.md` was written.

**Why it matters.** The ordering rule exists so criteria cannot be shaped around outcomes.

**Effect.** None on the criteria. What was read was the *schema* — which keys exist — not any value
distribution, aggregate or error statistic. The thresholds were chosen from the method specification, not
from the data. Recorded rather than left implicit.

---

## D-18 — Criterion A1 was mis-specified, and the verdict it produced is invalid

**What happened.** A1 was frozen as: *"For a model declared `OVER`, the predicted station must never exceed
the observed station beyond tolerance: predicting a vehicle further along than it got would mean the true
reachable set is not contained in the reported one."*

**That reasoning is inverted.** Predicting a vehicle *further along* at time `t` means predicting it
*arrives earlier* than it actually does. An earlier predicted arrival makes the reported set
`[t_predicted, horizon]` a **superset** of the achievable arrivals — which is exactly what `OVER` means.
The violation of `OVER` is the opposite case: predicting a vehicle *behind* where it got, hence arriving
*later* than achievable, which would leave true arrivals outside the reported set.

**And the quantity cannot decide it either way.** `station_error_m`, `position_error_m` and
`speed_error_m_s` are all **unsigned magnitudes** in this file: across 5598 covered transitions not one is
negative, and the observed station itself is not recorded. The sign is therefore unrecoverable, so A1 as
frozen measured *absolute error above 5 cm* — which is a statement about accuracy, not about approximation
direction, and cannot support either Rule A or Rule B.

**Effect on results.** The runner's printed verdict, `PREDICTION_ONLY`, followed correctly from A1's
failure, but **A1's failure means nothing about direction**. This package therefore records
`CRITERION_INVALID_NO_CONCLUSION_DRAWN`. Its measurements of A2, A3, A4 and A5 remain valid and are carried
into `r02` unchanged.

**Why the package was not edited.** The master plan requires that corrections come as a new
revision preserving the original frozen protocol and results. Editing A1 after seeing that it failed — even
to something more correct — is indistinguishable in the record from tuning a criterion to obtain a verdict.
`r02` carries the corrected criteria and a protocol that states what changed and why.

---

## Deviations that did not occur

No SUMO process start, no episode, no optimizer update, no checkpoint load, no TEST access. The historical
evidence package was opened read-only and was **not modified**; its own seal is unchanged. W4's two-CPU-hour
cap was not consumed.
