# Protocol — the interaction half: blocking windows as a fixed point

**Written before the module was implemented.** Frozen at the time of writing.

## The hole this closes, stated exactly

`constructive_arrival_set` takes `blocking_windows` as an **input**. Its own docstring scopes out where they
come from: *"no interaction with other participants' committed plans. That last omission is the harder half
of the problem."*

It is harder because it is **circular**. Participant `i`'s reachable times depend on when the others occupy
the shared resource; when they can occupy it depends on their reachable times, which depend on `i`. A
commitment set is consistent only if every participant's chosen time is reachable *given everyone else's
choices*.

## The operator

For participants `1..n` on a shared lane of length `L`:

- A **commitment** is a chosen arrival time `t_i`.
- A commitment induces an **occupancy window** `O_i(t_i)` during which `i` occupies the lane.
- The **blocking windows** participant `i` must respect are induced by `{O_j(t_j) : j ≠ i}`.
- `A_i(t_-i) = constructive_arrival_set(..., blocking_windows from t_-i)`.

A **mutually consistent commitment set** is an assignment with `t_i ∈ A_i(t_-i)` for every `i`, whose joint
occupancy also satisfies the lane-capacity constraint.

## The capacity constraint is joint, not pairwise — deliberately

Occupancy is **not** required to be pairwise disjoint. It is bounded by capacity: at every instant the
occupants must physically fit, using the arithmetic already in `lane_capacity_required_m` —
`n` bodies need `n·length + (n−1)·gap`.

For the frozen domain (5.0 m bodies, 2.5 m gap) a 14.0 m lane admits **two** occupants (12.5 m) but not
**three** (20.0 m).

This is exactly where a pairwise test is unsound as a team certificate: **every pair is fine and the triple
is not.** Pairwise disjointness would be too strong — it forbids the legal pair — and pairwise checking
cannot express "at most two". The constraint is therefore evaluated by a sweep over the interval structure,
never by decomposition into pairs.

## What may not be claimed, and why

**No existence theorem is available here, and none will be claimed.**

The standard fixed-point guarantees for set-valued maps (Kakutani) require the values to be **convex**. The
arrival sets in this project are **deliberately nonconvex** — unions of disjoint closed intervals, with the
convex hull forbidden by the method specification, because the hull would readmit times the blocking windows
removed.

**The property that makes the representation worth having is the property that removes the guarantee.** That
is a real cost of the design and is recorded as such, not worked around.

Consequently:

- A search that finds nothing establishes **`NOT_FOUND_ON_THIS_GRID`**, never "no fixed point exists".
- Non-existence may be asserted **only** when a separate proof applies — for example when a participant's
  arrival set is empty before any blocking, or when capacity is exceeded even under the most favourable
  assignment.

## Soundness requirement

Any returned witness must be **verified, not asserted**:

1. Every `t_i` lies in `A_i` recomputed against the *other* committed times.
2. Every `t_i` has a speed profile that integrates to the required distance at exactly `t_i`, with speed and
   acceleration legal throughout — the same discharge `constructive_arrival_set` already requires.
3. The joint occupancy satisfies capacity at every instant, by sweep.

A witness failing any of these is not reported.

## Acceptance rule, frozen before running

| Verdict | Condition |
|---|---|
| `WITNESS_VERIFIED` | A mutually consistent set is found **and** passes all three soundness checks |
| `NOT_FOUND_ON_THIS_GRID` | The search returns nothing; existence **unknown** |
| `PROVABLY_INCONSISTENT` | A proof of non-existence applies, independent of the grid |
| `UNSOUND` | A witness is produced that fails a soundness check — a defect in this module |

The package must demonstrate **all three** of the first outcomes on constructed configurations. A module that
can only report success has not been shown to detect failure.

## Required negative controls

1. A configuration where **pairwise passes and the joint constraint fails** — the three-on-a-14 m-lane case.
   If the joint check does not reject it, the joint machinery is decorative.
2. A configuration that is **provably inconsistent**, to show failure is reachable.
3. A configuration where a fixed point exists but the **convex hull** of some arrival set would admit a time
   that is actually blocked — showing the hull is unsound here, not merely imprecise.

## Prohibited

- Claiming existence from a failed search.
- Convexifying an arrival set at any point.
- Relaxing the capacity arithmetic or the integration tolerance to obtain a witness.
- Any simulator, optimizer, checkpoint or TEST access. This is analytical work in the finite abstraction.

## Resource limits

Analytical only. No SUMO process, no optimizer update, no checkpoint load, no TEST access.
