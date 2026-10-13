# Single-shot evaluation on a second held-out set of cities (A-138)

**Registered in:** `governance/AMENDMENTS_EN.md`, A-138 and its note, before any controller ran on these cities.

**Question.** Do the two primaries of the held-out evaluation (A-110) replicate on four cities that the project had
never downloaded, read or simulated?

**Cities** (accepted by the registered rule; `assets/osm_b/MANIFEST.json`): Denver downtown, Vancouver downtown,
Barcelona Eixample, Buenos Aires microcentro. 2.4 km squares from OpenStreetMap, built with the recipe recorded in
the headers of the existing networks. Data © OpenStreetMap contributors, ODbL.

**Design.** Frozen methods: PLB (c2_15), junction ambush (A-95), pursuit. AVOIDANT, RANDOM and OPTIMAL evaders;
teams of 3, 5 and 7; 20 scenarios × 2 SUMO seeds; salt PB1; 4,320 scheduled episodes. A null team of five pursuers
driving random routes, AVOIDANT and RANDOM: 320 scheduled episodes. Every episode is scored under OC, body gap ≤ 5 m
and centre distance ≤ 5 m.

**Primary B1.** PLB − pursuit, OC, pooled over AVOIDANT and RANDOM and the three team sizes; family-clustered
97.5 % lower bound > 0.

**Primary B2.** Body-gap 5 m − OC for the pursuit team, same pooling; family-clustered 97.5 % lower bound > 0.

**Secondary.** City → family intervals; by city and by team; OPTIMAL evader; PLB − junction ambush; centre-distance
rule; the null team under each endpoint; PLB − pursuit under the 5 m rules.

**Single shot.** The evaluation runs once. Its result is reported next to the TEST result and the two are not
pooled. After this run the four cities are spent.

**Checks before the run.** The null-team function was exercised on one TRAINING city with a development salt. No
episode was run on the four cities before this package.
