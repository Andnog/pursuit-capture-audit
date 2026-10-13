# Scientific decision — W2 contracts, dependency lock and admission

Experiment: `20260921_w02_contracts_r01`. Date: 21 September 2026.

**Decision: `ENGINEERING_ACCEPTANCE_SUPPORTED; D16 RESOLVED; D06 AND D07 PROPOSED NOT FROZEN; PROCEED TO W3 ADAPTER.`**

---

## 1. What was implemented

| Component | Status |
|---|---|
| Four JSON schemas, all closed | IMPLEMENTED, TESTED |
| Semantic invariants over episode results | IMPLEMENTED, TESTED |
| Oriented-rectangle body geometry | IMPLEMENTED, TESTED against hand-derived values |
| Independent capture judge | IMPLEMENTED, TESTED including the dwell boundary |
| Safety admission interface, trivalent | IMPLEMENTED, TESTED |
| Public observation builder and action menu | IMPLEMENTED, TESTED |
| Physical preflight | IMPLEMENTED, RUNS, blocks on version mismatch |
| Dependency lock | RESOLVED — `pyproject.toml`, `uv.lock`, `THIRD_PARTY_NOTICES.md` |
| Task, reward, assistance and split contracts | WRITTEN |
| Simulator adapter, evader policy, learner | **NOT IMPLEMENTED** — W3 and W6 |

145 tests across 10 modules, all passing; lint clean; the W0–W1 regression 14/14.

## 2. What was independently verified

**Schemas reject what they must.** Every required field in the observation, the nested vehicle record and
the episode result was deleted in turn and rejected. Out-of-range values, wrong enums and unknown extra
keys are rejected. All problems are reported, not just the first.

**Semantic invariants reject records that schemas cannot.** Most importantly: **a capture whose required
audit is unresolved cannot record `Z = 1`.** Also `Z = 1 ⟹ Y = 1`; `Y = 0 ⟹ Z = 0`; a safety failure or
failed physical validity cannot coincide with a capture; an incomplete trace forces `Y = UNKNOWN`;
not-executed cases stay in the denominator carrying no outcome.

**Body geometry is exact on hand-checked configurations.** Side-by-side centres 3.0 m apart give 1.2 m;
in-line centres 6.0 m apart give 1.0 m; overlap gives 0.0; a perpendicular case gives 0.6 m. Separation is
symmetric and heading differences wrap correctly near ±π.

**The capture predicate's four derived properties hold, and three are demonstrated on traces:**

1. **Ordinary following is not capture.** A trace at the historical O26 measured following gap of 2.5009 m
   is rejected, because `contact_gap_max_m` = 2.00 m sits below `min_gap_m` = 2.5 m. The historical
   programme's central negative finding is encoded in the predicate rather than left to a judge.
2. **A fly-through cannot satisfy the dwell.** Closing from 2.00 m to 0.30 m at the maximum relative speed
   takes 1.70 s, short of the 2.00 s dwell. Verified on a synthetic closing trace.
3. **The dwell boundary is exact.** 20 consecutive frames span 1.9 s and are rejected; 21 frames span
   exactly 2.0 s and are accepted.
4. **The witness cannot be shared.** Two pursuers holding 1.1 s each — 2.1 s in total — are rejected,
   because neither alone reaches the dwell.

**`UNKNOWN` is never permission.** A missing frame yields `UNKNOWN`, not 0. An unresolved neighbour yields
`UNKNOWN` admission whose `permits_execution` is false. An empty admission sequence is `UNKNOWN`, because
nothing was checked. One supported step does not certify a sequence.

**The environment is internally consistent.** SUMO binary 1.21.0, `traci` 1.21.0, `sumolib` 1.21.0,
CPython 3.14.6, agreeing. No episode was run.

**The W0–W1 result survives the source change.** W2 reformatted 12 of the 16 implementation files recorded
by the W1 package. The fourteen cases re-run against the reformatted source and the **unchanged** frozen
expectations: 14/14.

## 3. Decisions resolved and not resolved

**D16 — RESOLVED.** CPython 3.14.6; SUMO 1.21.0 as an **external system dependency**, not a pip package;
`traci`/`sumolib` 1.21.0; `numpy` 2.3.3; `jsonschema` 4.25.1; `ruff` 0.14.5 (dev); `torch` 2.14.0 pinned in
an optional group and **not installed**.

Two findings shaped this and are recorded rather than smoothed over:

- **`eclipse-sumo` has no macOS arm64 wheel.** `uv` resolves it but cannot install it. The binaries present
  came from a separate channel with the wheel tag `cp310-cp310-macosx_14_0_arm64`, unusable from CPython
  3.14. So the binary and the bindings come from different channels and **can drift apart silently** — a
  binding speaking a different TraCI version returns wrong state instead of raising. `preflight.py` blocks
  on that, and `uv sync` alone is not a sufficient environment.
