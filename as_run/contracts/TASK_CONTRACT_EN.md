# Task contract

Stage: W2. Date: 21 September 2026.
Status: **specified and implemented; capture parameters PROPOSED, not frozen.**

Machine-readable form: [`task_contract.json`](task_contract.json) and
[`../configs/domain_v1.json`](../configs/domain_v1.json). Where this document and the configuration
disagree, **the configuration is authoritative** — the code reads the configuration, never this text.

## 1. The task

Five pursuers and one moving evader on a lane-constrained urban road network, simulated in Eclipse SUMO
1.21.0. Vehicle bodies are 5.0 m × 1.8 m rectangles. Horizon 300 s, physical step 0.1 s, decision interval
1 s — 3000 physical steps and 300 decisions per episode. Starts are dispersed and moving; there is no
staged cage and no assigned finisher.

Selection is **centralized**: one selector observes the public projection for all pursuers and emits the
joint decision. This is declared, not disguised. It is not CTDE and supports no decentralized-execution
claim.

## 2. Information boundary

The selector receives exactly the fields in [`public_observation.schema.json`](public_observation.schema.json).
The schema is **closed**: an unknown key is rejected rather than ignored, so a prohibited field cannot be
smuggled in as an extra property.

**Observable:** per vehicle — id, class, position, speed, heading, lane, lane position, body dimensions.
Shared — simulation time, decision index, topology version, publicly displayed signal phases. The road
network is public and static, and is available for unseen cities under the declared deployment interface.

**Not observable, enumerated in `configs/domain_v1.json` under `prohibited_observation_keys`:** the evader's
route or any future position; any judge or audit output; private simulator fields; held-out or TEST
quantities; another agent's memory, intent or policy parameters; the factual outcome of an episode under
audit.

Two simplifications are declared rather than hidden: observation noise is zero, and the sensing radius is
unbounded over the six task vehicles. Partial observability and sensor noise are separate studies.

`build_public_observation` is the only constructor, so there is exactly one place to audit. It **derives**
`simulation_time_s` from the decision index and the contract interval rather than accepting a caller's
clock, so an observation cannot be desynchronised from the decision it belongs to.

## 3. Actions

Six public actions with stable ids and codes: `HOLD_LANE` (0), `CRUISE` (1), `SLOW` (2), `STOP_AT` (3),
`CHANGE_LANE` (4), `TURN_AT_NEXT_JUNCTION` (5). The menu is **data**, read from the configuration, so the
contract and the code cannot disagree about which actions exist.

Every action carries a per-vehicle validity bit from the public state and the safety admission interface.
An invalid action must record a reason: an action marked unusable with no explanation is indistinguishable
from a masking bug.

The executor allocates no helper, assigns no finisher role and encodes no hidden cooperation. **Any
coordination must come from the selector's choice among these actions.**

With no valid action the vehicle executes the contract-defined fallback. `HOLD_LANE` is declared
`always_valid`, so a fallback always exists and **the selector never invents an action**. The inference
deadline is 0.5 s; a miss is recorded and `HOLD_LANE` executes.

Proposed action and executed command are logged **separately**, because the guard may clamp the second
without changing the first. Finite assistance case A4 exists to keep that distinction enforced.

**Implementation status: contract only.** No action is implemented against the simulator; the adapter is W3.

## 4. The capture predicate — D06

Operational contact is a defined close interaction **without collision**, held continuously. It is not
mechanical impact and it is **not** physical restraint of a real vehicle.

| Parameter | Proposed | Bound by |
|---|---|---|
| `contact_gap_min_m` | 0.30 m | strictly positive; 30 × the geometry tolerance |
| `contact_gap_max_m` | 2.00 m | **strictly below `min_gap_m` = 2.5 m** |
| `capture_speed_max_mps` | 2.00 m/s | far below urban circulation speed |
| `relative_speed_max_mps` | 1.00 m/s | band traversal must take less than the dwell |
| `orientation_tolerance_rad` | 0.2618 (15°) | accommodates lane curvature, excludes crossing |
| `dwell_time_s` | 2.00 s | 2 decision intervals, 20 physical steps |
| `geometry_tolerance_m` | 0.01 m | polyline discretisation, not float noise |

