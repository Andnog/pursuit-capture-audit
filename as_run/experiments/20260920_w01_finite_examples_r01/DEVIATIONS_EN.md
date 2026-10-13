# Deviations

Experiment: `20260920_w01_finite_examples_r01`. Stage W0–W1.

Every deviation from the frozen protocol is recorded here with what changed, when, and whether any
scientific quantity was affected. **The frozen expectation file `tests/fixtures/finite_cases_v1.json` was
never edited.** No case was removed, and no failure was hidden.

---

## D-01 — Switch-margin comparison was not reproducible at the boundary

**When.** During the first execution of the unit test suite, before the frozen cases were run.

**What happened.** `test_switch_requires_strictly_exceeding_the_margin` asserted that a candidate scoring
*exactly* at the switch margin must not trigger a switch. The implementation returned `SWITCH`. The cause
is binary floating point: `0.58 + 0.10` evaluates to `0.6799999999999999`, so the test
`0.68 > 0.58 + 0.10` is `True`.

**Why it matters.** The `switch_margin` hysteresis is the entire mechanical difference between the `J0` and
`J1` arms. If its boundary behaviour depends on floating-point representation error, the two arms are not
reproducibly distinguishable, and a later ablation could attribute to *commitment* an effect that is
actually representation noise.

**Resolution.** `select_action` now requires `score(best) > score(committed) + switch_margin + TOLERANCE`
with `TOLERANCE = 1e-9`. A comment in the source records the reason.

**Effect on results.** None on the frozen cases. Case F6 compares `0.62` against `0.58 + 0.10`; `0.62` is
below the margin under either comparison, so F6's expected answer was unaffected. This deviation was found
by a property test, not by a frozen case.

---

## D-02 — Dependency scanner matched prose instead of imports

**When.** First execution of the unit test suite.

**What happened.** `test_package_uses_standard_library_only` scanned source text for lines beginning with
`import` or `from` and treated the following token as a module name. A docstring line beginning
`from the ...` was read as an import of a module named `the`, and the test failed.

**Why it matters.** A defective check is worse than no check: it produces noise that invites disabling the
test, and the property being checked — that W0–W1 introduces no external dependency — is a real
constraint of this stage.

**Resolution.** The scanner now parses each module with `ast` and inspects `ast.Import` and
`ast.ImportFrom` nodes, skipping relative imports. `ast` and `__future__` were added to the allowed set.

**Effect on results.** None. This was a defect in the test, not in the package under test. The property it
checks holds: the package imports only the standard library.

---

## D-03 — Runner comparator applied exact equality to an interval field

**When.** First execution of `scripts/run_finite_examples.py` against this package.

**What happened.** The comparator dispatched interval-aware comparison only for fields literally named
`joint_window` or `hull_window`. Case F4 asserts a field named `b1_joint_window`, which fell through to
exact equality and compared a tuple of pairs against an equal list of pairs. The first run therefore
recorded **13/14 PASS with F4 FAIL** and the gate verdict `NOT_SUPPORTED`, although the observed and
expected values were numerically identical:

```
observed=((9.0, 14.0),)   expected=[[9.0, 14.0]]
```

**Why it matters.** This is an evidence-tooling defect that produced a false negative. A false negative is
less dangerous than a false positive, but it is still a defect in the instrument that decides a gate, and
it is recorded rather than quietly corrected.

**Resolution.** The comparator now dispatches interval comparison for any field whose name ends in
`window`. The package was rerun.

**Effect on results.** The gate verdict changed from `NOT_SUPPORTED` to `SUPPORTED`. **No scientific
quantity changed**: the implementation produced the same value in both runs, and the frozen expectation was
not edited. Only the comparison of two equal values was corrected.

---

## D-04 — The first run's output files were overwritten

**When.** At the rerun described in D-03.

**What happened.** The rerun wrote `events.jsonl`, `results.jsonl` and `result.json` in place, overwriting
the first run's copies before they had been preserved.

**Why it matters.** The master plan requires that failed runs be retained and that packages not be
overwritten. Overwriting a failing run, even when the failure is an instrument defect, weakens the audit
trail.

**Resolution.** `first_run_record.json` preserves the first run's summary counts and the failing row
verbatim, as captured before the overwrite. The full first-run `events.jsonl` and `results.jsonl` **could
not be recovered and do not exist**; this is stated rather than reconstructed. Future packages must write
each execution into its own revision directory before any rerun.

**Effect on results.** None on the reported values. The loss is one of audit completeness, not of
correctness.

---

## D-05 — A soundness error in the specification was corrected before freezing

**When.** While deriving the expected answers by hand, before the fixture was frozen and before any
implementation existed.

**What happened.** The first draft of `METHOD_SPEC_EN.md` §2.3 stated that rejection on temporal grounds
was permitted when the arrival sets were labelled `OVER` **or** `UNDER`. That is unsound for `UNDER`: an
under-approximation is a subset of the true reachable set, so an empty intersection of under-approximations
does not prove that the true sets fail to intersect.

**Why it matters.** Had it survived, the implementation would have been able to emit `REJECTED` without
warrant, discarding opportunities that may in fact exist — the mirror image of the `SUPPORTED`-without-
warrant error that Rule A prevents.

**Resolution.** Rule B now requires **all** participating sets to be `OVER`. Where `UNDER` sets have an
empty intersection, the verdict is `UNKNOWN`. The `combine_direction` helper was removed, because mixing
directions bounds the truth in neither direction and no single "combined direction" is meaningful.

**Effect on results.** The corrected rule is what the fixture was derived against and what the
implementation was written against. Case F3 carries both variants explicitly: `OVER` labels give
`REJECTED`, and the identical sets with `UNDER` labels give `UNKNOWN`. This deviation is recorded because
the correction happened after the specification document was first written, not because it affected a
result.

---

## Deviations that did not occur

No SUMO episode, optimizer update, checkpoint load or TEST access was performed. No legacy runtime module
was imported or executed. No external dependency was installed. No frozen expectation was edited. No case
was excluded from the denominator. No historical file, sealed package, dirty file or untracked file was
modified.
