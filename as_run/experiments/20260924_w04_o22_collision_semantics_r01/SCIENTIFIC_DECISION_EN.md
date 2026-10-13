# Decision — the frozen capture predicate cannot be satisfied in SUMO as configured

**Claim class: safety semantics of the simulator.** O22's safety-admission part, authorised 2026-09-24. No
capture attempted, no TEST map, no optimizer. **This package measures and does not choose a remedy: D06 is
the Research lead's.**

## Verdict

`CAPTURE_BAND_IS_A_COLLISION_BY_DEFAULT_AND_IS_UNREACHABLE_UNDER_SAFE_FOLLOWING`.

## Finding 1 — SUMO calls the whole capture band a collision

Two stationary vehicles at forced bumper gaps, every position read back and verified exact:

| Gap (m) | In capture band | SUMO defaults | `--collision.mingap-factor 0` |
|---|---|---|---|
| 3.00, 2.60 | — | no collision | no collision |
| 2.40 | — | **collision** | no collision |
| 2.00, 1.00, 0.30 | **yes** | **collision** | no collision |

SUMO's own warning reports the gap **net of minGap**: 2.4 → −0.10, 2.0 → −0.50, 1.0 → −1.50,
0.30 → −2.20. Under default semantics a collision is any bumper gap below **minGap = 2.5 m**.

D06 asserts capture *cannot coincide with a collision* because 0.30 m > 0. That assumes collision means
overlap. In SUMO as configured it does not.

## Finding 2 — safe following cannot even reach the band

Collision *detection* and car-following are separate. With detection set to physical overlap
(`mingap-factor 0`) and SUMO's safety checks **on** (speed mode 31), a pursuer commanded to close on a
stationary evader stops at **2.501 m** — exactly minGap — and never enters [0.30, 2.00].

**So changing collision detection alone does not rescue D06.** The pursuer's own safe-speed logic keeps it
out of the band.

## O22 Roma, reinterpreted

The historical record: native collision at 21.8 s with a *positive* reported gap, arithmetic
`6.459929 − length 5 − MinGap 2.5`. That expression evaluates to **−1.04 m**, and it is **SUMO's collision
gap, net of minGap**. The legacy log's own arithmetic is SUMO's collision formula, and it reads negative.

The contract attributes O22 Roma to *"a modelling error in station-separation arithmetic"*. That is at best
incomplete: even a correctly computed physical gap of 1.46 m is a SUMO collision. Strong explanation from the
logged arithmetic; not re-run on the original scenario.

## The admission module reproduces the failure class

`safety/admission.py` checks physical separation and **never consults minGap**. It would admit a step leaving
a 1.46 m bumper gap that SUMO then reports as a collision — the Roma failure, in the new module. Not fixed
here: the correct fix depends on which remedy the Research lead chooses.

## Remedies, each the Research lead's

| Option | Changes | Consequence |
|---|---|---|
| Set vehicle **minGap below 0.30 m** | domain contract `min_gap_m` | Collision threshold and safe-following stop point both move below the band; D06 unchanged. Every vehicle follows closer than realistic traffic. |
| Collision = overlap (`mingap-factor 0`) **and** reduce minGap | both of the above | Most direct; still requires the minGap change |
| Disable safety checks for the pursuer | speed mode | **Prohibited**: weakens safety to obtain capture |
| Move the capture band above 2.5 m | frozen D06 | No longer "contact"; contradicts the lead's own definition |

## A lead, not a finding

Legacy O26 recorded 0/4 and 0/4 captures. If its capture distance also sat below minGap, safe following alone
would have prevented every one. The legacy contract differs; not checked.
