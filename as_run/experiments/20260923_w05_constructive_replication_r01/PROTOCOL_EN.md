# Protocol — replication of A-40 across maps and routes

**Written before the runner was implemented.** Frozen at the time of writing.

## Why

A-40 refuted the transfer of the constructive `UNDER` label on **one route of one map**: seven arrivals,
seven late, +0.956 to +9.678 s against a 0.1 s tolerance. It recorded that a consistent direction with an
identified mechanism is **not a proof**, and that replication is required before the refutation is stated as
general.

## Two questions, and the second matters more

**Q1 — Does the refutation replicate?** Across four TRAINING maps and several routes each, are arrivals
systematically late?

**Q2 — Is there any route on which it holds?** A-40 listed three possible repairs and called the third,
*narrow the domain to junction-free approaches*, "honest, and probably too restrictive". **That is a guess,
and this package can measure it instead.**

If some routes hold, the domain restriction is a live option and its cost can be quantified: what fraction
of routes qualify. If none hold, the restriction is dead and only a certified junction-delay bound remains.

**Q2 is the reason to run this. Replicating a failure four more times changes little; finding the boundary
changes the repair.**

## Method

1. Four **TRAINING** maps: `adelaide_cbd`, `seattle_downtown`, `toronto_downtown`, `washington_downtown`.
   Read-only. **No TEST map.**
2. Several distinct routes per map, taken in the deterministic order the route search returns them. **Not
   selected after seeing their errors.**
3. Per route: a junction census along its edges, from the network file.
4. Per route: three target times — earliest, 1.5x earliest, 2x earliest.
5. One vehicle per process, so no vehicle-vehicle interaction confounds the kinematics.
6. Tolerance **0.1 s**, unchanged from A-40, and unchanged by anything seen here.
7. Arrival measured on the **odometer**, sentinel checked explicitly, speed control **released** when the
   profile is exhausted. The three instrumentation defects found in A-40 are fixed, not re-introduced.

## Acceptance rule, frozen before running

| Verdict | Condition |
|---|---|
| `REFUTATION_REPLICATED` | Every route is late on every target |
| `REFUTATION_MIXED` | Some routes hold within tolerance and some do not |
| `REFUTATION_NOT_REPLICATED` | Every route holds within tolerance |
| `RUN_FAILED` | Too few arrivals to judge |

`REFUTATION_MIXED` is the **most informative** outcome and must not be presented as a weaker version of
`REFUTATION_REPLICATED`. If it occurs, the package must report **what distinguishes the routes that hold**.

## On the relationship between error and junctions

Junction counts are recorded per route, and any relationship to the error will be **described**.

**Describing a relationship is not certifying a bound.** A-40's repair options require a *certified upper
bound* on junction delay. An observed correlation over a few dozen routes is evidence about the mechanism and
**is not** such a bound, may not be used as one, and must not be fitted into the arrival construction.

## Prohibited

- Widening the 0.1 s tolerance.
- Selecting routes or maps after seeing their errors.
- Fitting any delay margin to the measurements.
- Disabling SUMO's safety checks.
- Any TEST map, optimizer update or checkpoint load.

## Resource limits

Declared with headroom on purpose. The previous two packages each exceeded their own limit because a run that
found a defect in the runner consumed the whole budget before a valid run began.

| | |
|---|---|
| SUMO process starts permitted | **150** |
| Simulated seconds permitted | 30000 |
| Optimizer updates permitted | 0 |
| Checkpoint loads permitted | 0 |
| TEST split accesses permitted | 0 |
