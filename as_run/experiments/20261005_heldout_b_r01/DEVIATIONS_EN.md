# Deviations — held-out B evaluation (A-138)

## 1. The run was stopped after 12 episodes, before any result was read (5 October 2026, 21:21)

The evaluation was launched at 21:20 with three workers and stopped one minute later, with 12 episodes written
(all of the first city in task order).

**Reason.** A second working session on the same repository, started by the research lead to answer a fifth review,
had modified source modules that this evaluation imports (`evaluation/capture_judge.py`, `evaluation/capture_time.py`,
`rl/rollout.py`, `rl/transitions.py`) between 21:05 and 21:06, and was still working. These modules were not in the
list hashed in `inputs.json`, and further edits during the run would have produced one single-shot result from more
than one version of the sources.

**State.** The 12 rows are kept in `results.jsonl` and were not opened for their outcomes; only the number of rows
and the city were read. No summary exists. The four cities are not spent.

**Before restarting.** The other session is asked to state which sources it still changes and whether its changes
alter the outcome of valid episodes. The run restarts only on frozen sources, with `inputs.json` rewritten to hash
every module on the execution path. The 12 episodes are then run again by the resumable runner only if their
recorded sources match; otherwise they are moved aside, unread, and the evaluation starts from zero.

## 2. Restart on frozen sources (6 October 2026, 02:00)

- The other session stated that `src/` has been frozen since 21:06:29 on 5 October, that is, before the first launch
  at 21:20. This was checked here: the four modules it touched carry the hashes it reported, no Python file imported
  by this evaluation has changed since 21:20, and a diff against the source archive of 5 October (17:5x) shows two
  changes only: an invalid-value guard in `evaluation/capture_judge.py` and a new field in `rl/rollout.py`.
- 140 recorded episodes (OPTIMAL, GOAL-DIRECTED, AVOIDANT and RANDOM evaders, seven earlier cities) were re-run with
  the modified judge: 140 of 140 reproduce their recorded outcomes (`LEVELS_CHECK_judge_guard.json`).
- The 12 episodes of the first launch were therefore produced by the sources used now. They are kept and the
  resumable runner continues from them. Their outcomes had not been read.
- `inputs.json` now hashes every module under `src/joint_interception` and every imported script; the list of the
  first launch is kept inside it. The hashes are compared again when the run ends.
- **Judged with the guard in place.** A frame with a non-finite value, a negative speed or a non-positive dimension
  can no longer satisfy the capture predicate, and a trace that contains one is not a capture. The guard can remove a
  capture and cannot create one. The TEST evaluation of A-110 ran without it.
- The run was idle between 21:21 and 02:00 because the session that owns it was not woken by its notifications.
