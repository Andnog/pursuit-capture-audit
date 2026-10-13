# Capture events in the official PEPCRL-MVP real-map environment (A-137)

**Registered in:** `governance/AMENDMENTS_EN.md`, A-137 and its clarification, before any gated run.

**Question.** Does the finding of the first published-environment audit (a 3×3 grid) hold in the released real-map
environment of the journal article of the same line of work?

**Source.** https://github.com/BUPT-ANTlab/PEPCRL-MVP, commit `ac8ca695`. Run unmodified from byte-identical
temporary copies (hashes in `third_party_hashes.json`). No licence file: the code is cited and evaluated, not
redistributed.

**Design.**
- Released scenarios on the real map: 6 pursuers / 3 evaders, 7 / 4, 8 / 5; about 300 background vehicles; 800 steps.
- 150 seeds per scenario (137000 + index), the same across teams and modes.
- Teams: `null` (random turns) and `chaser` (shortest-path turn towards the nearest remaining evader).
- Modes: `published` (unmodified, observer only) and `follow-up` (first captured evader not removed and followed for
  30 s; only the horizon parameter is raised so that the follow-up is complete).
- 1,800 scheduled episodes.

**Outcomes (descriptive).** Published success per team, with bounds over scheduled episodes; geometry and speeds of
every capture event; evader state at +1, +2, +5, +10 and +30 s with denominators; share of evaders stopped for at
least 2 s of simulation time behind one and the same stopped pursuer.

**Prediction recorded before the run.** No capture event joins two vehicles in the same lane (5 m vehicles,
front-bumper positions, one lane per direction).

**Aborted episodes.** The release has no branch for a pursuer being teleported by SUMO and stops with an error.
Such episodes are recorded as failed with their partial record, reported per team and scenario, and not replaced.

**Execution note.** Twelve episodes (seed index 0) were run outside the evidence tree as an execution check; they
are run again here.
