# Scientific decision — cage certificate audit r02 (A-83)

**Verdict: CERTIFICATE NOT ADEQUATE (pre-declared reading).** Population: 427 certified cages from the sealed pilot
r03 evaluation (4 learned checkpoints + cut), all reproduced exactly in SUMO (certification time identical).

Hold condition (pursuers keep their last command after certification), 60 s window:

| Measure | Value [95 % CI] |
|---|---|
| M1 escape (enters an edge leaving a certification-time gate) | 0.775 [0.735, 0.815] — bound ≤ 0.10 required |
| M1b leaves the network without crossing a gate | 0.066 [0.044, 0.089] |
| M2 physically blocked by a pursuer (≤ 0.5 m/s ≥ 2 s, pursuer leader ≤ 15 m) | 0.171 [0.136, 0.208] |
| M3 at a red/yellow signal at certification | 0.276 [0.234, 0.319] |
| M4 D06 contact capture | 0.141 [0.108, 0.173] |

State at certification: moving 269, red light 118, blocked 36, stopped 4 (median evader speed 7.4 m/s). Escapes occur
a median 12 s after certification. Every checkpoint behaves alike (escape 0.72–0.83); the policy condition gives the
same numbers (0.778). 28 cages had no gate at all (certificate vacuously true). Only 68/427 (16 %) neither escaped nor
left the network; 44 of these were physically blocked and 43 met the D06 capture predicate.

Post-hoc diagnosis (`POSTHOC_ESCAPE_DIAGNOSIS_cut.json`, the 65 escapes of the cut heuristic): in 58 (89 %) the
pursuer credited with holding the crossed gate was stopped on **another approach** to that junction (median 10.6 m
from its centre); the evader drove through the junction past it. A pursuer "within 25 m at ≤ 2 m/s" of a junction does
not close it. 30 of the 65 approaches have ≥ 2 lanes.

**Consequence.** The A-72 physical-cage certificate measures that pursuers are stationed near every frontier junction,
not that the evader is trapped. Results that used it as the endpoint — F3 (A-74), F4 (A-77), MARL pilots r02/r03
(A-79, A-82) — remain valid as statements about *certificate firing* and must not be reported as trapping or capture.
A validated endpoint is required before any further comparison.
