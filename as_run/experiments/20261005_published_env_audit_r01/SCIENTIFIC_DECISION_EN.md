# Scientific decision — capture events in a published pursuit environment (A-126, stage A)

**Status:** complete. 1,600 of 1,600 episodes, no failure. Descriptive study; no hypothesis test was registered.

## What was run

The official DGMARL-MVP environment (commit `62bd72e2`), unmodified, from byte-identical copies
(`third_party_hashes.json`). Two released scenarios, two teams (random turns; shortest-path chaser), two modes
(unmodified with an observer; first captured evader not removed and followed for 30 s). Same seeds across teams and
modes.

## Results

| | P4–E2 null | P4–E2 chaser | P7–E4 null | P7–E4 chaser |
|---|---|---|---|---|
| Episodes | 300 | 300 | 100 | 100 |
| Published success (all evaders captured in 800 steps) | 42.7 % [37.3, 48.3] | 4.0 % [2.0, 6.3] | 39.0 % [30.0, 48.0] | 2.0 % [0.0, 5.0] |
| Capture events | 398 | 139 | 325 | 137 |
| … same lane | 0 | 0 | 0 | 0 |
| … opposite directions | 82.9 % | 59.7 % | 82.5 % | 70.8 % |
| … inside a junction | 17.1 % | 40.3 % | 17.5 % | 29.2 % |
| … evader faster than 1 m/s | 75.6 % | 90.6 % | 70.5 % | 89.0 % |
| First capture, evader not removed: over 50 m from every pursuer at +10 s | 94.7 % [92.1, 97.4] | 92.8 % [88.0, 96.8] | 95.0 % [90.0, 99.0] | 92.5 % [86.2, 97.5] |
| … within 5 m of its captor at +5 s | 0 % | 0 % | 0 % | 0 % |
| … median distance to its captor at +30 s | 440 m | 422 m | 449 m | 420 m |

Intervals are episode-level percentile bootstraps (10,000 resamples). Full figures: `summary.json`.

## Findings

1. **The prediction recorded before the run held.** None of the 999 capture events joined two vehicles in the same
   lane. The published rule (front-bumper distance below 5 m, 5 m vehicles, one lane per direction) is met by vehicles
   that pass each other or cross inside a junction.
2. **A team that does not pursue meets the published success criterion in about 40 % of episodes** (42.7 % and
   39.0 %). A team that chases its evader by shortest path meets it in 2–4 %, because chasing places the pursuer
   behind the evader, where the rule cannot fire.
3. **The captured evader is not held.** With the evader left in the simulation, the first capture was the same event
   as in the unmodified run in every episode (577 of 577). Five seconds later no evader was within 5 m of its captor;
   ten seconds later 93–95 % were more than 50 m from every pursuer.
4. The pursuers' action space is a turn at each junction. It contains no action to stop or wait, so an operational
   stop cannot be commanded in this environment. 3–4 % of evaders stopped for 2 s behind a stopped pursuer, in
   ordinary queues.

## What this does and does not show

- It shows what the released environment's endpoint rewards: crossing the evader's path.
- It is **not** a reproduction of the article and **not** evidence about the published learner. The learner was not
  trained (stage B was not run). The release differs from the reported configuration (learning rates 1e-12 against
  1e-4; lane speed 13.9 m/s against a reported maximum of 20 m/s; no trained weights). SUMO 1.21 was used; the
  authors' version is not stated.
- The article reports success rates of 0.77–0.91 (P4–E2) and 0.73–0.81 (P7–E4) for four learned methods. The null
  team reaches about half of those values. The comparison is indicative only, for the reasons above.
- The article does not state the capture distance. The rule audited here is the one in the released code.

## Execution record

- Design and prediction registered in A-126 and its clarification before any run.
- Eight episodes (seed index 0) were run outside the evidence tree before the main run, to check that the official
  code starts on macOS with SUMO 1.21. The design was not changed afterwards. Their results are kept in
  `PRERUN_CHECK.jsonl`; the main run reproduced all eight identically.
- A separate scratch check, not kept as evidence, confirmed that the chaser closes on its target (mean distance from
  about 1,340 m to about 500 m in 400 steps, ending on the evader's road).
- The run was executed in three resumable blocks; a block ending on its time limit returned a non-zero shell status
  once, with no effect on the results.
- `summary.json` was written once on partial data (1,494 rows) by mistake, deleted, and regenerated from the complete
  1,600 rows.
- The third-party code has no licence file. It is cited and evaluated; it is not copied into this package.
