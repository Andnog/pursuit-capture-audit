# Deviations

Experiment: `20260921_w02_contracts_r01`. Stage W2.

**No frozen expectation was edited.** The two files holding the W0–W1 answers hash identically to the
values recorded in the W1 package.

---

## D-06 — The prose protocol was written after the first execution

**What happened.** The acceptance rule was fixed before outcomes, as the `gate.rule` string in
`scripts/run_contract_checks.py`, and has not changed. `PROTOCOL_EN.md`, however, was written after the
first execution — unlike W1, where the prose protocol came first.

**Why it matters.** The ordering discipline exists so a rule cannot be shaped around a result. Here the
machine-readable rule genuinely preceded the run, so the substance is intact, but the practice slipped.

**Effect on results.** None. The gate rule that decided the verdict is byte-identical to the one written
before the first execution.

**Corrective action.** Future packages write `PROTOCOL_EN.md` and `protocols/<experiment_id>.json` before
the first execution, as W1 did.

---

## D-07 — The schemas under-specified what master plan §14 requires

**What happened.** `test_every_required_result_field_is_enforced` failed on six fields:
`endpoint_time_s`, `safety_failures`, `guard_interventions`, `commitment_switches`, `assistance_label` and
`reasons`. They were present in the example record but absent from the schema's `required` list.

**Why it matters.** Master plan §14 states that each `results.jsonl` row includes the assistance label,
reasons, endpoint time and guard count. The schema did not enforce them, so a row could have omitted an
assistance label entirely and still validated. **The test found a real gap between the plan and the
contract**, not a test defect.

**Resolution.** All six were added to `required`. Several remain nullable, because "absent" and "known to
be inapplicable" are different statements and must stay distinguishable.

---

## D-08 — The prohibited-field check matched prose, recurring the W1 D-02 defect

**What happened.** `observation_invariants` derived tokens from the human-readable information-boundary
list and matched them against records. The first token of *"evader route file or any future evader
position"* is `evader`, which is a legitimate `vehicle_class`. Every valid observation was rejected.

**Why it matters.** This is the same anti-pattern as W1 deviation D-02 — treating prose as if it were
machine-readable — reappearing in a different module. Recurrence is the finding.

**Resolution.** `configs/domain_v1.json` now carries a separate machine-readable
`prohibited_observation_keys` list, checked recursively by key name. The prose list is explicitly marked as
prose that must not be pattern-matched. A test asserts both that `internal_memory` is caught and that a
legitimate `evader` class is **not** flagged.

---

## D-09 — Three test failures from asserting on hard-wrapped prose

**What happened.** Three separate assertions failed because the phrases they searched for were split across
lines or interrupted by markdown emphasis: `not a **formally synthesised shield**`, and
`It is not assigned an\ninvented reward`.

**Why it matters.** Each failure was spurious — the documents said exactly what was required. A test that
fails for formatting reasons trains the reader to ignore it, and one of these assertions dumped an entire
document into the failure output.

**Resolution.** A shared `document_text` helper reads a document with whitespace collapsed and emphasis
markers removed. All document-content assertions now use it and carry short failure messages.

---

## D-10 — The preflight mixed machine and human output on stdout

**What happened.** `scripts/preflight.py` printed its JSON report and then a human summary line, both to
stdout. The W2 runner could not parse the result and recorded the preflight as FAILED with
"preflight produced no parsable report" — although the environment was in fact consistent.

**Why it matters.** The preflight is the gate that blocks native work on a binary/binding mismatch. A gate
whose output cannot be read by the tool that consumes it is not a gate. The failure was safe in direction
(it blocked rather than passed), but the mechanism was wrong.

**Resolution.** stdout now carries only the machine-readable report; human lines go to stderr.

---

## D-11 — A sealed package was written to, and the tool now refuses

**What happened.** While verifying that the W0–W1 examples still run on a bare interpreter,
`scripts/run_finite_examples.py` was invoked against the already-sealed W1 package and rewrote its
`events.jsonl` and `result.json`.

**Why it matters.** This is the second occurrence of the same accident; the first is W1 deviation D-04.
Twice is a tooling problem, not carelessness.

**Effect on results.** **None.** `results.jsonl`, which carries every case outcome and every asserted-field
comparison, is **byte-identical to the original seal**. Only event timestamps and the cpu/wall timings
changed. This is documented in `../20260920_w01_finite_examples_r01/SEAL_EVENT_EN.md`, and the original
hashes are preserved under `superseded_seal` in that package's re-issued `checksums.json`.

**Corrective action.** Both runners now **refuse** to write into a package containing `checksums.json`
unless `--reseal` is passed explicitly. Verified: the refusal exits 2 without writing.

---

## D-12 — Source reformatting changed hashes recorded by the W1 package

**What happened.** W2 introduced `ruff` and reformatted the source. Twelve of the sixteen implementation
files recorded in the W1 package's `inputs.json` now hash differently.

**Why it matters.** The master plan requires recording the source actually executed. The W1 package records
source that no longer exists on disk in that exact form.

**Resolution.** `inputs.json` in the W1 package is left untouched — it is the honest record of what
produced that run. This package re-runs the same fourteen cases against the reformatted source and passes
**14/14** against the **unchanged** frozen expectations, so the result is demonstrated to survive the
change rather than assumed to.

---

## Deviations that did not occur

No SUMO episode was executed; the only invocation was `sumo --version`. No optimizer update, checkpoint
load or TEST access. No legacy runtime module imported or executed. No frozen expectation edited. No
inherited counter reset. No historical file, sealed package, dirty file or untracked file in either legacy
runtime root modified. `torch` was deliberately not installed.
