# Assistance audit protocol

Stage: W2. Date: 21 September 2026.
Status: **protocol specified; finite accounting IMPLEMENTED and tested; replay NOT implemented (W3/W5).**

The assistance audit is the **measurement component** that defines the `Z` endpoint. It is not this
project's contribution. The construction is adopted with attribution from the historical
[`METHOD_SPEC_EN.md`](../../urban_capture_cooperation_v3/research/20260919_novelty_audit_01/METHOD_SPEC_EN.md)
§4–§6.

## 1. What is intervened on

A **helper** distinct from the factual finisher, and a **physically admissible** policy substitution. No
body is removed or teleported: an invalid physical deletion may be used only as a logical negative control
illustrating a changed system, never as native execution or as a competitive baseline.

The declared family, fixed before outcomes:

| Id | Alternative | Question it answers |
|---|---|---|
| `b1` | public-information independent pursuit, same vehicle, same limits and interface | does the learned choice beat independent pursuit? |
| `b2` | continue a previously chosen admissible commitment without new teammate-conditioned selection | does the specified commitment update matter? |
| `b3` | safely withdraw interference through an existing admissible continuation | what did the physical interference achieve? |

**The primary substitution is `b1`, for a fixed block of five decisions**, followed by return to the frozen
policy under its recorded memory-update convention. `b2` and `b3` are secondary, separately named
contrasts. These answer **different questions** and their effects are reported separately before any
sensitivity envelope. None is a universally neutral "absence of cooperation", and the family must not be
chosen after seeing which baseline loses.

## 2. Admission is trivalent

`SUPPORTED_ADMISSIBLE`, `SUPPORTED_INADMISSIBLE`, or `UNRESOLVED`. Guards stay active and action
availability is recomputed in the evolving counterfactual state. **One-step safety does not certify a
sequence** — finite case F5 enforces this. A known-inadmissible member stays visible; an `UNRESOLVED`
member blocks any complete-family conclusion and is never silently replaced.

## 3. State restoration and coupling

A replay must restore the **complete** simulator, controller and guard state and prefix: pending commands,
memories, current commitments and exogenous randomness. Pause/resume must be validated against
uninterrupted execution before any replay result is used.

Other agents keep their policy **functions** and react naturally; their realised actions are not forced to
match the factual episode. In autoregressive selection, the insertion point is declared and later
conditionals are recomputed consistently.

**A shared seed is not a shared noise realisation.** After event divergence, differing events consume
random numbers in a different order. Use a verified keyed coupling where available; otherwise report paired
stochastic comparisons with uncertainty. **An unverified single replay cannot certify a deterministic
counterfactual**, and under a small replay allocation the assistance gate then remains unresolved and needs
a new prospective design.

## 4. Contrasts, bounds and labels

`d = Y_factual − Y_intervened`, with bounds `[l_f − u_b, u_f − l_b]`. A known outcome is a singleton; an
unknown outcome is `[0, 1]`. Envelope `L = min_b lower`, `U = max_b upper`, over resolved admissible
members only.

**These are logical bounds from missing outcomes. They are not confidence intervals** and must never be
reported as such.

Labels: `POSITIVE_ACROSS_FAMILY`, `BASELINE_DEPENDENT`, `NO_POSITIVE_EFFECT_DEMONSTRATED`,
`HARMFUL_ACROSS_FAMILY`, `INSUFFICIENT_SUPPORT`, plus an `incomplete_family` flag.

Properties that hold and are tested: unknown preservation; family expansion cannot narrow the envelope;
a positive contrast under one withdrawal does not establish universal necessity; and **coalition
redundancy** — two interchangeable helpers can each have a null leave-one-out effect while the pair
matters, so individual effects do not sum and a null effect is not evidence of absent coordination.

## 5. Coverage and the endpoint

Audit **every** factual capture in the confirmatory primary comparison, or freeze a probability sampling
design with inclusion probabilities and an estimator. Do not generalise from selectively audited successes.

For `N` executed cases with `S` supported positives and `U` unresolved: `[S/N, (S+U)/N]`. Not-executed
cases are reported separately with planned and executed denominators.

**A capture whose required audit is unresolved gives `Z = UNKNOWN`, never 1.** This is enforced in code as
a semantic invariant, not left to reporting discipline.

## 6. Implementation status

| Component | Status |
|---|---|
| contrast bounds, envelope, labels, endpoint bounds | **IMPLEMENTED and tested** (finite outcome tables, W1 cases A1–A8) |
| trivalent admission algebra | **IMPLEMENTED and tested** |
| `Z = UNKNOWN` invariant | **IMPLEMENTED and tested** |
| replay, state restoration, coupling verification | **NOT IMPLEMENTED** — W3 and W5 |
| helper and intervention-time selection rules | **UNRESOLVED** — D12 |
