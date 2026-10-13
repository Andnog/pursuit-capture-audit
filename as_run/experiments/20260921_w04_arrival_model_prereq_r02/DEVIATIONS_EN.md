# Deviations

Experiment: `20260921_w04_arrival_model_prereq_r02`. Stage: W4 prerequisite.

This revision exists **because** of a deviation in `r01`, recorded there as D-18: criterion A1 was
mis-specified and its verdict was withdrawn. `r01` is retained sealed rather than edited.

---

## D-19 — Criteria were re-frozen, and what that does and does not mean

**What happened.** `r02` freezes a new criterion set B1–B6, replacing A1 with a criterion that is decidable
from the available evidence.

**Why this is not criterion-shopping.** A1 was not replaced because it gave an unwelcome answer. It was
replaced because it could not give *any* answer: it tested the sign of a quantity recorded only as a
magnitude, and its underlying reasoning about direction was inverted. The replacement, B1, asks the prior
question — *can the direction be established from this record at all?* — and reports `UNRESOLVED` when it
cannot, rather than forcing a verdict.

**The check on this reasoning.** B2, B3, B4 and B5 are **carried over unchanged from r01** and produce
identical numbers. Only the defective criterion moved. And B2 refutes `UNDER` **independently of B1**, so
the operative conclusion does not rest on the criterion that was replaced.

---

## D-20 — Two runner defects, both caught by the run rather than by review

**What happened.** First, the criteria loop still enumerated the A-names after the measurement function had
been rewritten to emit B-names, so the run raised `KeyError: 'A1_lower_bound_soundness'`. Second, an earlier
textual patch had silently failed because `ruff format` had already collapsed the block it was matching.

**Why it matters.** The second is the more instructive: a string-matching patch applied after a formatter
had rewritten the target is a silent no-op, and the only reason it surfaced was that the first defect made
the run fail loudly. This is the fourth time in this project that a mechanical text edit has damaged or
failed to apply to source.

**Resolution.** Both fixed; the loop is now driven by a table keyed on the criterion names themselves, so a
renamed criterion cannot leave a stale enumeration behind. Lint and format were run to completion and the
package re-run afterwards, per amendment A-09.

**Effect on results.** None. No measurement was produced under either defect: the first prevented the run
from completing at all.

---

## Deviations that did not occur

No SUMO process start, no episode, no optimizer update, no checkpoint load, no TEST access. The historical
evidence package was opened **read-only and not modified**; its own seal is unchanged. **W4's two-CPU-hour
cap was not consumed** — this is a prerequisite recorded on its own engineering line. No frozen expectation
from any earlier stage was edited, and all 203 tests pass on both interpreters.
