# Scientific decision — final consolidated study r01 (A-90)

Equal speeds (evader 1.0×). 413 scenarios completed by all seven runs (49 of 2,940 episodes failed scenario
generation and are excluded pairwise). 7 cities (4 TRAINING, 3 DEVELOPMENT). 0 collisions. 1,323 audit replays, all
certifications reproduced.

## Pre-registered tests

| Test | Result | Verdict |
|---|---|---|
| C1 pursuit team − best single pursuer | −0.019 [−0.058, 0.019] | **NOT PASSED: no team effect beyond the best single pursuer** |
| C2 pursuit − cut | +0.005 [−0.041, 0.053] | no difference |
| A1 P(within 5 m) − P(trapped), pursuit team | +0.637 [0.586, 0.688] | PASSED: the lenient endpoint inflates success ~5× |
| B1 lane-level non-vacuous certificate | escape 0.058 [0.031, 0.089]; left the map 0.004; P(trapped \| fired) 0.964 [0.938, 0.987] | **CONFIRMED** |
| B2 junction-level certificate failure | escape 0.709 [0.683, 0.737] | replicates |

## Rates

| Run | P(trapped) | D06 contact | within 5 m | within 10 m | evader left the map |
|---|---|---|---|---|---|
| Pursuit (team of 3) | 0.165 [0.128, 0.201] | 0.155 | 0.801 | 0.891 | 0.131 |
| Cut | 0.160 | 0.160 | 0.552 | 0.770 | 0.123 |
| Random over gates | 0.155 | 0.153 | 0.579 | 0.705 | 0.165 |
| Individual | 0.051 | 0.051 | 0.269 | 0.477 | 0.177 |
| Pursuit, P1 alone | 0.070 | 0.068 | 0.651 | 0.753 | 0.138 |
| Pursuit, P2 alone | 0.070 | 0.070 | 0.683 | 0.765 | 0.138 |
| Pursuit, P3 alone | 0.082 | 0.080 | 0.622 | 0.724 | 0.140 |

- Best single pursuer per scenario (oracle choice): 0.184.
- Team − mean single: +0.090 [0.059, 0.122].
- Training and development cities behave alike (pursuit 0.169 / 0.158).

## Trap types

| Run | SANDWICH | DEAD_END | FRONT_ONLY | CONTACT_ONLY |
|---|---|---|---|---|
| Pursuit team | 39 | 9 | 18 | 2 |
| Cut | 29 | 6 | 27 | 4 |
| Random | 29 | 8 | 25 | 2 |
| Individual | 2 | 1 | 15 | 3 |
| Singles (p1 / p2 / p3) | 0 / 0 / 0 | 16 / 14 / 13 | 13 / 14 / 21 | 0 / 1 / 0 |

## Certificates (team runs)

| | fired | escape (hold) | P(trapped \| fired) | P(fired \| trapped) |
|---|---|---|---|---|
| junction-level | 1,098 | 0.709 | 0.199 | 1.000 |
| lane-level, non-vacuous | 225 | 0.058 | 0.964 | 0.991 |

## Reading

1. **No genuine cooperation.** A team of three pursuers traps the evader about as often as the best of its members
   acting alone; it beats the average member (+0.09). Teams change *how* the evader is trapped: sandwiches replace the
   dead-end and blocked-ahead traps of single pursuers. They do not change *how often*. The extra pursuers act as
   additional independent chances, not as complementary roles.
2. At equal speeds, pursuit, the cut and random gate assignment are indistinguishable (≈ 0.16); the individual
   gate heuristic is clearly worse (0.05).
3. Lenient endpoints inflate success about five-fold. Within 5 m: 0.80 for the pursuit team and 0.62–0.68 for a
   single pursuer, against 0.165 trapped. A pursuer passing the evader in the adjacent or opposite lane at ~3 m
   counts as a capture under that rule (`gifs/phoenix12_pursuit_5m_rule.gif`).
4. The non-vacuous lane-level certificate is confirmed as a valid trap detector on fresh scenarios at a different
   speed. The junction-level certificate fails again.
