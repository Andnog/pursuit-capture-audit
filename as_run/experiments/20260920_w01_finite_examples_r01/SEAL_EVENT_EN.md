# Seal event: this package was written to after it was sealed

Recorded: 21 September 2026, during W2. **The scientific rows were not affected.**

## What happened

This package was sealed on 20 September 2026. On 21 September, while verifying that the W0–W1 finite
examples still reproduce on a bare interpreter without the W2 dependency, `scripts/run_finite_examples.py`
was invoked against this package again. The script had no guard, so it rewrote files inside a sealed
package.

## Exactly what changed

| File | Status against the original seal |
|---|---|
| `results.jsonl` | **MATCHES** — byte-identical |
| `PROTOCOL_EN.md`, `plan.json`, `inputs.json`, `domain.json`, `environment.json` | MATCH |
| `DEVIATIONS_EN.md`, `SCIENTIFIC_DECISION_EN.md`, `first_run_record.json` | MATCH |
| `events.jsonl` | **CHANGED** — event timestamps only |
| `result.json` | **CHANGED** — `resources.cpu_seconds`, `resources.wall_seconds` and the unit-test count only |

`results.jsonl` carries every case outcome and every asserted-field comparison. It is **byte-identical to
the seal**, so no scientific quantity changed. The per-case statuses remain 14/14 PASS and the gate verdict
remains `SUPPORTED`.

The unit-test count in `result.json` rose from 58 to 145 because W2 added test modules. That is a true
statement about the rerun, not a change to the W1 result.

## Original seal, preserved

The original `checksums.json` hashes are preserved verbatim under `superseded_seal` in the current
`checksums.json`, so the pre-event state remains auditable. The two changed files can be identified against
it at any time.

## Why the source hashes in `inputs.json` no longer match the working tree

Separately, W2 introduced `ruff` and reformatted the source. Twelve of the sixteen implementation files
recorded in `inputs.json` now hash differently. **The frozen expectation files
(`configs/finite_examples_v1.json` and `tests/fixtures/finite_cases_v1.json`) are unchanged**, so the
answers this package was checked against are exactly the ones that were frozen before implementation.

`inputs.json` is left untouched: it is the honest record of the source that produced the original run. The
W2 package re-runs these fourteen cases against the reformatted source and records the new hashes, so the
result is shown to survive the change rather than assumed to.

## Corrective action

`scripts/run_finite_examples.py` now **refuses** to write into a package containing `checksums.json` unless
`--reseal` is passed explicitly. The same accident had already occurred once inside W1 as deviation D-04;
it will not occur a third time by accident.
