# Scientific decision — capture events in the official PEPCRL-MVP real-map environment (A-137)

**Status:** complete. 1,800 episodes scheduled, 1,781 completed, 19 aborted inside the released environment.
Descriptive study; no hypothesis test was registered. The prediction recorded before the run held.

## What was run

The official PEPCRL-MVP environment (commit `ac8ca695`), unmodified, from byte-identical copies
(`third_party_hashes.json`): the released real map with its three scenarios (6 pursuers / 3 evaders, 7 / 4, 8 / 5),
about 300 background vehicles, 800 steps. 150 seeds per scenario; two teams (random turns; shortest-path chaser);
two modes (unmodified with an observer; first captured evader not removed and followed for 30 s).

## Results

| | P6-E3 null | P6-E3 chaser | P7-E4 null | P7-E4 chaser | P8-E5 null | P8-E5 chaser |
|---|---|---|---|---|---|---|
| Episodes completed / scheduled | 150 / 150 | 142 / 150 | 149 / 150 | 149 / 150 | 150 / 150 | 144 / 150 |
| Published success, completed episodes | 31.3 % [24.0, 38.7] | 2.8 % [0.7, 5.6] | 59.1 % [51.0, 67.1] | 10.7 % [6.0, 16.1] | 58.7 % [50.7, 66.7] | 9.7 % [4.9, 14.6] |
| Published success, bounds over scheduled | 31.3–31.3 % | 2.7–8.0 % | 58.7–59.3 % | 10.7–11.3 % | 58.7–58.7 % | 9.3–13.3 % |
| At least one capture | 94.7 % | 63.4 % | 100.0 % | 95.3 % | 100.0 % | 97.9 % |
| Share of evaders captured | 65.6 % | 30.5 % | 86.9 % | 52.5 % | 89.2 % | 60.1 % |
| Capture events | 295 | 138 | 520 | 314 | 669 | 444 |
| same lane | 0 | 0 | 0 | 0 | 0 | 0 |
| opposite directions | 78.3 % | 82.6 % | 76.3 % | 79.0 % | 79.4 % | 75.7 % |
| inside a junction | 21.7 % | 16.7 % | 23.6 % | 21.0 % | 20.6 % | 24.3 % |
| different roads | 0.0 % | 0.7 % | 0.0 % | 0.0 % | 0.0 % | 0.0 % |
| headings differ by at least 150 deg | 91.5 % | 94.2 % | 92.9 % | 95.2 % | 91.6 % | 91.7 % |
| evader faster than 1 m/s | 61.4 % | 85.5 % | 67.1 % | 79.9 % | 71.0 % | 79.5 % |
| median front-to-front distance | 3.7 m | 3.7 m | 3.6 m | 3.5 m | 3.7 m | 3.7 m |
| First captures followed for 30 s | 142 | 96 | 150 | 143 | 150 | 146 |
| identical to the unmodified run | 142/142 | 90/90 | 149/149 | 142/142 | 150/150 | 141/141 |
| +1 s: within 5 m of its captor | 16.2 % | 8.3 % | 10.7 % | 9.8 % | 9.3 % | 9.6 % |
| +5 s: within 5 m of its captor | 1.4 % | 0.0 % | 0.0 % | 0.0 % | 0.0 % | 0.0 % |
| +10 s: evader faster than 1 m/s | 54.9 % | 52.1 % | 65.3 % | 72.0 % | 72.7 % | 81.5 % |
| +10 s: over 50 m from every pursuer | 79.6 % [72.5, 85.9] | 62.5 % [53.1, 71.9] | 83.3 % [77.3, 89.3] | 69.2 % [61.5, 76.9] | 82.7 % [76.0, 88.7] | 73.3 % [66.4, 80.1] |
| +30 s: median distance to its captor | 222 m | 200 m | 255 m | 252 m | 254 m | 266 m |
| Evaders stopped at least 2 s behind one stopped pursuer | 4.4 % | 6.1 % | 6.2 % | 8.9 % | 5.3 % | 11.2 % |

