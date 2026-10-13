# Scientific decision — W3 adapter, state restoration and candidate generation

Experiment: `20260921_w03_adapter_r01`. Date: 21 September 2026.

**Decision: `ENGINEERING_ACCEPTANCE_SUPPORTED; TRACI SURFACE UNVALIDATED; W4 BLOCKED ON D06, D08 AND THE ARRIVAL MODEL.`**

---

## 1. What was implemented

| Module | Status |
|---|---|
| `simulator/backend.py` — backend protocol, `DeterministicBackend`, explicit random stream | IMPLEMENTED, TESTED |
| `simulator/snapshot.py` — complete capture and restore with fingerprinting | IMPLEMENTED, TESTED |
| `simulator/sumo_adapter.py` — `EpisodeAdapter`: observation, masks, deadline, fallback, proposed vs executed | IMPLEMENTED, TESTED offline |
| `simulator/sumo_adapter.py` — `TraciBackend` | **DECLARED, NOT IMPLEMENTED** (W4) |
| `simulator/evader.py` | **NOT CREATED** — D08 unresolved |
| `opportunities/generator.py` — enumeration, accounted pruning, deterministic truncation | IMPLEMENTED, TESTED |
| `evidence/records.py`, `evidence/provenance.py` | IMPLEMENTED, TESTED |

All nine frozen checks pass, 49 tests within them; the full suite is 188 tests on the pinned environment
and 188 with 94 skipped on a bare interpreter; lint clean.

## 2. What was independently verified

**State restoration is exact.** Running 60 steps uninterrupted and running 30, snapshotting, restoring into
a fresh backend and running the remaining 30 produce an **identical fingerprint** over clock, bodies,
pending commands, commitment memory and the random stream. A command issued before the snapshot survives
it, and the restored run stays identical for a further 20 steps — the failure mode where a snapshot looks
correct at capture time and diverges on the next step is tested for directly.

**A shared seed is demonstrably not a shared noise realisation.** Two backends built from the **same seed**
and stepped the same number of times end in different states when they carry a different number of
vehicles, because they consume a different number of draws. Two same-seed runs separated by a single
different command diverge and do not reconverge. The assistance protocol asserts this; W3 shows it.

**And the converse: a verified prefix does couple them.** Restoring a captured prefix and issuing identical
commands reproduces the factual run exactly. That is the property an assistance replay actually needs, and
it is now demonstrated rather than assumed.

**The information boundary holds at every decision.** Twelve consecutive decisions each emit an observation
passing the closed schema and the semantic invariants. The selector receives exactly six keys and no
backend handle. The clock stays synchronised with the decision index, because it is derived from it rather
than supplied.

**Masks, fallback and deadline behave as contracted.** A neighbour within one decision interval invalidates
the speed-increasing action **with a recorded reason**; `HOLD_LANE` stays valid, so a fallback always
exists. A selector returning nothing, or an out-of-range index, executes the fallback rather than crashing.
A selector exceeding the inference deadline has its action **discarded**: the miss is recorded and the
fallback executes, because a late action is an action taken on a stale world.

**Pruning is accounted and reconciles.** Enumerated equals kept plus pruned plus truncated plus
deduplicated, with every removal carrying a reason and a key. A rejected candidate is **counted, not
forgotten** — the distinction the historical O26 diagnostic could not make between "no reachable
complementary candidate existed" and "the controller never created one". Truncation is recorded and its
ordering is deterministic across runs.

**Finite case F1 reappears through the generator.** On a 14 m lane the three-participant candidate is
rejected while all three pairs survive, reached through enumeration rather than asserted directly, and the
pairwise mode labels every opportunity it produces as *not* a team-feasibility certificate.

**Evidence rows cannot be inflated at construction.** Building a row with `Y=1, Z=1` and audit coverage 0.5
raises rather than writing. Not-executed rows stay in the denominator carrying `UNKNOWN`. An unresolved
audit widens the logical bounds from `[0, 0]` to `[0, 0.5]` instead of being counted as a success.

## 3. What was explicitly NOT verified

