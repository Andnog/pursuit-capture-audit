# Doctoral joint interception research

> **Current state (2026-10-04; see `governance/AMENDMENTS_EN.md` A-64 … A-116).** The sections below this note
> are historical (W0–W3) and are kept unchanged. Since A-64 every method is executed and judged in SUMO, and
> more than 100,000 episodes have been run. The TEST split was opened once, for the single-shot
> confirmation of A-110/A-111, and is now **spent** (`contracts/SPLIT_STATUS_EN.md`); the historical
> `contracts/split_manifest.json` still reads CLOSED and is not rewritten. The manuscript is in
> `docs/manuscript/ieee/`. An external review (A-115) led to a versioned audit addendum and a corrected learning
> study (A-116).
>
> **Update 2026-10-05 (A-117 … A-131).** Two further reviews were answered with versioned addenda. The manuscript is
> now an article (`main.tex`) plus a supplement (`supplement.tex`), organised around three findings. New sealed
> studies: an audit of the official environment of a published method (code in `third_party/`, not redistributed),
> a learner trained on the proximity endpoint, and three probes of the inherent limitations (kinematic model,
> background traffic, an evader tuned against the blocking controller). The evader has a fifth level, TUNED.
>
> **Update 2026-10-05, evening (A-133 … A-136).** A fourth review found a defect in the critic input and in the
> sampling seed of the MAPPO controllers. `native/mappo_ambush_v3.py` corrects both and the learning block was
> repeated; earlier conclusions about fine-tuning are withdrawn. The response to the review is in
> `docs/reports/20261005_fourth_review_response_EN.md`. Episode counts and the source-recoverability map are now
> produced by scripts (`scripts/count_episodes.py`, `scripts/build_source_status.py`).
>
> **Update 2026-10-06 (A-137 … A-142).** Two new sealed studies: an audit of a second published environment
> (PEPCRL-MVP, real map) and a second held-out set of four cities (HELD-OUT B: Denver, Vancouver, Barcelona, Buenos
> Aires; evaluated once and now **spent**, like TEST). A fifth review found two defects in the training loop of the
> learning studies, a capture-instant helper that did not reset on a missing vehicle, and a judge that accepted
> non-finite values. All are corrected in new or additive code (`rl/transitions.py`, `evaluation/capture_time.py`,
> `evaluation/capture_judge.py`, `scripts/train_mappo_v4.py`), with tests that reproduce each defect; no capture
> instant of the hold audit is affected. Response: `docs/reports/20261006_fifth_review_response_EN.md`.
>
> **Update 2026-10-06, afternoon (A-143 … A-145).** The learning block was repeated with the corrected loop
> (MAPPO-v4, `experiments/20261006_mappo_v4_r01`): neither registered primary was met and the conclusions of MAPPO-v3
> are unchanged. Log files of 14 sealed packages had lines appended by leftover simulator processes; the sealed
> content was intact and was restored with `scripts/repair_log_tails.py` (appended bytes kept in
> `provenance/log_tails/`). Leftover SUMO processes must be ended with `kill -9`, never with a plain `kill`.


Documentation baseline: 20 September 2026. Last updated: 21 September 2026.
**Implementation status: B0, W0–W1, W2, W3 and the W4 prerequisites complete. W4's decision blockers are cleared; implementation work remains.**
Scientific status: **analytical correctness and engineering acceptance supported; nothing else established.**

Research question: **Under what conditions does learning to select and maintain joint interception opportunities, represented by arrival-time windows and physical compatibility among pursuers, improve assisted capture of a moving evader and transfer to unseen cities, compared with policies without that representation and conventional cooperative planning?**

## Read in this order

1. [Research question, objectives and claim boundary](docs/RESEARCH_QUESTION_EN.md)
2. [English master plan v3](docs/DOCTORAL_MASTER_PLAN_EN_v3.md) — the governing specification
3. [Current project state](governance/PROJECT_STATE.json)
4. [Handoff: what exists, what runs, what is blocked](docs/HANDOFF_EN.md)
5. [Technical gap and novelty verdict](research/novelty/TECHNICAL_GAP_EN.md)
6. [Method specification](docs/METHOD_SPEC_EN.md)
7. [Legacy obligations](governance/LEGACY_OBLIGATIONS_EN.md) and [amendments](governance/AMENDMENTS_EN.md)
8. [Final documentary review](docs/FINAL_REVIEW_EN.md) and [frozen decision register](governance/DECISIONS_EN.md)

## What exists and runs

```bash
uv sync && uv run python scripts/preflight.py
```

```bash
uv run python scripts/run_contract_checks.py --package experiments/20260921_w02_contracts_r01
```

```bash
uv run python -m unittest discover -s tests -t tests
```

```bash
python3 scripts/verify_artifacts.py
```

