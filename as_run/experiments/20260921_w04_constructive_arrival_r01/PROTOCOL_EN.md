# Protocol: constructive arrival witnesses (W4 prerequisite)

Experiment ID: `20260921_w04_constructive_arrival_r01`. Created: 21 September 2026.
Stage: **W4 prerequisite**. **Protocol frozen before any implementation existed.**

## 1. The gap this closes, and why it is not blocked

The arrival-model task established that **only a constructive schedule yields an `UNDER` set**, and that
`UNDER` is the only direction Rule A accepts for a `SUPPORTED` verdict. It also left the obvious hole:
`ConstructiveArrivalModel` takes `(earliest, latest)` tuples **as input**. Nothing generates them, and
nothing verifies that the times in them are achievable. The `UNDER` label is currently an assertion.

**Why this can proceed while W4 cannot.** A constructive schedule answers: *can this vehicle be at this
station during this interval, and here is the control that does it?* That question needs the vehicle's
kinematic limits and the path — **not** the evader policy (D08) and **not** the capture thresholds (D06).
Those decide *which* opportunity is worth having and *whether contact counts as capture*; they do not
decide whether a vehicle can be somewhere at a time.

So the single-vehicle half of the constructive-witness problem is unblocked, and it is the half that
carries the `UNDER` justification.

## 2. What is built

`opportunities/schedule.py`:

- `SpeedProfile` — a sequence of constant-acceleration segments with exact closed-form integration of
  time, speed and distance.
- `earliest_arrival(...)` — accelerate to the limit, then cruise. Returns the time **and the profile**.
- `arrival_at(...)` — a profile arriving at **exactly** a requested time `t ≥ t_min`. This is the
  construction that makes the interval *full* rather than a pair of endpoints.
- `constructive_arrival_set(...)` — an `ArrivalSet` labelled `UNDER`, where the label is **earned**:
  every reported time has a schedule, and the schedules are verified legal.
- Blocking windows — intervals during which the station cannot be occupied — which make the resulting set
  **nonconvex**, the case the method specification requires and the convex hull destroys.

## 3. Acceptance criteria — frozen before implementation

Verification is by **integration of the produced profile**, never by re-asserting the formula that produced
it. A schedule is accepted only if simulating it lands the vehicle where and when it claims.

| Id | Criterion | Threshold |
|---|---|---|
| **C1** | The earliest schedule arrives at exactly `t_min`: integrating it covers the distance at that time | `1e-9` |
| **C2** | **Interval fullness.** For densely sampled `t` in `[t_min, t_max]`, `arrival_at(t)` returns a profile that integrates to arrival at exactly `t` | `1e-9`, ≥ 200 samples |
| **C3** | **Legality.** Every segment respects `0 ≤ v ≤ v_limit` and `−b_max ≤ a ≤ a_max` | zero violations |
| **C4** | **`UNDER` is earned.** Every time in the returned set has a verified legal schedule | zero unverified times |
| **C5** | **Nonconvexity.** With a blocking window the set is a union of ≥ 2 disjoint intervals, and every sub-interval is still fully scheduled | ≥ 2 intervals, C2 holds per interval |
| **C6** | **End to end.** Constructive sets drive the real compatibility predicate to `SUPPORTED` on a case where free-flow sets give `UNKNOWN` | exact verdicts |

**Gate rule, fixed now:** `SUPPORTED` only if all six hold. Any other result is `NOT_SUPPORTED`.

**The claim this can support, stated in advance:** that an `UNDER`-approximating arrival set **can be
produced and its label earned** — in the declared finite abstraction. That is strictly weaker than
producing one on a real road network, which is W4's job.

## 4. What this explicitly does not establish

- **Not** that constructive witnesses can be produced on a real SUMO network. The abstraction here is
  motion along a one-dimensional path with bounded acceleration; no junctions, no lane changes, no traffic,
  no signals.
- **Not** that interaction between participants is handled. A schedule that accounts for other vehicles'
  committed plans is the harder half, and it is scoped out here and named as remaining work.
- **Not** physical feasibility, assistance, learning, benefit, transfer or novelty.
- The capture thresholds remain **proposed, not frozen** (D06); the evader policy remains **unresolved**
  (D08). Neither is touched.

## 5. Resource limits

**0 SUMO process starts, 0 episodes, 0 optimizer updates, 0 checkpoint loads, 0 TEST accesses.** W4's
two-CPU-hour cap is **not** consumed; this is a prerequisite on its own engineering line.

## 6. Process rules carried forward

Protocol before implementation (D-06). Lint and format to completion **before** the run that produces the
package (A-09). The runner refuses to write into a sealed package (D-04, D-11). Verification by
integration, not by restating the generating formula — the W1 fixture discipline applied to code that
generates its own answers.

## 7. Outputs

The standard package set. Sealed after all writing has finished.