Intervals are episode-level percentile bootstraps (10,000 resamples). Full figures: `summary.json`.

## Findings

1. **The prediction held on the real map.** None of the 2,380 capture events joined two vehicles in the same lane.
   76–83 % were vehicles passing in opposite directions and 17–24 % crossings inside a junction; one event joined
   vehicles on different roads. The median distance between front bumpers was 3.5–3.7 m, the separation of the two
   lanes of a road.
2. **A team that does not pursue meets the published success criterion in 31 %, 59 % and 59 % of episodes** in the
   three scenarios. A team that chases its evader meets it in 3 %, 11 % and 10 %.
3. **The captured evader is not held.** With the first captured evader left in the simulation, the first capture was
   the same event as in the unmodified run in 814 of 814 checked episodes. All 827 first captures have 30 s of
   follow-up. Two seconds after the capture 12 of 827 evaders were still within 5 m of their captor; five seconds
   after, 2 of 827. Ten seconds after, 628 of 827 (76 %) were more than 50 m from every pursuer; this share is lower
   than on the 3×3 grid (93–95 %) because the map is smaller and the teams larger. Thirty seconds after, the median
   distance to the captor was 200–266 m.
4. **Operational-stop analogue.** 4–11 % of evaders were at some time stopped for at least 2 s behind one and the
   same stopped pursuer. The map has seven signalised junctions, and these stops occur in queues; the pursuers have
   no action to stop or wait.

## Reference to the article, and what it does not show

The article (IEEE T-ITS 25(8), 2024, Table III, real map, 100 tests per model) reports success rates of 0.68, 0.62
and 0.56 for PEPCRL-MVP and 0.47–0.62, 0.30–0.53 and 0.27–0.48 for its eight baselines. The null team here reaches
0.31, 0.59 and 0.59: below every reported method in the first scenario, and at the level of the proposed method and
above every reported baseline in the other two.

This comparison is **indicative only**:
- the learner was not trained here, and the release carries no trained weights;
- the released configuration may differ from the reported one, and SUMO 1.21 was used; the authors' version is not
  stated;
- 150 seeds were used here, 100 tests in the article;
- the article states the rule as a pursuer within 5 m of *its target*; the released code accepts any pursuer.

It is **not** a reproduction of the article and **not** evidence about the published learner. It is evidence about
the endpoint in the released environment: the rule is met by crossing an evader's path, and a team that only
wanders meets it often.

Both audited environments (this one and DGMARL-MVP, A-126) come from one research group and share code. This audit
adds a real map and the journal article of that line of work. It does not add an independent group.

## Aborted episodes

19 of 1,800 episodes (1.1 %) stopped with an error raised inside the released environment, between steps 429 and
791: 13 with `Lane '' is not known` (the release reads the lane of every pursuer at each step and has no branch for
a pursuer that SUMO is teleporting) and 6 with `Vehicle 'e…' is not known` (an evader that SUMO has removed is still
in the environment's list). 16 are in published mode and 3 in follow-up mode; 17 of the 19 are with the chaser team.
No team and scenario exceeds the registered limit of 20 % (the maximum is 8 of 150). They are recorded as failed,
with their partial record, and were not replaced. The 22 capture events they had produced before aborting are
included in the geometry. Success is given over completed episodes and with bounds over scheduled episodes.

## Execution record

- Design and prediction registered in A-137 and its clarification before the gated run.
- Twelve episodes (seed index 0) were run outside the evidence tree as an execution check; one aborted, which led
  to the clarification. They were run again here.
- The run was executed in resumable blocks: 21:08–23:00 on 5 October, then 02:00–03:16 on 6 October. Between the
  blocks nothing ran because the session that owns the run was not woken by its notifications.
- Sources were not modified while workers ran (`inputs.json`); the other session working on the repository did not
  touch the four scripts of this audit.
- The third-party code has no licence file. It is cited and evaluated; it is not copied into this package.
