# Decision — interpreter provenance

**Claim class: software correctness.** Nothing here supports or weakens any scientific claim.

## Verdict

`PROVENANCE_DEFECT_CORRECTED_AND_GUARDED`.

## The defect

`pyproject.toml` pins `requires-python = "==3.14.*"`. **`pytest` is not a declared dependency.** So
`uv run pytest` never used the virtual environment — it took the first `pytest` on `PATH`, belonging to a
**Python 3.10** framework install:

```
uv run python  -> .venv/bin/python3                                    3.14.6
uv run pytest  -> /Library/Frameworks/Python.framework/Versions/3.10/bin/pytest
```

Each package's `environment.json` reports `platform.python_version()` measured by a **sibling** process
launched with `uv run python` — genuinely 3.14.6. The record was true about a process that was not the one
running the tests. **Nothing in the evidence made the split visible.**

## Why it was not harmless

Python 3.12 replaced the single `STRING` token for an f-string with an
`FSTRING_START` / `FSTRING_MIDDLE` / `FSTRING_END` group. The glued-concatenation guard — itself added after a
real defect wrote `"is apinned"` into the provenance record — walks `STRING` tokens.

On 3.10 it inspected f-strings. **On the interpreter this project pins, it skipped every one of them**, while
reporting as passing. A guard written to catch silent corruption had itself gone silently partly inert.

## How it surfaced

Not by inspection, and not by any count. A new assertion — *"f-strings must be checked, not skipped"* —
**passed** under `uv run pytest` and **failed** under `python3 -m unittest` on 3.14. Two runners disagreeing
about the same source is what exposed it. Had only one runner ever been used, the defect would have stayed.

## Corrections

1. `glued_concatenations` rejoins `FSTRING_*` groups into a single literal, with depth counting so nested
   f-strings are handled.
2. `static_edges` replaces `ast.literal_eval`, which raises on an f-string. Parsing yields the static text
   around the substitutions — exactly what a glued concatenation corrupts. An edge that is a substitution
   yields "nothing to glue", which is correct.
3. **The detector now has a test that it detects**, with four cases including the f-string one. It had none.
   That absence is why it could go inert unnoticed, and it is the more important of the two defects.
4. `tests/test_interpreter_pin.py` asserts the running interpreter satisfies `requires-python`, using no
   third-party import and no `tomllib` so that it runs on the wrong interpreter and reports it.
5. README states the canonical runner.

## Measured result

| Runner | Interpreter | Exit | Result |
|---|---|---|---|
| `uv run python -m unittest discover -s tests -t tests` | 3.14.6, venv, deps present | 0 | **264 passed, 0 skipped** |
| `python3 -m unittest discover -s tests` | 3.14.6, bare | 0 | 264 passed, **168 skipped** (deps absent, skips reported) |
| `uv run pytest` | **3.10** | 1 | **fails by design** on the interpreter-pin check |

**The first row is the first full-suite result actually measured on the interpreter this project pins.**

## Correction of record

Sealed packages are **not** edited. **Any test count in a package sealed before 2026-09-21 was measured on
Python 3.10**, whatever the `python_version` field beside it says.

**No scientific verdict is withdrawn.** No verdict in this project rests on a test count. The arrival-model
refutation, the constructive-witness result and the evader ordering were each measured by scripts run under
`uv run python`, which resolved correctly to 3.14.6 throughout.

## Rule adopted

**A recorded interpreter version must be measured by the process that ran the work, not by a sibling
process. A runner that is not a declared dependency is not a pinned runner.**
