# Protocol: W3 adapter, state restoration and candidate generation

Experiment ID: `20260921_w03_adapter_r01`. Created: 21 September 2026. Stage: W3.
**This protocol was written before any W3 implementation existed and before any outcome was observed**,
correcting W2 deviation D-06.

## 1. The central constraint: W3 is validated offline

Master plan §10 sets the W3 acceptance as *"Public-information boundary, masks, fallback, deadlines and
state restoration validated **offline**; no legacy runtime import"*, with the resource limit *"Bounded
implementation task; no RL"*.

**No SUMO process is started in this stage.** Native execution is gated behind W4 and W5, which require the
D06 freeze, a validated arrival model, and the O22 safety evidence that remains open. Starting a simulator
now to "just check the adapter works" would take a native step before its gate, and obligation O22 exists
precisely because such steps were taken before their proofs.

This has a cost, and the cost is stated rather than hidden: **the TraCI adapter will not have been
exercised against a real SUMO process when W3 closes.** That is the first thing W4 must do, under its own
gate. What W3 can honestly establish is that the adapter's *contract behaviour* — boundary, masks,
fallback, deadline, snapshot and restore — is correct against a substitutable backend.

## 2. Design that makes offline validation meaningful

The adapter is written against a **backend protocol**, not against `traci` directly. Two implementations:

- `TraciBackend` — written against the pinned TraCI API of SUMO 1.21.0. **Not executed in W3.**
- `DeterministicBackend` — an in-memory kinematic backend with exact, inspectable state.

Everything the adapter does above the backend — building the public observation, computing masks, applying
the fallback, enforcing the deadline, capturing and restoring state — is backend-independent and is
validated against `DeterministicBackend`. What remains unvalidated is exactly the TraCI call surface, and
that is recorded as such.

## 3. Acceptance rule — fixed before outcomes

`SUPPORTED` only if **all** of the following hold:

1. **State restoration is exact.** Running `N` steps uninterrupted and running `N/2`, snapshotting,
   restoring and running the remaining `N/2` produce byte-identical state, including pending commands,
   controller memory and the random stream.
2. **A shared seed is demonstrated to be insufficient after divergence.** Two runs from the same seed that
   differ in one action consume the random stream differently and separate. This is a claim the assistance
   protocol already makes; W3 must demonstrate it rather than assert it.
3. **The information boundary holds at every decision.** Every observation the adapter emits validates
   against the closed schema and the semantic invariants; no prohibited key is reachable.
4. **Masks and fallback behave as contracted.** An inadmissible action is never selectable; with no valid
   action the contract fallback executes and is recorded as `FALLBACK`.
5. **The deadline is enforced.** A selector exceeding the inference deadline yields a recorded deadline
   miss and the always-valid fallback, never a late action.
6. **Proposed and executed are logged separately** whenever a guard clamps a command.
7. **The generator's pruning is accounted.** Every candidate removed at every stage is counted with its
   reason; the counts reconcile to the number enumerated.
8. **Episode result rows validate** against the schema and the semantic invariants.
9. No legacy runtime import; lint clean; every earlier stage's tests still pass.

Any other result is `NOT_SUPPORTED`. Claim class: **engineering acceptance only**.

## 4. Resource limits

**0 SUMO episodes, 0 SUMO process starts, 0 optimizer updates, 0 checkpoint loads, 0 TEST accesses.** The
preflight may invoke `sumo --version`; nothing else touches the simulator.

## 5. Process rules carried from earlier deviations

- This protocol precedes implementation (corrects D-06).
- Lint and format run to completion **before** the run that produces the package (corrects A-09).
- The runner refuses to write into a sealed package (corrects D-04 and D-11).
- No prose list is pattern-matched as data (corrects D-02 and D-08).

## 6. What a PASS does and does not establish

**Does establish:** the adapter's contract behaviour is correct against a deterministic backend; state
restoration is exact and is a prerequisite the assistance audit can rely on; the generator accounts for
what it discards.

**Does not establish:** that the TraCI call surface is correct — **no SUMO process was started**; that
arrival sets can be computed from a real network; physical feasibility; assistance; learning; benefit;
transfer; novelty. The capture parameters remain **proposed, not frozen**.

## 7. Outputs

`plan.json`, `inputs.json`, `domain.json`, `environment.json`, `events.jsonl`, `results.jsonl`,
`result.json`, `DEVIATIONS_EN.md`, `SCIENTIFIC_DECISION_EN.md`, `checksums.json`. Sealed only after all
writing has finished.