**The TraCI call surface. No SUMO process was started in this stage.** Every check above ran against
`DeterministicBackend`, an in-memory kinematic fixture that is not a traffic simulator and is not claimed
to be one. The adapter's behaviour *above* the backend protocol is validated; the translation *into* TraCI
calls is written and unexercised.

This was a choice, and the reasoning is recorded rather than the cost hidden. Native execution is gated
behind W4 and W5, which require the D06 freeze, a validated arrival model and the O22 safety evidence that
remains open. Starting a simulator to "just check the adapter works" would take a native step before its
gate — and obligation O22 exists precisely because such steps were once taken before their proofs. The
price is that W4 must exercise the TraCI surface for the first time, under its own gate, and should expect
to find defects there.

Also unverified: arrival sets computed from a real road network; anything physical, learned or comparative.

## 4. What evidence is missing, and what blocks what

**The arrival model still does not exist.** W2 built the machinery that consumes arrival sets; W3 built the
generator that enumerates candidates over them. Neither produces them. The recorded risk is unchanged and
quantified: historical O28 found `382` `UNKNOWN` predicted lane exits containing **all** `352` observed
lane changes, and concluded `MODEL_INADEQUATE_FOR_COUNTERFACTUAL_INTERCEPTION` because free-flow estimates
are lower bounds with no attainable upper bound under interaction. Under Rule A such sets are
`OVER`-approximations and **can never return `SUPPORTED`**. On that model, everything built in W2 and W3
would return `UNKNOWN` for every opportunity.

**D08 is now a hard blocker.** The evader policy is unresolved, so `simulator/evader.py` does not exist and
no episode can be defined, let alone run.

**D06 remains proposed, not frozen.** The Research lead must choose the reading of
`capture_speed_max_mps` — "brought near a stop" versus "moving containment" — before W4.

**O22 is untouched.** The safety admission interface is an empirical local guard, not a formally
synthesised shield. The directional/time proof, the second original safety regression and capture
preservation all remain open.

## 5. Gate status

| Gate | Verdict | Basis |
|---|---|---|
| W3 engineering acceptance | **SUPPORTED** | 9/9 frozen checks; 188 tests on both interpreters; lint clean |
| W2 engineering acceptance | **SUPPORTED, re-verified** | full suite passes unchanged |
| W1 analytical correctness | **SUPPORTED, re-verified** | full suite passes unchanged |
| W0 novelty | **NOT SUPPORTED** | unchanged; required comparison families still unread |
| Physical feasibility | **NOT ASSESSED** | no SUMO process has been started |
| O22, O27, O28 | **UNCHANGED** | nothing here discharges them |

Engineering acceptance permits only the next gated step. It is not a scientific result, and three stages of
it do not add up to one.

## 6. Next permitted task and its dependencies

**W4 — two complete offline assisted-capture constructions**, at a limit of two CPU hours total and at most
100,000 search expansions per original O26 case.

W4 cannot start until:

1. **D08 is resolved** — the evader's public-information policy, continuation rule and endpoint semantics.
2. **D06 is frozen** by the Research lead.
3. **An arrival model exists and is validated** on an independently selected, contract-compatible
   diagnostic set, with acceptance criteria frozen **before** that set is examined, declaring its
   approximation direction and reporting every unsupported case as `UNKNOWN`.

W4 must also exercise the TraCI surface for the first time and validate pause/resume against
**uninterrupted native execution**, not only against the deterministic backend. The `libsumo` absence means
the socket interface is the only option, and its determinism guarantees are weaker than the fixture's —
the coupling demonstrated in W3 must be re-established natively before any replay result is used.

**May proceed in parallel, independent of the above:** resolving T-CARE and the sequential pursuit-planning
record to primary citations; upgrading the dynamic-termination record to method-section depth; selecting
the conventional planner (D11) and the closest learned baseline (D05).

## 7. What this decision does not authorize

No SUMO episode. No optimizer run. No checkpoint load. No TEST access. No unattended campaign, heartbeat or
automatic retry. No reset of any inherited counter. No weakening of the capture predicate or the safety
conditions. No claim of feasibility, learning, benefit, transfer, novelty, doctoral sufficiency or journal
readiness. In particular, **nothing here licenses the statement that the adapter works** — only that its
contract behaviour is correct against a fixture.
