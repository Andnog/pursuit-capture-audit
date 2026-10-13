# Scientific decision — constructive arrival witnesses (W4 prerequisite)

Experiment: `20260921_w04_constructive_arrival_r01`. Date: 21 September 2026.

**Decision: `UNDER_SETS_CAN_BE_PRODUCED_AND_THE_LABEL_EARNED — IN THE FINITE ABSTRACTION ONLY.`**

---

## 1. What this closes

The arrival-model diagnostic established that **only a constructive schedule yields an `UNDER` set**, and
that `UNDER` is the sole direction Rule A accepts for a `SUPPORTED` verdict. It left an obvious hole:
`ConstructiveArrivalModel` took `(earliest, latest)` **as input**. Nothing generated those tuples and
nothing verified them, so the `UNDER` label was an assertion no one had discharged.

It is now discharged, for the single-vehicle problem. Every reported arrival time comes with a
`SpeedProfile` that is **integrated and checked** before the interval is returned.

**Why this could proceed while W4 cannot.** A constructive schedule answers *can this vehicle be at this
station at this time, and here is the control that does it* — a question needing kinematic limits and a
path, **not** the evader policy (D08) or the capture thresholds (D06). Those decide which opportunity is
worth having and whether contact counts as capture. They do not decide whether a vehicle can be somewhere
at a time.

## 2. What was verified, and how

All six frozen criteria pass; 25 tests within them; 228 tests across the project on both interpreters;
lint clean.

**C1 — the earliest schedule is exact.** Integrating it covers the distance at precisely the reported time,
and it matches closed-form values on two hand-computed cases: `sqrt(2d/a) = 10 s` from rest, and
`5 s + 7.5 s = 12.5 s` when the speed limit is reached mid-way. Requesting *any* earlier time is refused
rather than approximated.

**C2 — the interval is full, not a pair of endpoints.** Over 240 densely sampled times, each returned
profile integrates to arrival at exactly that time. This is the property the `UNDER` label actually rests
on: an interval is only under-approximating if *every* time in it is achievable. Fullness is also verified
from a standstill, where the vehicle must **accelerate** to hit a late target rather than slow down — a
different branch of the construction.

**C3 — every profile is legal.** Speed within `[0, v_limit]` and acceleration within `[−b_max, a_max]` on
every segment, checked at both ends and at interior extrema. The legality check is itself tested against a
deliberately illegal profile, because a check that can never fire is not a check.

**C4 — the label is earned per query.** The witness reports how many times it verified. An unreachable
distance returns **no witness** rather than a guess.

**C5 — nonconvexity is real.** Two blocking windows produce **three disjoint intervals**, no reported time
falls inside a blocked window, and every surviving sub-interval is still fully scheduled. The convex hull
of that set is shown to **swallow the blocked windows** — the precise error the nonconvex representation
exists to prevent.

**C6 — end to end through the real predicate.** Free-flow sets drive the actual compatibility predicate to
`UNKNOWN`; constructive sets reach `SUPPORTED`. **This is the first `SUPPORTED` opportunity verdict in this
project backed by anything other than a hand-written fixture.**

**Measured precision across 400 sampled arrival times:** worst distance error `4.26e-14 m`, worst time
error `0.0 s`, `0` legality violations.

## 3. A subtlety the tests caught, worth stating

Two `UNDER` sets with **disjoint** blocking windows produce an empty intersection — and the verdict is
`UNKNOWN`, **not** `REJECTED`. Rule B requires `OVER` sets to reject, because an under-approximation is a
*subset* of what is achievable, so its emptiness proves nothing about the truth.

The asymmetry between Rules A and B therefore now holds end-to-end through generated sets, not only through
hand-written fixtures. A model good enough to support is, by construction, not good enough to reject — and
the reverse. Any future claim of infeasibility needs its own `OVER` model; it cannot reuse this one.

## 4. What this explicitly does not establish

**Not that constructive witnesses can be produced on a real road network.** The abstraction is motion along
a one-dimensional path with bounded acceleration: no junctions, no lane changes, no traffic, no signals.

**Not that interaction is handled.** `blocking_windows` is supplied from outside; nothing computes it from
other participants' committed plans. That is the harder half — a self-consistent joint candidate needs each
participant's schedule to account for the others in the same candidate, which is a fixed-point problem, not
an independent computation. A joint opportunity built from these sets is sound only where participants do
not interact along their paths, which this package neither checks nor claims.

**Not** physical feasibility, assistance, learning, benefit, transfer or novelty. D06 remains proposed;
D08 remains unresolved.

## 5. Where this leaves the programme

The arrival-model finding said the method could **never** return `SUPPORTED` from a predictive model. That
remains true. What has changed is that the alternative is no longer hypothetical: the constructive route
works, its cost is visible, and the boundary between what it covers and what it does not is now precise.

**W4's two offline constructions are still the gate everything waits on.** This package makes the
single-vehicle component of them real and reduces W4's remaining problem to the part that genuinely needs
the network and the evader: computing blocking windows from other participants' plans, and doing it on
lanes with junctions.

## 6. Next permitted task

**W4**, still blocked on:

1. **D08** — the evader policy.
2. **D06 freeze** — the capture parameters.
3. **First execution of the TraCI surface**, unexercised since W3.
4. **The interaction half of the constructive problem** — blocking windows derived from participants'
   committed plans, on a real lane network.

Item 4 is newly *scoped* rather than newly blocked: before this package the whole constructive problem was
open; now the single-vehicle half is closed in the abstraction and the remainder is named.

Novelty work continues in parallel; citation chasing on B03/B04/B06 remains the cheapest open item.

## 7. What this decision does not authorize

No SUMO episode, optimizer run, checkpoint load or TEST access. No claim that any arrival set produced here
is valid on a real network. No use of these `UNDER` sets to **reject** an opportunity — Rule B forbids it.
No weakening of Rule A to admit `OVER` or `PREDICTION` sets into a `SUPPORTED` verdict.
