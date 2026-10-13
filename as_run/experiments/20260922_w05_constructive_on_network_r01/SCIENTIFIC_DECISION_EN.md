# Decision — the constructive chain on a real network

**Claim class: does an abstraction-level result transfer to the simulator.** No capture, no assistance, no
learning, no optimizer, no checkpoint, no TEST map. Nothing here discharges O22.

## Verdict

`CONSTRUCTIVE_TIMES_FAIL`.

**A constructively certified arrival time does not hold on the network. Every arrival was late.**

## Measured

Tolerance **0.1 s**, declared before the run as the simulator's own observation resolution.

**Arm 1 — one vehicle, kinematics alone.** Station at 1042.5 m along an 18-edge route.

| Target `t*` (s) | Actual (s) | Error (s) | Clamped steps |
|---|---|---|---|
| 77.722 | 82.400 | **+4.678** | 144 |
| 97.152 | 99.800 | **+2.648** | 93 |
| 124.355 | 126.600 | **+2.245** | 86 |
| 155.444 | 156.400 | **+0.956** | 52 |

**Arm 2 — the mutual-consistency witness, three participants driven concurrently.**

| Participant | Committed (s) | Actual (s) | Error (s) | Clamped steps |
|---|---|---|---|---|
| p1 | 77.722 | 87.400 | **+9.678** | 268 |
| p2 | 79.162 | 84.400 | **+5.238** | 192 |
| p3 | 80.602 | 90.000 | **+9.398** | 652 |

**Seven arrivals, seven late, none early.** The consistent sign is what makes this a refutation rather than
noise. The tighter the schedule the larger the error, and adding participants roughly doubles it.

## Mechanism, and why it is not avoidable

SUMO's safety layer was left **on**, so `setSpeed` is a request. It was overridden on 52–144 of roughly
780–1550 commanded steps with one vehicle, and on up to 652 with three.

The network carries **four traffic lights against 378 unregulated `priority` junctions**. So the lateness is
**not** a signals problem that a different route could dodge. It is junction right-of-way logic and
internal-edge handling — which the finite abstraction omits entirely, and which is what an urban network is
made of.

## Consequence, stated plainly

The arrival-model diagnostic refuted `UNDER` for **predictive** models: 0 of 5598 certified bounds. The
constructive route was the answer — only an executable schedule earns `UNDER`, and it did, with a worst
distance error of `4.26e-14` m in the abstraction.

**That rescue does not survive contact with the network.** Rule A admits `SUPPORTED` only when every arrival
set `UNDER`-approximates. A witness that arrives 4.7 s late is not an `UNDER` set on the network.

So, on a real lane network and under the construction as it stands: **no opportunity can be `SUPPORTED`** —
the same conclusion reached for predictive models, now for constructive ones.

## What would repair it, and what each would cost

1. **Model junction delay inside the profile.** Correct in principle. Requires a *certified upper bound* on
   junction delay, not a measurement; without certification the `UNDER` label is asserted again rather than
   earned, which is the defect the constructive work existed to remove.
2. **Construct with a certified margin.** Same problem: seven measurements are not a bound.
3. **Narrow the domain to junction-free approaches.** Honest, and probably too restrictive to be interesting:
   378 of 420 nodes are junctions.

None is free, and the first two must not be done by fitting a margin to these seven numbers.

## Limits

- **One route on one TRAINING map.** Seven measurements.
- A consistent direction with an identified mechanism — **not a proof.** Replication across maps and routes is
  required before stating this as general.
- Arm 2 tests committed **times**, not simultaneous lane occupancy under the capacity constraint. The joint
  occupancy question on the network remains untouched.
- The station edge is 0.95 m long, an artifact of selecting the edge at 60% of the route. Distance was
  measured by driving distance, so the result stands, but the geometry is worth knowing.

## What this does not establish

Nothing about capture, assistance, learning, benefit, transfer or novelty. The interaction operator and the
arrival witnesses remain correct **in the abstraction**; what is refuted is their transfer.