Full derivations and boundary cases are in the configuration. Four properties follow and are asserted by
tests:

1. **Ordinary following is excluded by construction.** The historical O26 diagnostic measured minimum
   prey/pursuer body gaps of 2.5009–2.5016 m across four full episodes and recorded that "proximity and
   ordinary following do not constitute capture". Because `contact_gap_max_m` < `min_gap_m`, that finding is
   encoded in the predicate instead of being left to a judge to apply.
2. **A fly-through cannot satisfy the dwell.** Band width 1.70 m ÷ maximum relative speed 1.00 m/s = 1.70 s,
   which is **less** than the 2.00 s dwell. A valid capture requires separation that is actually held.
3. **Capture cannot coincide with collision.** `contact_gap_min_m` is 30 × the geometry tolerance.
4. **The dwell is an integer number of physical steps** (20), so the witness aligns with recorded frames.

Separation is **body-to-body**, computed from oriented rectangles. Centre distance is not a substitute:
obligation O22 recorded a native collision at a reported positive body gap of 1.959 m precisely because
separation came from station arithmetic rather than geometry.

**These values are `PROPOSED_PENDING_RESEARCH_LEAD_FREEZE`.** D06 names the Research lead and requires the
freeze before W4. One tension is recorded openly in the configuration: `capture_speed_max_mps` is the
parameter most able to decide the project's outcome by definition rather than by evidence, and the choice
between "brought near a stop" and "moving containment" is a construct-validity decision, not an
implementation detail. Lowering it after seeing results, or raising it to obtain successes, is prohibited.

## 5. The judge

`evaluation/capture_judge.py` receives a trace and the contract. It never receives a policy, a reward or an
opportunity. It is trivalent:

- **`SUPPORTED`** — a single pursuer held every condition continuously for at least the dwell.
- **`REJECTED`** — no continuous run reaches the dwell.
- **`UNKNOWN`** — the trace has missing frames or is declared incomplete.

The witness must be held by **one** pursuer throughout. Allowing the role to pass between pursuers
mid-interval would let a sequence of brief proximities masquerade as one sustained containment. A safety
failure inside the interval invalidates the witness. **An incomplete trace is unresolved evidence, not
observed failure.**

## 6. Outcomes

`Y` is independently validated safe operational capture by 300 s. `Z` is capture **together with** positive
evidence under the frozen assistance audit. Endpoint causes are enumerated in the configuration.

`CAPTURE_MOVING_CIRCULATION` and `CAPTURE_AFTER_ROUTE_ENDPOINT` are reported **separately and never
summed**. Only the former counts toward the primary moving-evader outcome.

## 7. Two validation layers

Schemas reject structurally wrong records. **Semantic invariants** reject records that are structurally
valid but scientifically wrong — JSON Schema cannot express them, and each corresponds to a way the primary
endpoint could be silently inflated or a failure silently erased:

- `Z = 1` requires `Y = 1`;
- `Y = 0` requires `Z = 0`;
- **`Z = 1` requires `audit_coverage = 1.0`** — a capture whose required audit is unresolved gives
  `Z = UNKNOWN`, never 1;
- a capture endpoint cause requires `Y = 1`, and `Y = 1` requires a capture endpoint cause;
- `SAFETY_FAILURE` or `physical_validity = FAIL` cannot coincide with `Y = 1`;
- an incomplete trace requires `Y = UNKNOWN`;
- `NOT_EXECUTED` and `CANCELLED` keep the case in the denominator with `Y = Z = UNKNOWN`;
- `POSITIVE_ACROSS_FAMILY` requires full audit coverage.

A record must pass **both** layers.

## 8. What this contract does not establish

SUMO acceptance is **not** independently validated Ackermann dynamics. The safety admission interface is an
empirical local guard, **not** a formally synthesised shield — obligation O22 remains open on exactly that
point. Nothing here establishes physical feasibility, runtime feasibility, assistance, learning, benefit,
transfer or novelty.
