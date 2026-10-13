# Scientific decision — W0–W1 finite examples

Experiment: `20260920_w01_finite_examples_r01`. Date: 20 September 2026.

**Decision: `ANALYTICAL_CORRECTNESS_SUPPORTED; NOVELTY_NOT_ESTABLISHED; PROCEED TO W2 CONTRACTS ONLY.`**

---

## 1. What was implemented

A fresh Python package, `src/joint_interception/`, written under the new root, importing nothing from
either legacy runtime and depending on the standard library alone:

| Module | Content |
|---|---|
| `opportunities/types.py` | three-valued verdict algebra (`SUPPORTED`/`REJECTED`/`UNKNOWN`), the `Opportunity` record |
| `opportunities/reachability.py` | canonical nonconvex interval unions, exact intersection, `max_contiguous`, approximation-direction predicates |
| `opportunities/compatibility.py` | the joint predicate `C(q)`, its temporal/occupancy/movement components, and the pairwise relaxation `C_pair(q)` |
| `policies/memory.py` | commitment memory and the `CONTINUE`/`SWITCH`/`ABANDON` selection rule |
| `evaluation/assistance_audit.py` | contrast bounds, sensitivity envelope, assistance labels, endpoint bounds |

Supporting artifacts: `docs/METHOD_SPEC_EN.md` (specification), `configs/finite_examples_v1.json` (case
inputs), `tests/fixtures/finite_cases_v1.json` (hand-derived expected answers with arithmetic),
five test modules (58 tests), and `scripts/run_finite_examples.py`.

**Not implemented, and not claimed to be:** simulator adapter, evader policy, safety admission against real
geometry, capture judge, candidate generator over a real topology, any learner, any baseline arm, metrics
or statistics.

## 2. What was independently verified

All **14/14** planned cases PASS against expectations that were **derived by hand from the specification
before any implementation was written**, with the arithmetic recorded in the fixture so a third party can
check each answer without executing this code. Two additional variant checks PASS. The unit suite runs
58 tests, returncode 0.

Four properties were verified that are stronger than case-by-case agreement:

1. **The pairwise relaxation is unsound as a certificate of team feasibility.** On F1 the joint predicate
   returns `REJECTED` while `C_pair` returns `SUPPORTED`. The witness is exhaustively checkable: a lane of
   14.0 m usable length admits two 5.0 m bodies at a 2.5 m gap (12.5 m) but not three (20.0 m), so every
   pair fits and the triple does not.
2. **The convex hull is not a safe substitute for a nonconvex union.** On F3 the exact intersection is
   empty while the hull relaxation reports a 6.0 s window.
3. **The soundness rules are asymmetric, and the implementation honours the asymmetry.** The same two
   arrival sets give `REJECTED` under `OVER` labels and `UNKNOWN` under `UNDER` labels.
4. **Commitment memory changes a later choice, and the two arms are one code path.** On F6, `J1` holds `X`
   while `J0` re-selects `Y` from identical inputs; and `J1` run with degenerate constants reproduces the
   `J0` trace exactly.

Three implementation or tooling defects were found by these checks and are recorded in `DEVIATIONS_EN.md`:
a non-reproducible floating-point boundary in the switch rule (D-01), a dependency scanner that matched
prose (D-02), and a comparator that reported two numerically identical values as different (D-03).

## 3. Is the proposed technical difference still defensible?

**Partly, and considerably less than it was before this task.**

The bounded gap search located three method families absent from the inherited 46-record corpus, each of
which dissolves a component of the proposed contribution:

- **Arrival-time coordination among several pursuers is prior art.** Cooperative salvo guidance coordinates
  time-to-go across interceptors for simultaneous interception. Status `KNOWN`.
- **Nonconvex safe/arrival interval sets with agent geometry are prior art.** Continuous-time multi-agent
  pathfinding represents each vertex and edge as alternating safe and unsafe intervals, with swept bodies.
  Status `KNOWN`.
- **Learned commitment and termination of temporally extended decisions in multi-agent pursuit is prior
  art.** Dynamic-termination hierarchical MARL learns when to terminate options and is evaluated on pursuit
  tasks. Status `KNOWN`. **Hypothesis H2's mechanism is therefore not novel** and H2 is restated as a
  characterization question.

What survives is the **conjunction**, not any component: nonconvex arrival sets conditional on a reactive
evader's declared branches, a compatibility predicate over the *complete* candidate combination rather
than pairwise, a learned selector that also decides persistence, and an endpoint that separates physical
capture from protocol-supported assisted capture with `UNKNOWN` preserved. The defensible description of
the contribution is **an implementable joint-opportunity representation for lane-constrained vehicle
interception, plus an empirical characterization of when learning over it helps, fails or costs too much** —
not a new temporal representation, not a new commitment mechanism, not a new attribution theory.

