# Reward contract

Stage: W2. Date: 21 September 2026.
Status: **base reward specified; learner configuration UNRESOLVED (D17). Not implemented — W6.**

## 1. Base reward

Per master plan §11, and not altered here:

- **`+1` for the valid physical capture event**, as judged by the independent capture judge under the
  frozen contract. Not for proximity, not for a guard-accepted approach, not for reward shaping.
- **`− dt / 300` for elapsed simulated time**, accumulated over each interval `dt`.

Accumulation is explicit: for a decision interval covering `dt` simulated seconds, the time cost is
`dt / 300`, so a full 300 s episode without capture accrues exactly `−1.0`.

`gamma = 0.999`, `GAE lambda = 0.95`.

## 2. Termination and truncation are different things

- **No bootstrap** after an actual terminal capture, or after the task's true 300 s horizon.
- **Storage truncation is not termination.** If a rollout buffer ends mid-episode, the value function is
  bootstrapped from the next state, because the episode has not ended. Treating a buffer boundary as a
  terminal state injects a false terminal value and silently changes the objective.

The two cases must be recorded with different flags in every transition.

## 3. Unknown transitions are quarantined

A transition whose physical evidence is unresolved is **quarantined and reported**. It is not assigned an
invented reward and it is not silently dropped:

- it contributes to no gradient;
- it is counted and reported, so the denominator stays honest;
- the complete shaped return over an episode containing a quarantined transition is `null`, not a number.

Master plan §9: *"Do not assign reward zero to unknown evidence."* A zero reward is a claim that nothing
happened; `UNKNOWN` is a statement that we do not know.

## 4. Shaping

Potential-based shaping is **not** part of the base reward. It may be added only through a versioned
amendment that states the potential, its scale, and its terminal-zero definition.

A caution carried from the historical record, which applies to any future proposal: a terminal-zero
potential telescopes to `−Φ(initial)`, so it does **not** change the relative task return of
timeout-only complete trajectories. Shaping of that form cannot by itself make capture more attractive than
timing out; it changes only the within-episode gradient signal. Any claim that shaping caused an
improvement must survive that observation.

## 5. What is frozen before optimization

Masks, action eligibility, log-probabilities, stale-policy behaviour, invalid-trace handling and
optimizer/RNG/memory restoration are frozen **before** any optimizer runs, per D17. None is specified here
because none is implemented; W6 owns them.

## 6. Implementation status

**Not implemented.** No reward function, no learner, no optimizer exists in this project. This document is
the contract that W6 must satisfy, written now so that it cannot be adjusted after seeing results.
