# Scientific decision — direct trapping endpoint r01 (A-84)

**Verdict: PASSED (pre-registered primary).** Δ P(trapped) cut − individual = **+0.117 [0.061, 0.172]** over 180
fresh scenarios (salt `PE4`), full 300 s SUMO episodes. 0 failed episodes, 0 collisions.

| Policy | P(trapped) [95 % CI] | contact capture | certificate fired | P(trapped \| fired) | evader left map |
|---|---|---|---|---|---|
| cut | 0.156 [0.106, 0.211] | 0.150 | 0.639 | 0.235 | 0.194 |
| random over gates | 0.122 [0.078, 0.172] | 0.122 | 0.378 | 0.324 | 0.189 |
| T seed 1 (r03) | 0.133 [0.083, 0.183] | 0.133 | 0.617 | 0.216 | 0.178 |
| U seed 2 (r03) | 0.144 [0.094, 0.200] | 0.144 | 0.694 | 0.208 | 0.156 |
| T seed 2 (r03) | 0.094 [0.056, 0.139] | 0.094 | 0.633 | 0.149 | 0.211 |
| U seed 1 (r03) | 0.078 [0.039, 0.117] | 0.078 | 0.728 | 0.107 | 0.178 |
| individual | 0.039 [0.011, 0.067] | 0.039 | 0.378 | 0.103 | 0.139 |

Secondary (descriptive): random − cut −0.033 [−0.094, 0.028]; random − individual +0.083 [0.033, 0.139]; learned −
cut from −0.078 [−0.133, −0.022] (U1) to −0.011 [−0.078, 0.056] (U2); two learned policies are significantly below
cut. Trapping almost never happens without the certificate (P(trapped | not fired) ≤ 0.015), but the certificate fires
far more often than trapping occurs. Immobilisation and D06 contact capture nearly coincide.

**Interpretation.** Under a direct, observable endpoint, spreading pursuers over the evader's exits traps the evader
about four times as often as the individual-gate heuristic — but the absolute rate is low (≈ 15 % within 300 s), a
random assignment of pursuers to gates is statistically indistinguishable from the cut, and the r03 learned policies
(trained on the certificate) do not exceed the cut. The individual heuristic is a weak baseline; stronger
non-coordinated comparators (e.g. pure pursuit) are required before any claim that *coordination* causes the gain.
Classification: pilot-scale evidence on TRAINING maps; no confirmatory claim.