**Run the tests through `uv run python -m unittest`, not through a bare `pytest`.** `pytest` is not a
declared dependency, so `uv run pytest` silently falls through to whatever `pytest` is on `PATH` — which on
this machine belongs to a **Python 3.10** install, while the project pins `==3.14.*`. Every test result
recorded before 2026-09-21 was measured that way. It mattered: Python 3.12 changed the tokenizer, and a
source-hygiene check that passed on 3.10 was inert on 3.14. `tests/test_interpreter_pin.py` now fails loudly
on any interpreter that does not satisfy `requires-python`. See `governance/AMENDMENTS_EN.md` A-34.

`python3 -m unittest discover -s tests -t tests` on a bare interpreter also works and skips the tests that
need third-party packages; it reports the skips rather than hiding them.

Dependencies are pinned and locked ([`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)). The SUMO binaries
come from the Eclipse SUMO distribution, **not** from pip, so `uv sync` alone is not a sufficient
environment — `scripts/preflight.py` blocks on a binary/binding version mismatch.

The W0–W1 finite examples deliberately require **no** third-party package and still run on a bare
interpreter, where the W2 test modules skip.

Nine sealed evidence packages:
[`20260920_w01_finite_examples_r01`](experiments/20260920_w01_finite_examples_r01/SCIENTIFIC_DECISION_EN.md)
— 14/14 frozen finite cases against expectations derived by hand before implementation; and
[`20260921_w02_contracts_r01`](experiments/20260921_w02_contracts_r01/SCIENTIFIC_DECISION_EN.md)
— preflight consistent, W0–W1 regression 14/14, lint clean; and
[`20260921_w03_adapter_r01`](experiments/20260921_w03_adapter_r01/SCIENTIFIC_DECISION_EN.md)
— 9/9 adapter checks, exact state restoration; and
[`20260921_w04_arrival_model_prereq_r02`](experiments/20260921_w04_arrival_model_prereq_r02/SCIENTIFIC_DECISION_EN.md)
— **`UNDER` refuted**, so no joint opportunity can ever be `SUPPORTED` from a predictive arrival model
(`…_r01` is retained sealed with its verdict withdrawn for a mis-specified criterion); and
[`20260921_w04_constructive_arrival_r01`](experiments/20260921_w04_constructive_arrival_r01/SCIENTIFIC_DECISION_EN.md)
— **`UNDER` sets can be produced and the label earned**, verified by integrating every schedule. 228 tests
on both interpreters.

## What this does not establish

Analytical correctness on a finite abstraction, and engineering acceptance of the contracts, are the two
weakest of the claim classes. **No** physical feasibility, runtime feasibility, protocol-supported
assistance, learned acquisition, benefit of the joint representation, benefit of commitment, transfer,
novelty, doctoral sufficiency or journal readiness is established. **No SUMO process has been started in this root** — the only SUMO invocation was `--version` — and no
optimizer run, checkpoint load or TEST access has occurred. The TraCI call surface is written but
**unexercised**; W4 exercises it for the first time, under its gate.

The capture parameters are **FROZEN** as of 21 September: capture is **contact-to-stop**, and **contact
alone is not capture** — coordination is required, which makes the endpoint stricter than proposed. The
evader is a **scripted difficulty level**, not a policy. See [`MAPS_STATUS.md`](MAPS_STATUS.md) for the 12
audited networks and the identified historical TEST set.

The W0 search established that three components of the proposed contribution are **prior art**: arrival-time
coordination among pursuers, nonconvex safe-interval representation with agent geometry, and learned
commitment/termination in multi-agent pursuit. The candidate contribution is the conjunction and the
empirical characterization, not any component. Two closure attempts on 21 September resolved the conventional planner (**CCBS**, complete and optimal),
conceded a **fourth** component (learned reachability-informed allocation), and left four families open —
**all of them blocked on access or on information outside this project**, not on effort. See the [technical gap](research/novelty/TECHNICAL_GAP_EN.md).

## Fresh-start policy

Research-specific implementation, configurations, datasets and trained policies are built afresh under this
root. Historical projects are evidence sources, not runtime dependencies: no legacy module is imported,
symlinked or executed, and no legacy weight, optimizer state, replay buffer or demonstration is loaded.
Standard external software such as SUMO and learning libraries may be used with pinned versions and
licenses. Inherited obligations and resource limits survive the restart and are recorded in
[`governance/LEGACY_OBLIGATIONS_EN.md`](governance/LEGACY_OBLIGATIONS_EN.md).

Earlier entry points describing assistance attribution as the principal contribution are historical;
attribution is a measurement component supporting the interception question.

All new scientific documents, code identifiers, configurations, reports, captions and manuscript material
are in English. Original source titles, immutable historical filenames and quotations retain their original
spelling with an English explanation where needed.

## A note on `governance/REVIEW_MANIFEST.json`

That manifest is the sealed record of the 2026-09-20 documentary review and is **not** updated as work
proceeds. Re-verifying it now reports one intentional mismatch, on this `README.md`, explained in
[`governance/AMENDMENTS_EN.md`](governance/AMENDMENTS_EN.md) A-05. Every other sealed file, and all thirty
historical seal checks, still match.
