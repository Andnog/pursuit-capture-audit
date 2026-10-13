# Protocol — final consolidated study r01 (A-90)

Frozen before any episode. Approved by the Research lead ("A and B together; check whether there is real coordination
or only pursuit; equal speeds; the aim is to finish the thesis").

**Setting.** As A-88, except the evader drives at **1.0×** (same speed-cap factor as the pursuers). 7 cities: TRAINING
adelaide, toronto, washington, seattle; DEVELOPMENT phoenix, portland, sapporo. TEST closed. Fresh scenarios, salt
`PE7`, 60 per map, one SUMO seed each. Full 300 s episodes. No learning.

**Runs per scenario.** Team policies: pursuit, cut, individual, random over gates. Coordination counterfactuals:
pursuit with **each single pursuer alone** (same start position; the other two are not inserted).

**Endpoints.** *Trapped* (A-84). Trap type at the immobilisation window: SANDWICH (pursuer also behind within 30 m),
DEAD_END, FRONT_ONLY, CONTACT_ONLY (A-89). *Lenient proximity*: minimum evader–pursuer centre distance over the 0.1 s
trace ≤ 5 m (as in PEPCRL-MVP) and ≤ 10 m. Certificates: junction-level (A-72) and lane-level non-vacuous (A-88 with
≥ 1 gate). Audit: hold-condition re-simulation of every team episode in which a certificate fired (A-83).

**Pre-registered tests.**
- **C1 (real coordination):** paired Δ P(trapped), pursuit team − best single pursuer (per scenario, max over the
  three singles), bootstrap 95 % CI lower bound > 0.
- **C2 (strategy):** pursuit − cut; reported as pursuit > cut, cut > pursuit or no difference (CI vs 0).
- **A1 (calibration):** for the pursuit team, P(within 5 m) − P(trapped), lower bound > 0 ("the lenient endpoint
  inflates success").
- **B1 (lane-level certificate, confirmation of A-89 post-hoc refinement):** hold escape upper bound ≤ 0.10 and
  left-the-map upper bound ≤ 0.10 and P(trapped | fired) lower bound ≥ 0.90 → CONFIRMED; fewer than 30 events →
  INSUFFICIENT.
- **B2:** junction-level certificate hold escape lower bound > 0.10 (failure replicates at equal speed).

Descriptive: all rates by split, team − mean single, trap-type counts per policy, certificate precision and recall,
proximity inflation per policy. Paired analyses use scenarios completed by every run. Budget ≈ 5 CPU-h.
