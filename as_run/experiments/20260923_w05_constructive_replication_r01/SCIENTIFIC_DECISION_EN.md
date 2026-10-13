# Decision — replication of the transfer refutation

**Claim class: replication of a transfer refutation.** No capture, no assistance, no learning, no optimizer,
no checkpoint, no TEST map. Nothing here discharges O22.

## Verdict

`REFUTATION_REPLICATED`, and on stronger evidence than A-40 had.

**48 closed-loop runs across 4 TRAINING maps and 12 routes. 48 lost feasibility mid-flight. Zero kept it.**

## The two questions

**Q1 — does it replicate?** Yes. 48/48 arrivals late, none early, errors +0.13 s to +171.4 s against a
0.1 s tolerance, median +25.5 s.

**Q2 — is there any route on which it holds?** **No.** Not one of 12 routes on 4 maps. A-40 listed *narrow
the domain to junction-free approaches* as a possible repair and guessed it was "probably too restrictive".
It is not restrictive — **it is empty**. That repair is dead.

## The result that matters more than the arrival errors

A-40 measured arrival error under **open-loop** execution: command the time-indexed profile and see when you
land. That conflates the schedule being unachievable with open-loop execution amplifying any early deviation.

This package adds a **closed-loop** arm that asks the honest question every step: *from where the vehicle
actually is, does a legal schedule landing at `t*` still exist?*

**It does not, in 48 runs out of 48.** And feasibility is lost early — with a **median 61% of the route still
ahead**, ranging from 94% to 9% remaining.

So the refutation is not an artifact of how the plan was executed. **The target becomes unreachable during
flight, every time.**

## Detector soundness, checked rather than assumed

The logged loss details show remaining time and fastest-possible time equal to one decimal, which would be
consistent with a floating-point boundary artifact. Probed directly: `arrival_at` returns a profile at
**exactly** the earliest possible time and `None` only strictly below it. The detector fires only on genuine
infeasibility. The equality was rounding in the log.

## A-40's mechanism attribution is withdrawn

A-40 diagnosed the lateness as **junction right-of-way logic**, from a junction census on **one** route.

Across 48 measurements the correlation between arrival error and junction count before the station is
**0.02**. **Junction count explains nothing.** That attribution was too confident for the evidence it had,
and it is withdrawn.

What survives: correlation with **clamped steps is 0.54**. SUMO overrides the commanded speed and the deficit
accumulates. **Why** it overrides is not established here, and the package does not guess again.

## A structural observation, not an empirical one

The lower endpoint of every `UNDER` arrival set is the **earliest** arrival, which by construction has **zero
slack**. Any deficit at all makes it unreachable.

**So the earliest time in any `UNDER` set is unreachable in practice, as a property of the representation
rather than of this simulator.** Relaxed targets fare better only until their slack is consumed — at 1.5x and
2.0x, feasibility was still lost in every run, later in the flight.

## Consequence

A-40's conclusion stands and widens: **on a real lane network, under the construction as it stands, no
opportunity can be `SUPPORTED`.** Rule A requires every arrival set to `UNDER`-approximate, and no arrival
set produced here survives contact with the simulator.

Of A-40's three repair options, one is now closed by measurement:

1. **Model junction delay with a certified bound** — still open, and now less attractive: junction count is
   not the explanatory variable, so a junction-indexed bound would be indexing on the wrong thing.
2. **Construct with a certified margin** — still open, still needs a certification no measurement provides.
3. **Restrict to junction-free approaches** — **closed. Zero qualifying routes in the corpus.**

## What was deliberately not done

**No delay margin was fitted to these 48 measurements.** The protocol forbade it before the numbers existed.
A margin fitted here would re-assert the `UNDER` label that the constructive work exists to *earn*, and would
be calibrated on the very data that refuted it.

## Limits

- Four TRAINING maps, 12 routes, 48 closed-loop measurements. Broad enough to refute "it was one route",
  not broad enough to characterise the deficit.
- Single vehicle per run, so no vehicle-vehicle interaction. Arm 2 of A-40 showed three vehicles roughly
  double the error; that is not re-measured here.
- The mechanism behind SUMO's speed overrides is **not** established.
