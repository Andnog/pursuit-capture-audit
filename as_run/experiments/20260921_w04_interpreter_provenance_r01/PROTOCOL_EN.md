# Protocol — interpreter provenance of the test suite

## Claim class

**Software correctness only.** Nothing here bears on any scientific claim. No scientific verdict in this
project rests on a test count.

## Question

Does the interpreter recorded in each package's `environment.json` match the interpreter that actually
executed the test suite?

## Method, fixed before running

1. Resolve `uv run python` and `uv run pytest` to their executables independently.
2. Read `requires-python` from `pyproject.toml`.
3. Run the full suite under every available runner and compare, test by test, rather than by count alone.
4. Where two runners disagree on the same source, treat the **disagreement** as the finding, not either
   result.

## Acceptance rule, fixed before running

| Verdict | Condition |
|---|---|
| `CONSISTENT` | Every runner resolves to an interpreter satisfying `requires-python`, and all agree |
| `PROVENANCE_DEFECT` | A runner resolves outside the pin, or two runners disagree on the same source |
| `INCONCLUSIVE` | Only one runner is available |

A `PROVENANCE_DEFECT` requires a guard that makes the same defect fail loudly next time. **Correcting the
result without adding the guard does not close it.**

## Resource limits

No simulator, no optimizer, no checkpoint, no TEST split.
