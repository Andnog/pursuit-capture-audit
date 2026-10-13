# Reproduce the study

Four levels, from seconds to days. Each level checks something different, and none depends on trusting the one
before it.

| Level | Question it answers | Needs |
|---|---|---|
| [0. Verify](#level-0--verify-the-evidence) | Is this the sealed evidence? | Python |
| [1. Recompute](#level-1--recompute-the-numbers) | Do the numbers of the article follow from the sealed records? | Python |
| [2. Replay](#level-2--replay-sealed-episodes) | Do sealed episodes come out the same in the simulator? | SUMO 1.21 |
| [3. Run again](#level-3--run-a-study-again) | Does a study, run from scratch, give the same result? | SUMO 1.21, hours to days |

## Requirements

| What | Version | For |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | any recent | every level; it installs Python and the packages |
| Python | 3.14 | installed by uv; the frozen code is pinned to it |
| [Eclipse SUMO](https://eclipse.dev/sumo/) | **1.21.0** exactly | levels 2 and 3 |
| PyTorch | 2.14.0 | levels 2 and 3 (`uv sync --extra learning` in `as_run/`): the simulation workers load it, also in the studies that train nothing |

The repository has two environments. The library (`src/pursuit_audit`, this directory) needs nothing beyond the
standard library. The frozen code (`as_run/`) has its own pinned environment (`as_run/pyproject.toml`,
`as_run/uv.lock`); commands that run it are given from inside `as_run/`.

```bash
git clone https://github.com/Andnog/pursuit-capture-audit.git
cd pursuit-capture-audit
uv sync                                      # the library and its tests
(cd as_run && uv sync --extra learning)      # the frozen code, with PyTorch
```

## Level 0 — verify the evidence

Every evidence package was sealed when its last writer ended: `checksums.json` holds the SHA-256 of each of its
files.

```bash
uv run pursuit-audit verify
```

Expected: `832 sealed files present and identical`, `126 sealed files not in this copy`, `0 packages with a file
that differs from its seal`. The 126 absent files are the heavy ones (run logs, pickled training states,
animations). They are in the data archive, and `as_run/SNAPSHOT.json` lists each with its size and its sealed
checksum; with the archive unpacked over `as_run/experiments/`, the same command reports them as present.

## Level 1 — recompute the numbers

**From the raw records, with independent code.** The library recomputes the headline contrasts of both held-out
evaluations from their per-episode records (`results.jsonl`) with its own statistics, and compares each with the
sealed value, to the last stored digit:

```bash
uv run pursuit-audit recompute
```

Expected: `13 of 13 recomputed values equal the sealed ones`. Among them are the two primary results:
predictive lane blocking minus pursuit, `[0.1453, 0.0855, 0.2073]` on TEST and `[0.0643, 0.0145, 0.1139]` on
HELD-OUT B (estimate and 97.5 % family interval).

**Every number of the article.** The table of the 113 values that the article states, each derived from a sealed
summary:

```bash
make numbers                 # rewrites results/ARTICLE_NUMBERS.md; `make check-results` fails if it changes
```

**The count of simulations and the figures**, from the frozen scripts:

```bash
cd as_run
uv run python scripts/count_episodes.py                    # 197 655 evaluation episodes, and the rest
uv run --with matplotlib python scripts/make_figures.py    # the figures, from the sealed packages
```

**The tests.** The library's tests include the equivalence of its capture rule with the judge that scored the
study (20 000 random situations and 400 random traces), and the frozen code has its own suite:

```bash
uv run pytest                                                           # the tests of the library
(cd as_run && uv run python -m unittest discover -s tests -t tests)     # 528 tests of the frozen code
```

In this copy the frozen suite reports 526 passes, one skip and one error: that test reads the pickled training
state of a learning study, a heavy file that is in the data archive. Without PyTorch, 21 more tests report an
import error.

## Level 2 — replay sealed episodes

Install SUMO 1.21.0 and make it visible, either with `SUMO_HOME` or by having `sumo` on the `PATH`. Then check the
installation; this starts no simulation:

```bash
cd as_run
uv run python scripts/preflight.py           # must end with "ok": true
```

The preflight compares the version that the binary reports with the versions of the two Python bindings. It
matters: a binding that speaks another version of the protocol returns wrong vehicle states instead of an error.

Replay a few sealed captures. The hold audit replays each captured episode twice, once as sealed and once with the
pursuers held, and checks that the first replay reproduces the sealed capture:

```bash
uv run python scripts/audit_d06_persistence.py --package /tmp/replay_demo --limit 6 --workers 2
```

It writes to the new directory that you name, never to a sealed package. `--limit` takes the first tasks only;
without it the script replays all 1 433 captures of that audit. Each line of `/tmp/replay_demo/results.jsonl`
should say `"reproduced": true`, and should equal the line with the same key in the sealed package
(`experiments/20261003_d06_persistence_audit_r01/results.jsonl`):

```bash
cd .. && uv run python tools/compare_runs.py as_run/experiments/20261003_d06_persistence_audit_r01 /tmp/replay_demo
```

Checked on 13 October 2026 from this copy: 6 of 6 replays reproduced the sealed capture and gave records identical
to the sealed ones.

Simulations are deterministic for a given scenario, seed and SUMO build. The study checked this at every audit:
replays reproduced every sealed outcome that was run again. On another platform or build of SUMO, small numerical
differences can change individual episodes; compare summaries in that case, not single records.

## Level 3 — run a study again

Every study follows the same pattern. Its script takes the directory of an evidence package, runs in chunks that
can be resumed, and writes its records and its summary there.

```bash
cd as_run
uv run python scripts/<script>.py --package experiments/<name>_rerun --workers 8 --budget-min 25
```

- `--package` is the output directory. **Give a new name.** The sealed packages are the evidence of the article and
  must stay as they are; a script that is pointed at a sealed package would add to it.
- `--budget-min` is the length of one chunk, in minutes. When a chunk ends, run the same command again: it resumes
  from the records already written. Repeat until it reports that nothing is left and writes `summary.json`.
- `--workers` is the number of parallel simulations.
- Some scripts have a quick mode for a first check (`--limit N`, `--smoke`, `--devcheck`); see `--help`.

When the run is complete, seal the new package and compare it with the sealed one:

```bash
uv run python scripts/package_tools.py seal --package experiments/<name>_rerun
uv run python scripts/package_tools.py verify --package experiments/<name>_rerun
cd .. && uv run python tools/compare_runs.py as_run/experiments/<name> as_run/experiments/<name>_rerun
```

`compare_runs.py` matches the per-episode records of the two packages by key and reports how many are identical,
and which fields differ in the others.

### Which script for which result

[`results/STUDIES.md`](results/STUDIES.md) lists the 90 sealed studies with the script of each, and gives the
command for every study that the article rests on. `uv run pursuit-audit studies --article --commands` prints the
same list. [`results/EVIDENCE_MAP.md`](results/EVIDENCE_MAP.md) goes the other way: from each claim of the article
to the package, the file and the key that hold it.

The main ones:

| Result of the article | Package | Script |
|---|---|---|
| Parameters of predictive lane blocking | `20261002_ambush_optimization_r01` | `run_ambush_optimization.py` |
| Single-shot evaluation, TEST cities | `20261003_test_confirmation_r01` | `run_test_confirmation.py` |
| Single-shot evaluation, HELD-OUT B cities | `20261005_heldout_b_r01` | `run_heldout_b.py` |
| Hold audit of operational capture | `20261003_d06_persistence_audit_r01` | `audit_d06_persistence.py` |
| Null team, joint escape, clustered intervals | `20261004_audit_addendum_r01` | `audit_addendum.py`, `addendum_reanalysis.py` |
| Coordination ablation, active-escape probe | `20261004_audit_addendum_r03` | `audit_addendum_r03.py`, `addendum_r03_reanalysis.py` |
| Goal-directed evader | `20261003_goal_evader_r01` | `run_goal_evader_study.py` |
| Evader tuned against the controller | `20261005_tuned_evader_r01` | `run_tuned_evader_study.py` |
| Kinematic models | `20261005_kinematic_sensitivity_r01` | `run_kinematic_sensitivity.py` |
| Background traffic | `20261005_traffic_sensitivity_r01` | `run_traffic_sensitivity.py` |
| Published environment, DGMARL-MVP | `20261005_published_env_audit_r01` | `audit_published_env.py`, `analyse_published_env.py` |
| Published environment, PEPCRL-MVP | `20261005_published_env_pepcrl_r01` | `audit_published_env_pepcrl.py` |
| Learning, final implementation | `20261006_mappo_v4_r01` | `train_mappo_v4.py`, `analyse_mappo_v4.py` |

### Notes for particular studies

- **Order.** The parameter search (`run_ambush_optimization.py`) comes first: later studies read the selected
  parameters from its package. To run everything again from nothing, follow the date order of
  `results/STUDIES.md`; to run one study again, the sealed packages that it reads are already in place.
- **Held-out evaluations.** TEST and HELD-OUT B were each evaluated once, with frozen methods. Running them again
  is a replication of a registered analysis, not a place to try variants: a result chosen after looking at these
  cities is no longer held out.
- **Learning studies** (`train_*.py`). The final one made 16 384 training attempts and about 22 000 test episodes;
  it took about nine hours on eight workers.
- **Models with Kolmogorov–Arnold networks** (`kan_capture_law*.py`, `interpretability_*.py`) need two more
  packages: `uv run --with pykan --with scikit-learn python scripts/<script>.py ...`.
- **Published environments.** Clone the two repositories at the commits given in
  [`THIRD_PARTY.md`](THIRD_PARTY.md) into `as_run/third_party/` first.
- **Road networks.** The fifteen city networks are in `as_run/assets/` (`osm/` and `osm_b/`), with the checksums
  that the study recorded in `as_run/MAPS_STATUS.json`. They are derived from OpenStreetMap (ODbL). Run the scripts
  from `as_run/`: the paths in that file are relative to it.
- **Registration.** Each package has its `PROTOCOL_EN.md`, written before the runs, and its
  `SCIENTIFIC_DECISION_EN.md`, written after. The amendments that registered and reported every study are in
  `as_run/governance/AMENDMENTS_EN.md`.

## What cannot be reproduced exactly

- Packages store the hashes of their sources, not complete copies. For some earlier studies the code at launch
  cannot be recovered in full; `as_run/provenance/PACKAGE_SOURCE_STATUS.json` says which, package by package, and
  `as_run/provenance/` holds the source archives that exist.
- The audits of the published environments used the released configurations and a later version of the simulator
  than those articles; they are reproducible as run here, not as a reproduction of those articles.
