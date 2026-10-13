# Deviations

Experiment: `20260921_w04_constructive_arrival_r01`. Stage: W4 prerequisite.

Process rules from earlier stages were followed rather than breached: the protocol was written **before**
any implementation existed (D-06), and lint and format were run to completion **before** the run that
produced this package (A-09).

---

## D-24 — The first run was correctly held at `NOT_SUPPORTED` by its own gate

**What happened.** All six criteria passed on the first execution, but the gate returned `NOT_SUPPORTED`
because the acceptance rule includes lint, and the runner itself contained one over-long line.

**Why it is recorded rather than quietly fixed.** The gate behaved exactly as frozen: it refused to declare
success while a declared condition was unmet, even though the condition was trivial and unrelated to the
science. A gate that waives its own conditions when they are inconvenient is not a gate. The line was
fixed and the package re-run.

**Effect on results.** None on the six criteria, which passed identically in both runs.

---

## D-25 — Verification is by integration, never by the generating formula

**What happened.** Not a deviation but a discipline worth recording, because the alternative is the easy
default. Every check integrates the produced `SpeedProfile` and compares the result against the claimed
distance and time. No check re-applies the arithmetic that built the profile.

**Why it matters here more than usual.** This module *generates its own answers*. Checking a generator
against its own formula checks nothing: an error in the formula appears identically on both sides. The W1
fixtures had the same problem and solved it by deriving expectations by hand; the analogue for generated
output is to simulate it.

**Measured result:** across 400 sampled arrival times the worst distance error was `4.26e-14 m`, the worst
time error `0.0 s`, and there were `0` legality violations.

---

## D-26 — The interaction half of the problem is scoped out, and named

**What happened.** The generator accounts for a vehicle's own kinematics and for externally supplied
`blocking_windows`. It does **not** compute those windows from other participants' committed plans.

**Why.** That is the harder half: a self-consistent joint candidate requires each participant's schedule to
account for the others in the same candidate, which is a fixed-point problem rather than an independent
computation. Solving it needs the real network and is W4 work.

**Effect on results.** The `UNDER` label is earned **for the single-vehicle problem**. A joint opportunity
built from these sets is sound only where participants do not interact along their paths — which this
package does not check and does not claim.

---

## Deviations that did not occur

No SUMO process start, no episode, no optimizer update, no checkpoint load, no TEST access. W4's
two-CPU-hour cap was not consumed. No frozen criterion was edited after seeing a result. No earlier sealed
package was written to. No inherited counter was reset.
