# Deviations — robustness study r01

1. **Chunked execution.** The first launch was stopped by the session's background-task time limit (30 min) after
   4,000 of 22,980 episodes. All 4,000 recorded lines are complete and parse. A resume option was added to
   `scripts/run_robustness_study.py` (skip recorded episodes, append, stop after `--max-episodes`). The episode
   function (`task`), the scenario list and every setting are unchanged. Episodes are deterministic per
   (scenario, seed, run), so chunks compose exactly. The script hash after the change is
   ad55939afadf3fa3d6741126078af245f83b80b7e71f15230c6dbb07aca7c9fc; the launch hash is in `inputs.json`.
2. **Shared machine.** Other SUMO processes, not part of this project's run, were active on the machine during
   execution. This affects wall time only.
