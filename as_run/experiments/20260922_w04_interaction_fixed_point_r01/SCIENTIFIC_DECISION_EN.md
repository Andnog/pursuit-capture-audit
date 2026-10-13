# Decision — the interaction half as a fixed point

**Claim class: analytical correctness in the declared finite abstraction only.** No simulator, no optimizer,
no checkpoint, no TEST access. Nothing here establishes physical feasibility, assistance, learning, benefit,
transfer or novelty, and nothing discharges O22.

## Verdict

`INTERACTION_OPERATOR_IMPLEMENTED_AND_CONTROLLED`. All seven checks passed. All three outcomes of the
acceptance rule were demonstrated on constructed configurations, not only the favourable one.

## What was open

`constructive_arrival_set` took `blocking_windows` as an **input** and scoped out where they come from. They
come from the other participants, which makes the problem circular: when `i` can arrive depends on when the
others occupy the lane, which depends on when *they* can arrive, which depends on `i`.

That circularity is now stated as an operator and searched constructively.

## The capacity constraint is joint, and pairwise is wrong in both directions

Occupancy is **not** required to be pairwise disjoint. It is required to **fit**: at every instant the
occupants must satisfy `n·length + (n−1)·gap ≤ L`. On the frozen domain a 14.0 m lane admits **two** 5.0 m
bodies at a 2.5 m gap (12.5 m) and not **three** (20.0 m).

Measured, on constructed windows:

| Configuration | Pairwise sees | Joint sweep sees | Capacity |
|---|---|---|---|
| Three overlapping **at one instant** | 2 — passes | **3 — fails** | 2 |
| Three overlapping **pairwise in sequence** | 2 | 2 — passes | 2 |

**A pairwise test is unsound in both directions.** It accepts the simultaneous triple that does not fit, and
a rule forbidding pairwise overlap would reject the sequential three that do. Only a sweep over the interval
structure expresses "at most two". This is the project's joint-versus-pairwise claim instantiated inside the
fixed point rather than asserted about it.

## The coupling was inert, and that was caught

The first witness found looked correct and **was vacuous**. Three participants at 60/80/110 m: only one saw
any blocking window at all, and that window lay entirely *before* its earliest arrival, so it removed
nothing. Every arrival set was a single interval. **The machinery was present and doing no work.**

The cause is structural, not a bug. When the blockers commit at their own earliest times, the window they
create starts at or before the blocked participant's earliest arrival, so removing it **truncates a front**
rather than punching a hole.

A configuration where the coupling bites has to invert that: **blockers far, blocked participant near**, so
their occupancy falls strictly *inside* its reachable range. With blockers at 250 m and one participant at
30 m:

```
near : [4.804, 20.670] ∪ [26.670, 120.000]     blocked by [20.670, 26.670]
```

**A genuinely nonconvex arrival set, produced by the interaction itself.** Its convex hull
`[4.804, 120.000]` readmits `t = 23.67`, at which two vehicles already fill the capacity-two lane. The hull
is not merely imprecise here — **it readmits a physically blocked time**. Both configurations are now fixed
as tests, so a regression to inert coupling fails rather than passes.

## What may not be claimed, and why it cannot be

**No existence theorem is available, and none is claimed.**

Kakutani's fixed-point theorem requires the set-valued map to have **convex** values. These arrival sets are
deliberately **nonconvex**, and the method specification forbids the convex hull — because, as above, the
hull readmits exactly the times blocking removed.

**The property that makes the representation worth having is the property that removes the guarantee.** That
is a real cost of the design. It is recorded rather than worked around, and it is not a defect in the
implementation: no amount of better search recovers a theorem the geometry has excluded.

Consequently the search is a **grid enumeration**, chosen because a cleverer search would make a negative
result harder to interpret:

- `NOT_FOUND_ON_THIS_GRID` — demonstrated on four participants with a 12 s horizon and a 6 s dwell, 81
  combinations examined. **It carries no proof and licenses no claim of non-existence.**
- `PROVABLY_INCONSISTENT` — reserved for proofs independent of the grid. Two demonstrated: a lane too short
  for a single body, and a participant unreachable *before any blocking at all* — sound because blocking only
  ever removes times, so an empty set under no blocking is empty under any.

## Soundness

A returned witness is verified, not asserted. For every participant, its committed time is checked to lie in
its arrival set **recomputed against the others' commitments**; every reported time retains the discharged
`UNDER` label from `constructive_arrival_set`, meaning an integrable legal speed profile; and joint occupancy
is checked against capacity by sweep.

## Limits

- The finite abstraction: one-dimensional approach distances, one shared lane, no junctions, no lane changes,
  no signals, no traffic. **Nothing here has touched SUMO.**
- Homogeneous vehicles at the frozen body and gap.
- Occupancy is arrival plus the contract dwell, with no additional safety pad — deliberately, because a second
  undeclared margin on top of the capacity arithmetic is how a guard stops being checkable.
- Grid enumeration: exponential in participants. Three to five participants, not a scalable solver.
