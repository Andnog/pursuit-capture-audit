# Decision — O27

**Claim class: abstract feasibility under the declared model.** Offline: no SUMO process, no optimizer, no
checkpoint, no TEST map.

## Verdict

**`W4_GATE_NOT_PASSED`.** Zero complete constructions in eight cases. The gate required two among the four
AVOIDANT cases.

| Level | Case | Verdict | Captures needing their helper |
|---|---|---|---|
| AVOIDANT | adelaide_cbd | `NECESSARY_BUT_B1_NULL` | 6 |
| AVOIDANT | seattle_downtown | `CAPTURE_NOT_COORDINATED` | 0 |
| AVOIDANT | toronto_downtown | `CAPTURE_NOT_COORDINATED` | 0 |
| AVOIDANT | washington_downtown | `NO_WITNESS_WITHIN_CAP` | 0 |
| OPTIMAL_ESCAPE | adelaide_cbd | `NECESSARY_BUT_B1_NULL` | 14 |
| OPTIMAL_ESCAPE | seattle_downtown | `CAPTURE_NOT_COORDINATED` | 12 |
| OPTIMAL_ESCAPE | toronto_downtown | `NECESSARY_BUT_B1_NULL` | 87 |
| OPTIMAL_ESCAPE | washington_downtown | `CAPTURE_NOT_COORDINATED` | 0 |

## The verdict is robust

- **To the criterion.** Under the most lenient rule — necessity alone — AVOIDANT has captures needing their
  helper in **one** case of four, below the two required. Changing the criterion would not pass the gate.
- **To the CPU cap.** A diagnostic rerun reproduced 5 of 8 cases exactly; the other 3 hit their CPU budget
  and stopped at different points. The search returns on the first construction, and those three ran to their
  budget, so **neither run produced one**.

## What was found

**Coordination exists under the declared model.** In four cases a capture failed when the helper never acted.

**But none could be certified by D12's `b1` contrast.** In every such capture the helper's contribution was
**positional and established before D12's window**: on the real maps the evader's decisive choice came 6 to
33 s before the witness started. Five decisions of independent pursuit cannot move a helper that is already in
position. Against an evader that reads pursuer positions, positioning is the only way this model produces
coordination — so under the frozen D12 window, coordination is not certifiable here.

## What limits the reading

- **The search space.** Five of eight cases exhausted the candidate generator before their budget. "No
  construction" is relative to the generator's patterns — junction interception with holds of 6, 10 or 16 m
  and releases up to two decisions early — not to the budget.
- **The model under maneuvering.** Legal on all eight baselines, the declared model still produced emergency
  braking (1–3 events) or collisions (up to 5 058 steps of persistent overlap) under some construction plans.
  Verification rejected every one, so no invalid construction was accepted, but part of the searchable space
  was lost to model defects.
- **A known defect in the model version that ran.** Chained internal lanes are read as their first lane only.
  Found during the run and not fixed during it, so the recorded input hashes stay those of the code that ran.
  It makes the model optimistic at those junctions.

## Not established

That capture is infeasible — a failed search is not a proof. Anything native. Physical feasibility,
assistance, learning, benefit, transfer or novelty.

## What the plan says now

W5 requires the W4 gate. Fewer than two constructions means **stop and decide**, not extend.
