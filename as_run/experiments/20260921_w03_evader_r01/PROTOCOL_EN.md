# Protocol: scripted evader levels (W3 completion)

Experiment ID: `20260921_w03_evader_r01`. Created: 21 September 2026. Stage: **W3 completion**.
**Protocol written before the checks were run; the implementation followed the frozen D08 decision.**

## 1. What this completes

`simulator/evader.py` is named by master plan §4 as a W3 artifact. W3 closed **without it**, recorded as
deviation D-14: decision D08 was unresolved, and writing an evader then would have meant inventing the
policy whose properties the plan requires be justified.

D08 was **resolved and frozen on 21 September 2026**. The evader is a **scripted difficulty level**, not a
policy — three declared levels, deterministic, never faster than the pursuers. That removes the reason the
artifact was withheld, so it is now built to the decision rather than to a guess.

## 2. The design consequence that matters most

The capture contract (D06, frozen the same day) admits a capture in a cul-de-sac as **coordinated** only if
the evader was **forced** there, with positive evidence that no better exit was available where it entered.

That evidence has to come from somewhere, and the only place it can come from is **the evader's own
decision record**. So every decision logs its full admissible set, not just the choice. This module is the
link between D08 and D06; without it the dead-end rule would be unfalsifiable and the endpoint would be
decided by assertion.

## 3. Checks — frozen before running

| Id | Check |
|---|---|
| **E1** | **Determinism.** The same `(level, seed)` reproduces the same decisions exactly. |
| **E2** | **Keyed, not sequential, randomness.** A choice depends on the decision index, not on how many numbers anything else drew — so a restored prefix reproduces it. |
| **E3** | **The levels differ in difficulty.** Level 3 never enters a cul-de-sac while an alternative exists; level 1 sometimes does; level 3 never scores its own choice below what level 2 achieved. |
| **E4** | **The decision record supports the D06 dead-end rule.** Alternatives logged at every decision; `forced` only when every alternative was also a dead end. |
| **E5** | **Information boundary.** `choose` receives only the decision index, the current edge and the pursuers' **current** nodes. No future route, no oracle, no judge output. |
| **E6** | **Contract agreement.** The three levels, the determinism requirement and the no-faster-evader rule match `configs/domain_v1.json`. |

**Gate:** `SUPPORTED` only if all six pass, the full suite passes on both the pinned and a bare
interpreter, and lint is clean.

## 4. Resource limits

**0 SUMO process starts, 0 episodes, 0 optimizer updates, 0 checkpoint loads, 0 TEST accesses.** The
evader is exercised against the in-memory topology, exactly as W3 exercised the adapter.

## 5. What this does and does not establish

**Establishes:** the three levels behave as declared and differ in difficulty; decisions are reproducible
and auditable; the dead-end rule is checkable rather than rhetorical.

**Does not establish:** that any of this runs against a real network — **no SUMO process is started**. The
topology here is a small directed graph, not one of the 12 audited OSM networks. Nor physical feasibility,
assistance, learning, benefit or transfer.

**A conservative choice, recorded:** `was_forced_into_dead_end` credits the pursuers only when every
alternative at the entry decision was itself a dead end. A team might block an escapable alternative
without it being a cul-de-sac, and this test would not credit them. Crediting that needs occupancy evidence
at the entry decision, which this module does not have. **The strict reading is the one that cannot
over-credit**, and over-crediting is the failure mode that matters for the endpoint.
