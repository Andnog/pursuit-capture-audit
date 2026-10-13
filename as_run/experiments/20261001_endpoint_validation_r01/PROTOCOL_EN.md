# Protocol — endpoint validation r01 (A-88, option B)

Frozen before any episode. Approved by the Research lead (option B), including use of the **DEVELOPMENT** cities
(phoenix_downtown, portland_downtown, sapporo_grid; D15). TEST cities stay closed. No learning.

**Maps.** TRAINING: adelaide_cbd, toronto_downtown, washington_downtown, seattle_downtown (first use of seattle in the
caging setting). DEVELOPMENT: phoenix_downtown, portland_downtown, sapporo_grid. Fresh scenarios (salt `PE6`), 60 per
map, one SUMO seed each (9500 + index). Setting as A-84 (3 pursuers, evader AVOIDANT 1.5×, sigma 0.5, legal control
interface, full 300 s episodes).

**Policies.** cut; individual (each pursuer to the gate with its largest own time margin); **nearest** (each pursuer to
the gate it reaches soonest, independently); **pursuit** (every pursuer drives to the evader's edge); random over gates.

**Endpoints.** Primary *trapped* as A-84 (immobilised ≥ 10 s behind a pursuer leader within 15 m, no red/yellow signal
within 30 m; or D06 contact capture). Two certificates recorded at every step:
- *junction-level* (A-72): every gate has a pursuer within 25 m at ≤ 2 m/s;
- *lane-level* (A-88, new): every lane of every edge by which the evader would enter the gate carries a pursuer at
  ≤ 2 m/s that is ahead of the evader when the evader is on that edge (parked pursuers excluded).
Both: safe region ≤ 2 junctions, held 10 s.

**Audit (phase 2).** Every episode in which a certificate fired is re-simulated with the pursuers frozen from that
certificate's certification (hold condition, A-83); escape = entering an edge leaving a certification-time gate within
60 s. Certification must reproduce exactly (non-reproduced cases reported and excluded).

**Primary tests (pass/fail).**
- **P1** (coordination vs non-coordinated baselines, all 7 maps): Δ P(trapped) cut − individual, cut − nearest and
  cut − pursuit, each bootstrap 95 % CI lower bound > 0 (all three required; intersection-union, no adjustment).
- **P2** (external replication): DEVELOPMENT maps only, cut − individual lower bound > 0.
- **P3a** (certificate failure replicates): junction-level hold-escape on DEVELOPMENT maps, lower bound > 0.10.
- **P3b** (lane-level certificate): pooled hold-escape upper bound ≤ 0.10 → ADEQUATE; > 0.10 → NOT ADEQUATE; fewer
  than 30 certified events → INSUFFICIENT EVENTS.

**Secondary (descriptive).** Random − cut; per-map cut − individual; precision P(trapped | fired) and recall
P(fired | trapped) of each certificate; sensitivity of the trapping endpoint over immobilisation 5/10/20 s × leader gap
10/15/25 m × signal exclusion none/30/60 m (cut − individual, cut − strongest baseline, sign stability).

Budget ≈ 6 CPU-h. Paired analyses use scenarios completed by every policy.
