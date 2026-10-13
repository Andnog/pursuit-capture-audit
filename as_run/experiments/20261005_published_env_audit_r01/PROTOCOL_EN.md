# Audit of capture events in a published pursuit environment (A-126, stage A)

**Registered in:** `governance/AMENDMENTS_EN.md`, A-126 and its clarification, both written before any run.

**Question.** In the official code of a published multi-vehicle pursuit method, what physically happens at the
instant the environment declares a capture, and what happens to the evader if it is not removed?

**Source.** https://github.com/BUPT-ANTlab/DGMARL-MVP, commit `62bd72e2`. The code is run unmodified from a
byte-identical temporary copy (hashes in `third_party_hashes.json`). It has no licence file, so it is not copied
into this package or into the project's sources.

**Design.**
- Scenarios: 4 pursuers / 2 evaders (300 episode indices) and 7 pursuers / 4 evaders (100 indices), 3×3 grid,
  200 background vehicles, 800 steps, all as released.
- Arms: `null` (uniformly random turns) and `greedy` (shortest-path chaser in the published action space).
- Modes: `published` (unmodified dynamics, observer only) and `followup` (the evader of the first capture event is
  not removed; 30 s of follow-up).
- Seed: 126000 + episode index, identical across arms and modes.

**Outcomes (descriptive, episode-level bootstrap; no hypothesis test).**
1. Published success (all evaders captured within the horizon) and number captured, per arm.
2. Geometry of capture events: same lane, opposite direction, junction, different road; speeds; heading difference.
3. Share of capture events compatible with an operational stop (same lane, pursuer ahead, both at most 1 m/s).
4. After the first capture without removal: evader speed and distance to pursuers at +1, +2, +5, +10 and +30 s.
5. Reference: evaders reaching an operational-stop analogue (at most 1 m/s for 2 s behind a stopped pursuer).

**Prediction recorded before the run.** With 5 m vehicles, front-bumper positions and one lane per direction, a
capture between vehicles following each other in the same lane is geometrically excluded.

**Execution note.** Before the main run, one episode index (index 0, eight episodes) was executed outside the
evidence tree to check that the official code starts on macOS with SUMO 1.21. The design above was already
registered and was not changed afterwards. Those eight episodes are re-run here with the same seeds.
