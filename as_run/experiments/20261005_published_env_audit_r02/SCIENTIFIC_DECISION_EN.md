# Scientific decision — published-environment audit, addendum r02 (A-133, R4-B)

**Status:** complete. 812 of 812 replays, no failure. Versioned completion of the sealed audit r01, which is not
modified. Descriptive.

## 1. Follow-up completion

- 12 of 577 first captures in r01 had less than 30 s of follow-up because the episode horizon ended (10 in the
  4 vs 2 scenario and 2 in the 7 vs 4 scenario; keys in `summary.json`).
- All 12 were re-run with the horizon extended to the capture plus 30 s. **12 of 12 reproduced the sealed first event**
  (same step, evader and pursuer), and all now have the five marks.
- With complete follow-up for all 577 first captures:

| | P4–E2 null | P4–E2 chaser | P7–E4 null | P7–E4 chaser |
|---|---|---|---|---|
| First captures followed for 30 s | 270 | 127 | 100 | 80 |
| +1 s: within 5 m of its captor | 33 (12.2 %) | 30 (23.6 %) | 9 (9.0 %) | 14 (17.5 %) |
| +5 s: within 5 m of its captor | 0 | 0 | 0 | 0 |
| +10 s: over 50 m from every pursuer | 256 (94.8 % [92.2, 97.4]) | 118 (92.9 % [88.2, 96.9]) | 95 (95.0 % [90.0, 99.0]) | 74 (92.5 % [86.2, 97.5]) |
| +30 s: median distance to its captor | 439 m | 423 m | 449 m | 424 m |

The statement "five seconds later no evader was within 5 m of its captor" now rests on all 577 cases (in r01 it
rested on 576). The +10 s shares change by at most 0.1 point.

## 2. Stop analogue with a time-based duration

- The 800 published-mode episodes were re-run. **800 of 800 reproduced the sealed capture events, and the sealed
  function returned the sealed result in 800 of 800.**
- The r01 quantity was two consecutive observations one second apart, which is at least one second, not two, and did
  not require the same leader. It is reported under that name.
- New quantity: the evader is at most 1 m/s behind one and the same pursuer, itself at most 1 m/s, without
  interruption for at least 2 s of simulation time (three consecutive 1 s observations).

| | P4–E2 null | P4–E2 chaser | P7–E4 null | P7–E4 chaser |
|---|---|---|---|---|
| Evaders | 600 | 600 | 400 | 400 |
| Two consecutive observations (r01 quantity) | 23 (3.8 %) | 16 (2.7 %) | 16 (4.0 %) | 14 (3.5 %) |
| Stopped at least 2 s behind the same stopped pursuer | 23 (3.8 %) | 15 (2.5 %) | 16 (4.0 %) | 13 (3.2 %) |

Two evaders counted by the earlier rule do not reach two seconds behind one pursuer.

## What changes in the manuscript

- The supplement gives the number of first captures followed and states that the 12 censored cases were completed in
  a versioned addendum.
- The last row of the table is replaced by the time-based quantity.
- No conclusion changes: 999 events, none in the same lane; success rates of the two teams; the evader is not held.

## Record

- Before the run, 14 replays were executed outside the evidence tree to check the script; all reproduced the sealed
  events and were run again here.
- The official code ran unmodified, from byte-identical copies, as in r01. For the 12 follow-ups only the
  environment's `max_steps` parameter was raised.
- `ANALYSIS.json` (marks with denominators and episode-level bootstrap intervals) was produced after the run by
  `scripts/analyse_published_env_r02.py`, which reads the results and changes nothing else.
