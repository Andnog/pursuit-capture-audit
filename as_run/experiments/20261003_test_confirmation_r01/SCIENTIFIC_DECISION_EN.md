# Scientific decision — single-shot TEST confirmation r01 (A-110)

16,128 rows: 15,040 episodes (526 scenario-placement failures, identical across methods within each block) and 1,088
certificate audits (all reproduced). 0 collisions. Run once; methods frozen; analysis written before launch.

## Confirmatory (Bonferroni over two; 97.5 % paired bootstrap)

| | Estimate | 97.5 % CI | Verdict |
|---|---|---|---|
| **H1** PLB (c2_15) − pursuit, TEST, AVOIDANT/RANDOM × teams 3/5/7 (468 scenario-cells) | **+0.145** | [0.101, 0.189] | **PASSED** |
| **H2** pursuit: body-gap ≤ 5 m − D06, TEST, all evaders and teams (699) | **+0.679** | [0.642, 0.717] | **PASSED** |

H1 per city: Chicago +0.113, Melbourne +0.064, Minneapolis +0.211, Salt Lake City +0.197; city-cluster 95 % interval
[0.076, 0.216]. H2 rates: within 5 m (body) 0.851, within 5 m (centre) 0.748, D06 0.172 (×4.9).

## Secondary

- **S1** PLB − A-95 ambush, pooled: +0.101 [0.065, 0.138].
- **S2** Strongest evader (OPTIMAL_ESCAPE), PLB − pursuit: TEST +0.171 [0.121, 0.225]; seven non-TEST cities (OX)
  +0.214 [0.165, 0.261]; positive in every team size in both.
- **S3** Cooperation: no cell with Bonferroni-positive synergy (TEST 9 cells, OX 3 cells). Synergy ranges from −0.13 to
  +0.04. Single PLB pursuers capture 0.16–0.20.
- **S4** MAPPO − PLB: KAN −0.001 [−0.033, 0.032], MLP −0.009 [−0.040, 0.024]; KAN − MLP +0.007 [−0.011, 0.027].
- **S5** Lane-level certificate on TEST **CONFIRMED**: escape 0.054 [0.029, 0.083], left network 0.025, precision
  (trapped) 0.963 [0.938, 0.983], n = 240. Junction-level failure **replicates**: escape 0.586 [0.553, 0.619],
  precision 0.30, n = 848.
- **S6** see H1 per city and city-cluster interval.

## Capture by cell (TEST, D06)

| Evader | Team | PLB | A-95 | Pursuit | MAPPO-KAN | MAPPO-MLP |
|---|---|---|---|---|---|---|
| Random | 3 | 0.299 | 0.175 | 0.162 | 0.299 | 0.305 |
| Random | 5 | 0.351 | 0.260 | 0.221 | 0.396 | 0.377 |
| Random | 7 | 0.370 | 0.292 | 0.292 | 0.448 | 0.468 |
| Avoidant | 3 | 0.297 | 0.203 | 0.127 | 0.259 | 0.241 |
| Avoidant | 5 | 0.373 | 0.253 | 0.171 | 0.323 | 0.316 |
| Avoidant | 7 | 0.367 | 0.266 | 0.215 | 0.329 | 0.304 |
| Optimal | 3 | 0.253 | 0.156 | 0.130 | 0.247 | 0.234 |
| Optimal | 5 | 0.260 | 0.188 | 0.091 | 0.273 | 0.286 |
| Optimal | 7 | 0.364 | 0.260 | 0.143 | 0.338 | 0.299 |

## Reading

The method claim, the measurement claim and the certificate claim all hold on four cities that were never simulated
before, with frozen methods. On TEST, PLB beats pursuit by more than on the seven development-phase cities (+0.145 vs
+0.04 to +0.15), and it also beats pursuit against the strongest evader. The gain stays individual rather than
cooperative. Learned MAPPO controllers match PLB, which they imitate, and do not exceed it; KAN = MLP.