- **The interpreter was chosen against a later constraint, not a current one.** CPython 3.14 was checked to
  have `torch` 2.14.0 `cp314` macOS wheels before being pinned. An interpreter that worked for W2 but
  blocked the learner at W6 would have forced a re-pin and invalidated the environment record.

**D06 — PROPOSED, NOT FROZEN.** All seven contact parameters have values, physical derivations, boundary
cases and a consistency check that the code enforces. D06 names the **Research lead**, and the freeze is
required before W4.

One tension is recorded openly rather than settled by the implementer: `capture_speed_max_mps` is the
single parameter most able to decide the project's outcome **by definition rather than by evidence**. At
2.00 m/s, capture means the evader was brought near a stop — the containment reading — which risks pushing
successes toward the administrative route endpoint that the master plan requires be reported separately. A
higher bound admits "moving containment", which is a different scientific claim needing its own
construct-validity argument. **The Research lead must choose the reading explicitly.** Lowering it after
seeing results, or raising it to obtain successes, is prohibited.

**D07 — PROPOSED, NOT FROZEN.** Observation fields, action menu, validity masks, fallback and deadline are
specified and implemented at contract level. Nothing is implemented against the simulator; the freeze
follows W3 integration.

**Still UNRESOLVED:** D08 evader policy; D10 operational commitment values; D11 planner; D05 learned
baseline; D12 helper and intervention-time rules; D15 splits and maps; D17 learner configuration.

## 4. What evidence is missing

Everything that requires running the simulator. No episode has been executed in this project, so **none of
this has been exercised against a real SUMO trace**. The judge has never seen a trace SUMO produced; the
admission interface has never guarded a real step; the observation builder has never been fed real vehicle
state.

The **arrival model does not exist**. This is the load-bearing gap, and the risk was quantified before W2
began: the historical O28 audit recorded `382` `UNKNOWN` predicted lane exits containing **all** `352`
observed lane changes, and concluded `MODEL_INADEQUATE_FOR_COUNTERFACTUAL_INTERCEPTION` because free-flow
estimates are lower bounds with no attainable upper bound under interaction. Under Rule A of the method
specification, arrival sets from such a model are `OVER`-approximations and **can never return
`SUPPORTED`**. W2 has built the machinery that consumes arrival sets; it has not shown that usable arrival
sets can be produced.

Obligation **O22** is untouched: the directional/time safety proof, the second original safety regression
and capture preservation all remain open. The admission interface implemented here is an **empirical local
guard, not a formally synthesised shield** — which is precisely the gap O22 names.

## 5. Gate status

| Gate | Verdict | Basis |
|---|---|---|
| W2 engineering acceptance | **SUPPORTED** | preflight consistent; 145/145 tests; 14/14 regression; lint clean |
| W1 analytical correctness | **SUPPORTED, re-verified** | 14/14 against unchanged frozen expectations after reformatting |
| W0 novelty | **NOT SUPPORTED** | unchanged; required comparison families still unread |
| Physical feasibility | **NOT ASSESSED** | no episode has been run |
| O22, O27, O28 | **UNCHANGED** | nothing here discharges them |

Engineering acceptance **permits only the next gated scientific test**. It is not a scientific result.

## 6. Next permitted task and dependencies

**W3 — minimal fresh adapter, representation, memory, judge wiring and event logging.** Dependencies
satisfied: contracts exist, schemas validate, the preflight passes, and the dependency lock is resolved.

W3 must deliver: `simulator/sumo_adapter.py` written against the pinned TraCI API — **not** an adapter that
imports the old project; `simulator/snapshot.py` with validated pause/resume; `simulator/evader.py` once
D08 is resolved; candidate generation over a real topology; and offline validation of the public-information
boundary, masks, fallback, deadlines and state restoration. **No RL.**

W3 must also confront the `libsumo` absence: the adapter uses the TraCI socket interface, which has
consequences for determinism and speed that bear directly on the replay coupling the assistance audit
requires.

**Blocked, and not unlocked by this result:** W4 offline constructions require the D06 freeze and a
validated arrival model. W5 native work requires the W4 gate, O22 safety evidence and D04 reconciliation of
the exhausted capability-intervention allowance. W6 learning requires the native feasibility gate and D04
reconciliation of the exhausted learning allowance. TEST remains closed, and its historical counterpart has
not even been located.

## 7. What this decision does not authorize

No SUMO episode. No optimizer run. No checkpoint load. No TEST access. No unattended campaign, heartbeat or
automatic retry. No reset of any inherited counter. No weakening of the capture predicate or the safety
conditions — in particular, **no adjustment of `capture_speed_max_mps` in response to results**. No claim
of feasibility, learning, benefit, transfer, novelty, doctoral sufficiency or journal readiness.
