# Protocol — does a constructively computed arrival time hold on a real network?

**Written before the runner was implemented.** Frozen at the time of writing.

## The question

Every constructive result so far lives in a finite abstraction: one-dimensional approach distances, one
shared lane, no junctions, no lane changes, no signals, no traffic. `constructive_arrival_set` earns the
`UNDER` label by integrating a speed profile exactly.

**`UNDER` means the time is achievable.** In the abstraction that is a theorem about the integral. On a lane
network it is a claim about reality, and it has never been tested.

> Given a station on a real SUMO network and a constructively computed arrival time `t*`, does the vehicle
> actually arrive at `t*`?

## Why the answer could be no, stated in advance

- **SUMO's safety layer is left ON.** `setSpeed` is a request; car-following and junction logic may execute
  something slower. Already measured in `20260922_w04_traci_first_execution_r01`.
- **Junctions and traffic lights** are absent from the abstraction. A red light makes any schedule late.
- **Speed limits vary per edge.** The abstraction carries a single `speed_limit_mps`.
- **Lane changes and internal junction edges** change the distance actually travelled.

**A late arrival refutes `UNDER` on the network**, because the time was not achievable. An early arrival is a
different failure: the arrival set asserts arrival *at* `t`, not *by* `t`.

## The tolerance, fixed now and justified now

Arrival is observed once per physical step of **0.1 s**. Below the simulator's own resolution, equality is
not observable, so the comparison tolerance is **one physical step, 0.1 s**.

This is declared **before any run**. It is not a tolerance on the physics — the abstraction is exact — it is
the resolution at which the simulator can be interrogated at all. **It may not be widened afterwards.** The
residual distance at the crossing step is recorded as well, so sub-step error is visible rather than hidden
inside the tolerance.

## Method

1. `scripts/preflight.py` must pass.
2. One **TRAINING** map, read-only. **No TEST map.**
3. Choose a route and a station at a fixed driving distance along it.
4. The abstraction's `speed_limit_mps` is the **minimum allowed speed over the route's edges**, so the
   profile is legal everywhere on the route rather than only on average. Recorded as a modelling choice.
5. **Arm 1 — kinematics alone.** One vehicle, several target arrival times spanning the reachable set.
   Command the constructive profile each step; record the step at which driving distance to the station
   first reaches zero.
6. **Arm 2 — the mutual-consistency witness.** Execute the three-participant commitment set produced by
   `solve_mutual_consistency`, and check both the individual arrival times and whether lane occupancy in the
   simulator respected capacity.
7. Close every process.

## Acceptance rule, frozen before running

| Verdict | Condition |
|---|---|
| `CONSTRUCTIVE_TIMES_HOLD` | Every arrival is within 0.1 s of its target, in both arms |
| `CONSTRUCTIVE_TIMES_HOLD_ARM_1_ONLY` | Arm 1 holds, arm 2 does not |
| `CONSTRUCTIVE_TIMES_FAIL` | Arm 1 does not hold |
| `RUN_FAILED` | SUMO could not be started, or no vehicle reached the station |

**`CONSTRUCTIVE_TIMES_FAIL` is the expected-plausible outcome and is publishable as-is.** If it occurs, the
error must be reported **with its sign and magnitude**, and the consequence stated: an `UNDER` label earned
in the abstraction does not transfer to the network, and the method specification's reliance on constructive
witnesses needs a network-level qualification.

## Prohibited

- Widening the 0.1 s tolerance after seeing a result.
- Disabling or weakening SUMO's safety checks to make a schedule fit.
- Choosing a route or station after seeing which one produces small errors.
- Any TEST map, optimizer update or checkpoint load.
- Claiming anything about capture, assistance, learning or benefit.

## Route and station selection, fixed before running

The route is the **first** one `pick_route` returns for this network, unchanged from the two previous
packages. The station is at **60% of the route's drivable length**, chosen to leave room to accelerate before
it and to avoid the final edge. Neither is tuned.

## Resource limits

| | |
|---|---|
| SUMO process starts permitted | 6 |
| Simulated seconds permitted | 600 |
| Optimizer updates permitted | 0 |
| Checkpoint loads permitted | 0 |
| TEST split accesses permitted | 0 |
