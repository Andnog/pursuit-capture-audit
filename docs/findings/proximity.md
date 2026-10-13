# Proximity is not interception

## A team that does not pursue

The simplest check of an endpoint is to score a team that is not trying. Five pursuers drive random routes; nobody
chases the evader.

![Success under proximity endpoints and under operational capture](../assets/figures/F1_endpoint_calibration.png)

On seven cities (548 episodes), that team scores 3.1 % [1.5, 5.1] under operational capture, 33.2 % [28.5, 38.1]
within 5 m between bodies, 23.4 % [19.2, 27.7] within 5 m between centres and 42.3 % [37.4, 47.5] within 10 m. On
the four cities of the second held-out set it scores 1.6 %, 27.3 % and 21.4 %. Proximity endpoints register success
in a large share of episodes without any pursuit; operational capture has a small floor of incidental matches.

## The same episodes under both endpoints

Every episode of the two held-out evaluations was scored under each endpoint. These tables are computed from the
sealed per-episode records by the library of this repository (avoidant and random evaders, all team sizes).

**TEST** (Chicago, Melbourne, Salt Lake City, Minneapolis)

--8<-- "generated/test_endpoints.md"

**HELD-OUT B** (Denver, Vancouver, Barcelona, Buenos Aires)

--8<-- "generated/heldout_b_endpoints.md"

For the pursuit team, with every evader, the 5 m body-gap rule reports 0.851 against 0.172 for operational capture
on TEST, a ratio of 4.9, and 0.776 against 0.227 on HELD-OUT B, a ratio of 3.4. The registered contrast, body gap
minus operational capture, is +0.679 [0.620, 0.735] and +0.549 [0.476, 0.620] (97.5 % intervals).

The disagreement depends on the regime. On small grids like those of the literature, the centre-distance rule is
close to operational capture, or stricter. This does not show that published results obtained with other policies
and environments are inflated. It shows that proximity and operational interception answer different questions in
real downtown traffic.

## What a published capture rule measures

To check that these proximity rules are not a straw man, we ran the official code of two published methods,
without modifying it, and looked at their capture events.

In the released environment of **DGMARL-MVP**, a capture is a distance below 5 m between the front bumpers of a
pursuer and an evader, and the evader is then removed from the simulation. Vehicles are 5 m long and every road has
one lane per direction, so a pursuer that follows the evader in its lane cannot satisfy the rule.

| | Team that turns at random | Team that chases |
|---|---|---|
| Published success criterion met | 42.7 % [37.3, 48.3] | 4.0 % [2.0, 6.3] |
| Capture events | 398 | 139 |
| in the same lane | 0 | 0 |
| vehicles in opposite directions | 82.9 % | 59.7 % |
| inside a junction | 17.1 % | 40.3 % |
| evader faster than 1 m/s | 75.6 % | 90.6 % |
| evader over 50 m from every pursuer 10 s later | 94.8 % [92.2, 97.4] | 92.9 % [88.2, 96.9] |

The last row comes from leaving the evader in the simulation after its first capture: ten seconds later it was
more than 50 m from every pursuer in 93–95 % of cases.

In the released real map of **PEPCRL-MVP**, with its design and a prediction registered beforehand, none of 2 380
capture events joined two vehicles in the same lane. The team that turns at random met the published criterion in
31.3 %, 59.1 % and 58.7 % of episodes in the three scenarios, against 2.8 %, 10.7 % and 9.7 % for the team that
chases.

!!! warning "What this audit does and does not say"
    The released configurations differ from the ones reported in those articles, we used a later version of the
    simulator, and we did not train the published learners. The audit says nothing about the quality of those
    learners. It shows what the endpoint rewards in these environments: crossing the evader's path, not stopping
    it. Both environments come from one research group.

## The endpoint changes the conclusion

On three independent sets of fresh scenarios, predictive lane blocking minus pursuit is +0.123 [0.088, 0.160],
+0.119 [0.076, 0.160] and +0.128 [0.084, 0.170] under operational capture. Under the 5 m body-gap rule it is
−0.013 [−0.025, −0.004], −0.004 [−0.013, 0.004] and −0.004 [−0.011, 0.003], and under the centre-distance rule
−0.021 [−0.040, −0.002], −0.038 [−0.059, −0.020] and −0.021 [−0.038, −0.006]. A 12-point advantage in operational
capture is invisible under one proximity rule and reversed under the other.

## Is the operational endpoint any better?

It was audited the same way. With every pursuer held from the capture on, and a complete 60 s follow-up, no escape
was observed in 1 433 audited captures. That is not a guarantee: when the hold audit was repeated with a probe that
asks for a lane change every second, 15 evaders escaped. If the controllers keep re-planning after a capture, 8–14 %
of evaders are later released. Operational capture measures close stopping behind a pursuer; it does not prove that
escape is impossible, and it requires no rear blocker.

The six replays that this repository uses as its simulator check come from this audit; see
[Reproduce](../reproduce.md).
