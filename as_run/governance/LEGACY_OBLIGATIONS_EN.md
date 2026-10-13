# Legacy obligations register

Stage: B0. Date: 20 September 2026. Status: **obligations identified and scoped; none discharged.**

## 0. Purpose, source and reading discipline

The instruction to rebuild the research implementation from scratch changes *where code is written*. It
does not erase evidence, reset counters, or discharge obligations inherited from the historical
programme. This register resolves each inherited obligation into: its source, its exact recorded
condition, its scope, its present disposition in this project, and what would count as discharging it.

**Single obligation source.** All obligation text below is read from:

- `/Users/andrei/Documents/PHD/Union/urban_dynamic_containment/docs/HANDOFF_TRAINING_20260910.md`
  (4070 lines, 114 numbered sections; sha256 recorded in [`SOURCE_PROVENANCE.json`](SOURCE_PROVENANCE.json) as `HIST10`).

The complete document was located and its obligation-bearing sections (§81–§114) were read, not only the
sections cited in the master plan. Line numbers below refer to that file.

**Two runtime roots are not equivalent.** `/Users/andrei/Documents/PHD/Union/urban_dynamic_containment`
(`RUNTIME_HOME`, HEAD `6f526c3a`, 133 working-tree entries, 33 docs, 111 tests) and
`/Volumes/SSD Mac/PHD/Union/urban_dynamic_containment` (`RUNTIME_SSD`, HEAD `857d9837`, 12 working-tree
entries, 1 doc, 18 tests) are **distinct divergent trees**, not copies or symlinks. `RUNTIME_SSD` does not
contain the handoff at all. `RUNTIME_HOME` is therefore the canonical source of obligation text. Neither
root is imported, executed, or placed on this project's import path.

**Notation.** The historical handoff is written in a heavily compressed style in which digits and words
are frequently run together (for example `>=14/20acrossfourmaps`). Quotations below preserve the original
characters exactly and add an English expansion where the compression could be misread.

**Preservation.** No historical file, failure record, sealed package, dirty file or untracked file has
been modified, deleted or reset by this project. The 133 working-tree entries in `RUNTIME_HOME` and the
12 in `RUNTIME_SSD` are preserved as found.

## 1. Obligation summary

| ID | Obligation | Recorded historical status | Disposition in this project | Blocks |
|---|---|---|---|---|
| O22 | Directional/time safety proof, second original safety regression, capture preservation | **OPEN** — two measured safety gaps; "bounded implementation incomplete" | Inherited as a *safety-evidence requirement*, not as legacy code. Must be re-established natively under the new contract. | W4 onward (native) |
| O26 | Local viability diagnostic on four Condesa TRAINING cases | **COMPLETE, negative** — `NO_GO_CURRENT_CONTROLLER`, 0/4 and 0/4 | Closed as an experiment. Its four case definitions are an *immutable scenario asset* usable only with provenance and a compatibility check. | Reuse of its success labels (prohibited) |
| O27 | Two complete offline assisted-capture constructions | **UNMET** — 0 of required 2 | Structurally identical to the master plan's W4 requirement. Inherited as an unmet prerequisite. | W4, W5 |
| O28 | Interception model-readiness gate | **STOPPED** — `MODEL_INADEQUATE_FOR_COUNTERFACTUAL_INTERCEPTION` | Inherited as a model-validation requirement before any counterfactual interception search. | W4 model validation |
| 14/20 | Four-map progression rule | **OPEN, never passed** | Scope recovered (see §5). Applies to *stage progression after acquisition*, not to W0–W1 and not to first optimization. | W6→W7 progression |
| CAP | Integrated capability intervention allowance | **1 of 1 consumed** (by O26) | Exhausted under the historical programme. Any further native capability trial needs an explicit recorded amendment. | W5 native work |
| LRN | Registered learning intervention allowance | **at least 2 of 2 consumed**; a third registration is unreconciled | Treated as exhausted. See §7 for the unresolved third entry. | W6 training |
| TEST | Final city TEST set | **SEALED, never opened** | Remains closed. Exposure log required before any TEST access. | W8 |

## 2. O22 — directional and time safety proof

**Source.** §104 (line 3904) "ACTIVE O22 — two measured safety gaps; bounded implementation incomplete";
§105 (line 3917); §111 (line 3994); restated as outstanding in §112 (line 4034) and §113 (line 4053).

**Recorded conditions, verbatim fragments with expansion.**

- §104: `Condesa803001movingC2: p1/preybodyoverlap278.0s,guardinfeasible278.3s.` — on Condesa scenario
  803001, a pursuer/prey **body overlap occurred at 278.0 s** and the local guard reported infeasibility at
  278.3 s.
