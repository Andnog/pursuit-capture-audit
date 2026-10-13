# Protocol: W2 contracts, dependency lock and admission

Experiment ID: `20260921_w02_contracts_r01`. Created: 21 September 2026. Stage: W2.

## 1. Freeze status — stated precisely

The **acceptance rule was fixed before outcomes**: it was written into
`scripts/run_contract_checks.py` as the `gate.rule` string before the first execution, and has not been
changed since. This prose protocol was written **after** the first execution. That is a deviation from the
W1 practice of freezing the prose protocol first, and it is recorded as **D-06** in `DEVIATIONS_EN.md`.

W2 is an **engineering-acceptance** stage: it checks that contracts reject what they must reject, not
whether a scientific hypothesis holds. The freeze requirement is correspondingly weaker than for a stage
that measures an outcome. It is not waived, and the deviation is recorded rather than argued away.

## 2. What this package answers

Do the task contracts, schemas and semantic invariants reject missing and invalid critical fields; is the
simulator environment internally consistent; and do the W0–W1 finite results survive the source changes
introduced by W2?

## 3. Acceptance rule, as pre-registered in the runner

> `SUPPORTED` only if the preflight is consistent, every contract-check module passes, the W0–W1 regression
> is 14/14, and lint is clean.

Any other result is `NOT_SUPPORTED`. Claim class: **engineering acceptance only**.

## 4. The three groups

**Preflight.** `scripts/preflight.py` asks the SUMO binary and both Python bindings for their versions and
checks they agree. It **starts no simulation, steps no vehicle and writes no trace**. It exists because the
binary and the bindings come from different distribution channels on this platform: a binding that speaks a
different TraCI version returns *wrong state* rather than raising, which would corrupt every downstream
physical claim invisibly.

**Contract checks.** Ten test modules. The W2 modules skip when `jsonschema` is absent, so the W0–W1 finite
results remain reproducible on a bare interpreter with no third-party package.

**W0–W1 regression.** The fourteen frozen finite cases, re-run against the source as reformatted in W2, and
checked against the **unchanged** frozen expectations in `tests/fixtures/finite_cases_v1.json`. It writes
into this package and never into the sealed W1 package.

## 5. Resource limits

W2 permits no native campaign; additional engineering compute is recorded separately. **Executed: 0 SUMO
episodes, 0 optimizer updates, 0 checkpoint loads, 0 TEST accesses.** The only SUMO invocation was
`sumo --version`.

Dependencies were resolved and installed: this is the W2 dependency-lock task. `torch` was deliberately
**not** installed; it is pinned in an optional group and installing it is a W6 action with its own ledger
entry.

## 6. What a PASS does and does not establish

**Does establish:** the schemas reject every missing required field, out-of-range value, wrong enum and
unknown extra key; the semantic invariants reject records that are structurally valid but scientifically
wrong; body separation is computed geometrically and matches hand-derived values; the capture predicate's
four derived properties hold; the safety admission interface is trivalent and `UNKNOWN` never permits
execution; the simulator binary and bindings agree; the W0–W1 results survive the source change.

**Does not establish:** that any of this behaves correctly against a *real* simulator trace — no episode
has been run. Nor physical feasibility, protocol-supported assistance, learned acquisition, benefit,
transfer or novelty. The capture parameters are **proposed, not frozen**; D06 names the Research lead.

## 7. Outputs

`plan.json`, `inputs.json`, `domain.json`, `environment.json`, `events.jsonl`, `results.jsonl`,
`result.json`, `DEVIATIONS_EN.md`, `SCIENTIFIC_DECISION_EN.md`, `checksums.json`. Checksums are sealed only
after all writing has finished.
