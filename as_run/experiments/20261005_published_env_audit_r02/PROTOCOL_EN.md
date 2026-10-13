# Published-environment audit, addendum r02 (A-133, R4-B)

**Registered in:** `governance/AMENDMENTS_EN.md`, A-133, before any run of this addendum.

**Why.** The fourth independent review found two defects in the presentation of the sealed audit
(`experiments/20261005_published_env_audit_r01`):
- 12 of 577 first captures have less than 30 s of follow-up because the episode horizon ended;
- the "stopped for 2 s" analogue accepted two observations one second apart.

**What is run.** Versioned replays of sealed episodes. The sealed package is read and never written. The official
code runs unmodified, from byte-identical copies, exactly as in r01. No case is replaced.

1. **Follow-up completion.** The 12 censored episodes are re-run in follow-up mode with the horizon extended to the
   capture plus 30 s (only the `max_steps` parameter of the environment changes). Each must reproduce the sealed
   first event: same step, evader and pursuer.
2. **Stop analogue with a time-based duration.** The 800 published-mode episodes are re-run with an observer that
   records, per evader, the longest uninterrupted span in simulation seconds during which it is at most 1 m/s behind
   one and the same pursuer, itself at most 1 m/s. Two seconds need three consecutive 1 s observations. Each re-run
   must reproduce the sealed capture events, and the sealed function must return the sealed result.

**Outcomes (descriptive).**
- Follow-up marks at +1, +2, +5, +10 and +30 s with their denominators, before and after completion.
- Share of evaders stopped for at least 2 s behind one stopped pursuer; the earlier quantity, reported as "two
  consecutive observations".

**Execution note.** Before the run, 14 replays (the 12 follow-ups and two published-mode episodes) were executed
outside the evidence tree to check the script. All reproduced the sealed events. They are run again here.