- §104: `Roma803002C1: nativecollisionp3/p5at21.8s withpositivebodygap1.959m` — a **native collision
  between pursuers p3 and p5 at 21.8 s** despite a positive reported body gap, traced to station
  separation arithmetic (`6.459929−length5−MinGap2.5`). The handoff records `nativecollisionremainsFAIL`.
- §111 (line 3994): `Broader O22 directional/time proofs, second original safety regression and
  capture-preservation remain pending.`
- §113 (line 4053) and §114 (line 4068) both restate O22 as outstanding at the end of the historical record.

**Scope.** Three distinct sub-obligations, all open: (a) a directional/time safety proof covering close
parallel encounters and actor segment exit; (b) a **second** original safety regression; (c) capture
preservation under the repaired guard.

**Disposition here.** O22 is inherited as a *class of safety evidence that must exist before native
execution*, not as legacy source to port. The two measured gaps are concrete falsifying cases: the new
safety admission module must be able to state a verdict on close parallel encounters and on
segment-exit geometry, and the new contract's collision test must not depend on the station-separation
arithmetic that failed at 21.8 s. Satisfying O22 with new evidence is permitted by master plan §3;
carrying over the old identifier as if satisfied is not.

**Discharge condition.** Contract-level definitions plus new safety-admission tests and, before any
native campaign, native regression evidence under the new capture contract. Not dischargeable in W0–W1.

## 3. O26 — local viability diagnostic

**Source.** §111 (prospective scope, line 3994) and §112 (result, lines 4001–4037). Evidence package
`/Volumes/SSD Mac/PHD/Union/urban_dynamic_containment_evidence/v2_20260907/recovery_20260919_26`
(36 entries, `checksums.json` present).

**Recorded conditions and result.**

- Design: four unchanged **moving, initially open Condesa TRAINING cases**; integrated and reactive arms
  over a shared public interface; all runtime guards active; no optimizer or checkpoint.
- Execution: 8 native evaluations, each 300 simulated seconds / 3000 frames, all physically accepted.
- Result: **integrated 0/4 captures, reactive 0/4**. On each case all 3000 recorded frames were
  *exactly identical between arms*. Full-team return −1.000 and coverage 1.0 in every case.
- Decision: `NO_GO_CURRENT_CONTROLLER`.
- First measured defect: `6548stop/stationary-lateral candidate occurrences over1200completed decision
  intervals`, of which **none** passed the selector's joint forward-location 5.3–40 m and heading-agreement
  criterion; all 1200 recorded selection intentions were navigation.
- Ending label: `INDETERMINATE` with `NO_CAPTURE` — explicitly **not** rewritten as escape or impossibility.

**Scope limit recorded in the source.** §112: `These are four TRAINING cases on one map, not unseen-map
generalization, a learned policy comparison or a population-level efficacy estimate.`

**Disposition here.** The experiment is closed and is not repeated. Two separable things survive:

1. **The four case definitions** (original P199 Condesa indices 0..3, seeds 520000..520003, unchanged spawn
   lanes and stations, all six vehicles at 3 m/s, directed prey separations 148.84–292.38 m, per §110
   line 3938, frozen as `reference_cases.json` sha256 `a4e891465fee5a7e5bda80f00a8f233a502047c68535c3c05a0fdebadd80c5bd`).
   These are candidate **immutable scenario assets** for the master plan's W5 legacy comparison. Adoption
   requires a provenance entry, a hash check and a compatibility check against the new contract.
2. **The measured defect** — that a heuristic selector generated thousands of stationary-lateral candidates
   and never scored any as jointly usable. This is the empirical motivation for the present research
   question and is usable as diagnostic context.

**Prohibited.** Reusing O26 success labels; treating its 0/4 as evidence about the new contract; repeating
it unchanged; expanding PPO or recollecting near-cage teachers on the basis of it (§112 explicit).

## 4. O27 and O28 — offline construction and model readiness

**O27.** §113 (lines 4039–4056). Evidence: `recovery_20260919_27` (58 entries). Decision
`NO_GO_NATIVE_OR_RL_CONSTRUCTIVE_GATE_UNMET`, recorded as `Complete witnesses0/required2` — **zero of the
two required complete constructions**. Recorded scale: 491 analytic barrier templates, 57,042 macro
expansions across original and corrected passes, under the 100,000-per-case cap, about 10.38 CPU seconds.
Broader reduced graph admitted static cooperative cuts in 4/4 cases; the unique-navigation abstraction in
only 1/4 (case 001); **no candidate survived the ETA-proxy screen**. The handoff states explicitly that the
complete temporal solver is `NOT implemented`.

