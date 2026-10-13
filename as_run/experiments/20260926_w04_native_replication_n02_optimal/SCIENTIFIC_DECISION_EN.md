# Decision — N02: native replication, OPTIMAL_ESCAPE (reported, not gated)

**Two TRAINING maps yield a natively replicated construction against the OPTIMAL_ESCAPE evader** — seattle_downtown
and washington_downtown. This package cannot meet or fail the W5 prerequisite (its runner's summary line
"prerequisite MET" applies the N01 rule mechanically and is **not** a gate outcome here).

| Map | Verdict | Model search | Native checks |
|---|---|---|---|
| adelaide_cbd | `NO_WITNESS_WITHIN_CAP` | 4,616 exp, CPU cap 450 s | 0 |
| seattle_downtown | **`NATIVE_CONSTRUCTED`** | 386 exp, 38.9 s | 1 of 1 accepted |
| toronto_downtown | `NO_WITNESS_WITHIN_CAP` | 5,004 exp, CPU cap | 0 |
| washington_downtown | **`NATIVE_CONSTRUCTED`** | 237 exp, 40.5 s | 1 of 10 accepted; 9 failed the open-loop factual |

Constructions:
- seattle: finisher p5, helper p4 (10.5 m away at witness start), model witness 59.4 s; SUMO 60.0 s open and
  closed loop; b1 and helper-never-acts REJECTED in both loops.
- washington: finisher p3, helper p1 (23.2 m), model witness 94.4 s; SUMO 95.2 s open and closed; both contrasts
  REJECTED in both loops.

**Post-hoc check (not in the protocol):** no emergency braking (> 4.5 m/s²) in any factual arm. One arm —
washington b1 counterfactual, closed loop — has 18 steps of evader emergency braking from 103.5 s, after the
model's witness window: the closed-loop evader chooses a sharp continuation at its lookahead without the model's
caution. It does not create a capture; it makes that arm's trajectory not ordinary-legal from 103.5 s.

CPU 1,019 s wall; 5.3 s SUMO. TRAINING only.
