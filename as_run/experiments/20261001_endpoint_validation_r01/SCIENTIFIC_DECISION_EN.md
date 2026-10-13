# Scientific decision — endpoint validation r01 (A-88)

406 scenarios completed by all five policies (70 of 2,100 episodes failed scenario generation: the team could not be
placed; they are excluded pairwise). 7 maps: 4 TRAINING (incl. seattle, first use), 3 DEVELOPMENT. 0 collisions.
1,435 audit replays, all certifications reproduced exactly.

## Pre-registered primary tests

| Test | Result | Verdict |
|---|---|---|
| P1 cut − individual / − nearest / − pursuit (all maps) | +0.069 [0.039, 0.101] / +0.059 [0.030, 0.091] / **−0.106 [−0.150, −0.062]** | **NOT PASSED** |
| P2 cut − individual on DEVELOPMENT | +0.088 [0.047, 0.135] | PASSED |
| P3a junction-level certificate fails on DEVELOPMENT (escape lower bound > 0.10) | escape 0.635 [0.593, 0.677] | PASSED (failure replicates) |
| P3b lane-level certificate (escape upper bound ≤ 0.10) | escape 0.010 [0.000, 0.023], n = 311 | ADEQUATE |

P(trapped), all maps: **pursuit 0.212**, random 0.121, cut 0.106, nearest 0.047, individual 0.037 (training /
development: pursuit 0.230 / 0.187; cut 0.094 / 0.123). Random − cut +0.015 [−0.025, 0.054]. Per map, cut −
individual is positive on adelaide, phoenix, portland, sapporo, and not on toronto (−0.017) or seattle (0.000).

**Reading of P1.** All pursuers driving to the end of the evader's current edge — no coordination at all — traps the
evader twice as often as gate-based coordination. The earlier "coordination effect" (A-85) held only against weak
gate-based individual baselines.

## Certificates (descriptive and post hoc)

| | fired | escape (hold) | left the map (hold) | P(trapped \| fired) | P(fired \| trapped) |
|---|---|---|---|---|---|
| junction-level (A-72) | 1,124 | 0.704 | 0.087 | 0.189 | 1.000 |
| lane-level (A-88) | 311 | 0.010 | **0.341** | 0.643 | 0.943 |
| lane-level, ≥ 1 gate (post hoc) | 202 | 0.015 [0.000, 0.035] | 0.000 | **0.990 [0.975, 1.000]** | — |

Post hoc: 109 of the 311 lane-level certificates were **vacuous** (no gate: the evader's reachable region runs off the
map), and 106 of those evaders left the map within seconds. The pre-registered P3b counts gate crossings only, so it
reads ADEQUATE; counting map exits, the unrefined lane-level certificate fails 35 % of the time. Requiring at least one
gate fixes this. The refined lane-level certificate fires before the trap is confirmed in every trapped case (median
8 s earlier). It is therefore a valid, slightly early detector of trapping, not a long-horizon predictor.
Junction-level certificates with ≥ 1 gate still escape 0.771.

## What a "trap" is (post hoc, `POSTHOC_TRAP_GEOMETRY.json`)

Of 212 trapped episodes, at the immobilisation window:

| Type | Share |
|---|---|
| SANDWICH (a pursuer also behind within 30 m) | 35 % (74) |
| DEAD_END (the edge leads only back on itself) | 20 % (43) |
| FRONT_ONLY (blocked ahead, free behind) | 41 % (87) |
| D06 contact without immobilisation | 4 % (8) |

DEAD_END and FRONT_ONLY traps rely on the evader being unable to turn around mid-block. That is a property of the SUMO
vehicle model and of the legal-driving evader, not of physical enclosure. Strict sandwich rates per policy (of 406):
pursuit 8.6 %, random 4.9 %, cut 3.7 %, individual 0.7 %, nearest 0.2 %.

## Sensitivity

cut − individual is unchanged across all 27 threshold combinations (immobilisation 5/10/20 s × gap 10/15/25 m × signal
exclusion none/30/60 m): +0.067 to +0.069, all lower bounds > 0. cut − strongest baseline (pursuit) is negative in
all 27 combinations.

## Consequences

1. The claim "spreading pursuers over exits traps more" is **withdrawn** as a general claim: simple pursuit beats it.
2. The A-87 MARL closure stands, with a recorded limitation. Learning was anchored to the cut by BC and kept
   near-deterministic by a low entropy bonus. It never approached pursuit, although CHASE was in its action set.
3. Constructive methodological result: a lane-level, non-vacuous certificate is a valid trap detector (escape 1.5 %,
   precision 0.99). The junction-level certificate is not, on TRAINING and DEVELOPMENT cities alike.
4. Physical trapping of a faster, legally driving evader by three pursuers in real downtowns is rare (≤ 21 %). Fewer
   than half of the traps are true enclosures.

**Source note.** Both pre-registered phases finished with the hashed sources unchanged. Afterwards, and only for the
post-hoc trap-geometry analysis, `scripts/audit_cage_certificate.py` gained a `follower` field in its per-step record.
The hash in `inputs.json` therefore no longer matches the current file; no pre-registered number depends on that
change.