This is structurally the same requirement as master plan W4 ("two complete offline assisted-capture
constructions"). It is inherited as **unmet**, with its 100,000-expansions-per-case search cap and the
warning that a static cut is not execution feasibility.

**O28.** §114 (lines 4058–4070). Evidence: `recovery_20260919_28` (35 entries). Decision
`MODEL_INADEQUATE_FOR_COUNTERFACTUAL_INTERCEPTION`. Recorded measurements: 6000 pursuer action/mask checks
passed; 5980 complete intervals with 20 incomplete final intervals retained; 5598 isolated point
hypotheses; **382 UNKNOWN predicted lane exits, containing all 352 observed lane changes**; 2062
moving-start hypotheses with position error p95 ≈ 1.227 m (max 2.409 m) and speed error p95 ≈ 2.329 m/s
(max 4.434 m/s).

Two findings bind directly on the present method specification:

- `Available free-flow lane estimates are lower bounds; isolated O27 profiles provide no upper interacting-pursuer arrival bound.`
- `Existing encoding lacks a shared corridor graph/arrival interface. No complete joint transition/mask predictor is established.`

**Disposition.** O28 is inherited as a **model-validation prerequisite**: before W4 counterfactual search,
the new arrival model must be validated on an independently selected diagnostic set, must declare its
approximation direction, and must represent lane-change and other unmodelled behavior as UNKNOWN rather
than as a fabricated bound. Master plan §6 already requires this; O28 is the empirical reason it is
required. The 382/352 UNKNOWN finding is the reason `UNKNOWN` is a first-class state in the W1 fixtures.

## 5. The four-map 14/20 rule — exact scope

**Sources.** §81 line 3580 (case structure), §81 line 3582, §82 line 3598, §82 line 3600, §87 line 3664,
§88 line 3677, §90 line 3772, §91 line 3783, §94 line 3790, and restated as open in §112 line 4034,
§113 line 4053 and §114 line 4068.

**The rule as recorded.**

- §88 line 3677: `Requirebothseedcaptures/favorableinitial and>=14/20acrossfourmapswithoutphysicalfailuresforprogression.`
  Expansion: progression requires **both training seeds to produce captures**, a **favorable comparison
  against the initial policy**, and **at least 14 of 20** reserved cases **across four maps**, **with no
  physical failure**.
- §82 line 3600: `Both-seed valid captures plus favorable initial comparison gate amplification;14/20 across four maps without physical failure gates stage progression.`
  Expansion: the seed/initial condition gates *amplification*; the 14/20 condition gates *stage progression*.
  They are two conditions, not one.
- The denominator: §81 line 3580 records `20 reserved TRAINING curriculum checks (2/5 per map)`; §90 line
  3772 records `Twenty reserved TRAINING-map curriculum scenarios fixed before weights`; §88 line 3677
  frames them as `20reserved TRAINING cases x9arms`. The four maps appear in the §81 menu audit as
  **Condesa, Berlin, Boston, Roma**.

**What the rule is not** — recorded explicitly in the source:

- §81 line 3582: `Do not use old mutable supervisors, substitute seeds, omit failures, require14/20 before first optimization or demand completed C2–C4.`
  **The rule must not be required before first optimization.**
- §94 line 3790: `Two diagnosticcasescannotfulfillfour-map14/20gateorgeneralization.` A small diagnostic
  subset cannot satisfy it.
- It is nowhere described as a significance test, and it is not evidence of generalization: the reserved
  cases are TRAINING-map cases, so passing it would establish progression readiness on **seen** maps only.

**Recorded status.** Never passed. Stated as open or closed at every subsequent checkpoint, including the
final three sections of the handoff.

**Applicable scope in this project.** The historical rule is a *progression* rule between an acquisition
pilot and a broader campaign. Its structural analogue here is the boundary between W6 (acquisition pilot)
and W7 (confirmatory mechanism study). It does **not** apply to B0, W0, W1, W2, W3, and it must not be
imposed as a precondition for first optimization.

**UNRESOLVED items.** (a) The exact per-map allocation of the 20 cases: the compressed source string
`(2/5 per map)` admits more than one reading and the individual reserved case identifiers were not
enumerated in the handoff. (b) Whether "without physical failure" counts failures across all 20 cases or
only across the 14 counted successes. (c) Whether the new contract's cases could be placed in
correspondence with the historical 20 at all. These must be resolved, or the rule explicitly amended,
before it is applied — not at the moment it is invoked.

**Prohibited.** A contact-based reinterpretation of the rule without a recorded amendment; and under any
reading, passing it never counts as passing the historical caging endpoint (master plan §3).

## 6. Protected TEST data and previous exposure

**Recorded status.** The final city TEST set is described as sealed, closed or unopened at every
checkpoint where it is mentioned, including §110 line 3942 (`finalcityTESTsealed`), §112 line 4034
(`Four-map14/20progression and finalcityTEST stay closed`), §113 line 4053 and §114 line 4068. No handoff
section records a TEST opening.

**Exposure that did occur.** The following were examined and are therefore **exposed development
evidence**, not fresh holdouts:

- The four Condesa O26/O27/O28 cases (indices 0..3, seeds 520000..520003) — examined in three successive
  evidence packages.
- The 20 reserved TRAINING curriculum cases — §88 line 3700 records that 180 paired zero-update jobs were
  frozen and launched over these cases; their outcomes were therefore opened.
- DEVELOPMENT episodes — repeatedly stated as never being training data, but used for method decisions.

**Disposition here.** This project defines its own splits under master plan §12 and decision D15. Because
the historical map set (Condesa, Berlin, Boston, Roma) is exposed, any new city used for a transfer claim
must be separated at the **city** level from all four, and overlapping OSM extracts must be checked.
TEST remains closed until method, checkpoint-selection rule, metrics, inference procedure and resource
limits are frozen. **UNRESOLVED:** the identity and provenance of the sealed historical city TEST set is
not recorded in the handoff; it must be located before any claim that this project's TEST is disjoint
from it.

## 7. Capability and learning intervention budgets

**Integrated capability interventions — cap 1, consumed 1.**

- §110 line 3942: `Maxoneintegratedcapabilityintervention before scientificdecision;maxtwolearninginterventions beforedecision.`
- §112 line 4030 (O26 decision): `This completes the single integrated-capability trial before a new scientific decision.`
- §113 (O27): `No second native capability trial consumed.`

The single allowance was consumed by O26. §112 states: `A new native intervention requires its own
prospective contract, distinct declared evaluation cases/budget and scientific justification; it is not an
automatic repeat or an uncounted extension of this trial.`

**Registered learning interventions — cap 2, at least 2 consumed, third entry unreconciled.**

- Intervention 1 (**safety**): preregistered §81 line 3611 (`Safety intervention1 preregistered:
  opt-in straight-cross-lane-body-v1 ...`); recorded complete at §87 line 3664 (`First safety intervention complete`).
- Intervention 2 (**acquisition**): preregistered §87 line 3664 (`Acquisition intervention2 now
  preregistered: freshMLP780001/780002, BC200epochs3e-4/batch64/clip.5 ...`); launched §88 line 3667;
  training completed and reserved evaluation started (§88 addenda); then
  **`Latest state: PAUSED AFTER USER INTERRUPTION`** (line 3703). The paired evaluation was recorded as
  `31complete/2interrupted/147unlaunched` at §89 line 3715.
- Repeated constraint: §87 line 3664 and §88 lines 3677, 3693 —
  `No thirdautomaticlearninginterventionifthisonefails` / `after a negative second outcome`.

**UNRESOLVED — the third registration.** §103 line 3893 records that, for O21,
`AMENDMENT_01.md froze the smallest new learning intervention before implementation/outcomes` (a
training-only directed-prey proximity potential `0.1*mean(100/(100+d))`, runtime v2.58). The same section
(line 3899) simultaneously restates `Max2registered learning interventions before scientific decision`.
The handoff **does not state** whether this O21 amendment consumed the second allowance, re-used an
existing one, or was registered outside the numbered series. This project therefore treats the learning
allowance as **exhausted** and records the ambiguity rather than resolving it favorably. Nothing here
grants a new allowance.

**Disposition.** Both inherited allowances are treated as exhausted. Per master plan §10, the new project
must record an explicit amendment before any budget-consuming launch, and may not silently reset a
counter by changing directories. Whether the historical caps bind a fresh implementation at all, or
whether the new programme's own W4/W5/W6 caps (2 CPU hours; 15 episodes; 144 episodes) supersede them, is
**UNRESOLVED** and is decision D04's subject. It must be settled before W5 — not at launch time.

## 8. What B0 and W0–W1 may do under this register

Permitted now, because none of the above obligations gates it: documentation; provenance; the novelty and
gap analysis; the mathematical method specification; independently derived finite fixtures; and pure-Python
implementation of the finite examples with no simulator, optimizer, checkpoint or TEST access.

Blocked until the corresponding obligation is discharged or explicitly amended: any SUMO episode (O22);
any counterfactual interception search presented as feasibility (O27, O28); any native capability trial
(CAP); any optimizer run (LRN, and the native feasibility gate); any TEST access (TEST).

## 9. Register maintenance

Each obligation is discharged only by a new evidence package containing a frozen protocol, executed
results including failures, and a scientific decision — or by an explicit amendment in
`governance/AMENDMENTS_EN.md` recording what changes, why, which historical results become incompatible
and what new evidence is required. An old identifier appearing in a new document is not proof of
satisfaction.
