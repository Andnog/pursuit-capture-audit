# Reproduce

Four levels, from seconds to days. The full instructions, with every command, are in
[`REPRODUCE.md`](https://github.com/Andnog/pursuit-capture-audit/blob/main/REPRODUCE.md).

| Level | Question it answers | Needs |
|---|---|---|
| 0. Verify | Is this the sealed evidence? | Python |
| 1. Recompute | Do the numbers of the article follow from the sealed records? | Python |
| 2. Replay | Do sealed episodes come out the same in the simulator? | SUMO 1.21 |
| 3. Run again | Does a study, run from scratch, give the same result? | SUMO 1.21, hours to days |

## Without a simulator

```bash
git clone https://github.com/Andnog/pursuit-capture-audit.git
cd pursuit-capture-audit
uv sync

uv run pursuit-audit verify       # 832 sealed files, each against its checksum
uv run pursuit-audit recompute    # 13 headline results, from the per-episode records
uv run pytest                     # the tests, with the equivalence of the capture rule
```

`verify` reports the sealed files that are present and identical, those that are absent from this copy (the heavy
ones, which are in the data archive) and those that differ, of which there should be none.

`recompute` starts from the raw records of the two held-out evaluations, computes each contrast with the library's
own statistics, and compares it with the sealed value.

## With the simulator

```bash
cd as_run
uv sync --extra learning
uv run python scripts/preflight.py                 # checks the installation; runs nothing
uv run python scripts/audit_d06_persistence.py --package /tmp/replay_demo --limit 6 --workers 2
cd .. && uv run python tools/compare_runs.py as_run/experiments/20261003_d06_persistence_audit_r01 /tmp/replay_demo
```

The second command replays six sealed captures, and the third compares the new records with the sealed ones. When
we ran this from the public copy, six of six were identical.

## Run a study again

Every study has one script, which takes the directory of a new evidence package and runs in chunks that can be
resumed:

```bash
cd as_run
uv run python scripts/run_heldout_b.py --package experiments/heldout_b_rerun --workers 8 --budget-min 25
```

The [list of studies](https://github.com/Andnog/pursuit-capture-audit/blob/main/results/STUDIES.md) gives the
script and the command of each of the 90 sealed studies. Give a new package name: the sealed packages are the
evidence of the article and must stay as they are.

## Two layers

The repository keeps the code that produced the results (`as_run/`) exactly as it ran, and next to it a library
written to be read and reused (`src/pursuit_audit/`). The library is compared with the frozen code by tests: its
capture rule on 20 000 random situations and 400 random traces, its confidence intervals on the sealed records.
A cleaned-up copy alone would not be evidence; the frozen copy alone would be hard to read. Both are here.