This narrowing was recorded prospectively, in W0, before any experiment could be run.

## 4. What evidence is missing

**For novelty.** T-CARE could not be resolved to a primary record. The sequential pursuit-planning record
named in master plan §7 was not located. Grasper, DualCL, DACOOP and PGTS have not been read at full-method
depth. No citation chasing was performed on the three newly verified records. The dynamic-termination
record was verified from its abstract verbatim, not its method sections. No conventional temporal planner
has been selected. Until these exist, **no claim may carry status `DOCUMENTED_TECHNICAL_DIFFERENCE`.**

**For everything downstream.** Nothing here bears on physical feasibility, runtime feasibility, learned
acquisition, benefit, transfer, or doctoral sufficiency. Specifically missing: the seven operational
contact thresholds (all `UNRESOLVED`, D06); the dynamics, observation and action contract (D07); the
dependency lock (D16); an arrival model validated on an independently selected diagnostic set; safety
evidence discharging obligation O22; and two complete offline constructions, of which the historical
programme achieved **zero of two**.

**The sharpest risk is already measured.** The historical O28 audit recorded `382` `UNKNOWN` predicted lane
exits containing **all** `352` observed lane changes, and concluded
`MODEL_INADEQUATE_FOR_COUNTERFACTUAL_INTERCEPTION` because free-flow estimates are lower bounds with no
attainable upper bound under interaction. Under Rule A, arrival sets derived from such a model are
`OVER`-approximations and **can never yield `SUPPORTED`**. The representation implemented here is therefore
correct but, on the only model this programme has ever measured, would return `UNKNOWN` for every
opportunity. W2–W4 must produce an `UNDER`-approximating arrival model or the method cannot certify an
opportunity at all.

## 5. Gate status

| Gate | Verdict | Basis |
|---|---|---|
| W1 analytical correctness | **SUPPORTED** | 14/14 frozen cases PASS; 58 unit tests pass; four cross-check properties hold |
| W0 novelty | **NOT SUPPORTED** (`POTENTIAL_DIFFERENCE`) | Three components shown to be prior art; required comparison families unread |
| Physical feasibility | **NOT ASSESSED** | No simulator, no geometry, no contract |
| Protocol-supported assistance | **NOT ASSESSED** | Finite accounting only; no replay, no coupling verification |
| Learned acquisition, benefit, transfer | **NOT ASSESSED** | No learner exists |
| O22, O27, O28 | **UNCHANGED** | Nothing here discharges them |

A PASS here establishes **analytical correctness only** — the first of the eight claim classes, and the
weakest. Master plan §10 states that passing W4 establishes feasibility only under the declared model;
W1 is weaker still, establishing correctness only under the declared *abstraction*. In particular, nothing
here shows that the joint/pairwise discrepancy demonstrated on F1 ever occurs on a realised urban state.

## 6. Next permitted task and its dependencies

**Next permitted: W2 — contracts, dependency lock and admission tests.** Its dependencies are satisfied:
W2 requires the method specification (delivered) and the finite fixtures (delivered), and does not require
a positive novelty verdict.

W2 must produce: `contracts/TASK_CONTRACT_EN.md` and its JSON schemas; `REWARD_CONTRACT_EN.md`;
`ASSISTANCE_PROTOCOL_EN.md`; `SPLIT_PROTOCOL_EN.md`; `configs/domain_v1.json`; `pyproject.toml` with
`uv.lock` and `THIRD_PARTY_NOTICES.md`; and admission tests that reject missing or invalid critical fields.
It must resolve D06 (the seven contact parameters, with physical rationale and units), D07 and D16.

**Blocked, and not unlocked by this result:**

- W4 offline constructions — require D06, D07, the arrival-model validation and the resolution of O28.
- W5 native work — requires the W4 gate, O22 safety evidence, and reconciliation of the exhausted
  capability-intervention allowance under D04.
- W6 learning — requires the native feasibility gate and reconciliation of the exhausted learning-intervention
  allowance under D04.
- Any TEST access — the split remains closed.

**Work that may proceed in parallel with W2, because it does not depend on the unresolved novelty claim:**
resolving T-CARE and the sequential pursuit-planning record to primary citations; upgrading the
dynamic-termination record to method-section depth; selecting the conventional temporal planner under D11
and the closest learned baseline under D05.

## 7. What this decision explicitly does not authorize

No SUMO episode. No optimizer run. No checkpoint load. No TEST access. No unattended campaign, heartbeat or
automatic retry. No reset of any inherited counter. No weakening of the capture predicate or of the safety
conditions. No claim of feasibility, learning, benefit, transfer, novelty, doctoral sufficiency or journal
readiness.

If the pending literature reads later show that the conjunction is already implemented elsewhere, the
required response is to attribute it, implement it as a baseline, and decide whether a substantial
empirical question remains — not to redefine the question to preserve a claim.
