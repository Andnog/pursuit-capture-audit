# Protocol: W0 novelty closure

Experiment ID: `20260921_w00_novelty_closure_r01`. Created: 21 September 2026. Stage: **W0 revision**.
**Acceptance rule frozen before any new search was executed.**

## 1. Why now

W0 closed with `SEARCH_NOT_CLOSED` and the composite claim at `POTENTIAL_DIFFERENCE`. Five families were
left pending. Every handoff since has listed resolving them as work that **may proceed in parallel**,
because it depends on none of the blockers that hold W4: not D06, not D08, not the arrival model, not the
TraCI surface.

It is also the block with the highest consequence per unit of effort. If the conjunction this project
claims is already implemented somewhere, then the arrival-model finding, the contracts and the adapter are
all in service of a contribution that does not exist, and the programme must change rather than continue.

## 2. Pending families to resolve

1. **T-CARE** — named in master plan §7; query Q01 returned no matching record.
2. **The sequential pursuit-planning record** named in master plan §7 — never located.
3. **Full-method reads** of Grasper, DualCL, DACOOP, PGTS.
4. **The conventional temporal cooperative planner** to implement as `PLAN` — decision **D11**.
5. **Citation chasing** on B03 (salvo guidance), B04 (continuous-time MAPF), B06 (dynamic termination).

Plus decision **D05**, the closest learned pursuit baseline to adapt.

## 3. The discriminating question, restated exactly

The composite claim C12 is the **conjunction**, since its components are already `KNOWN`:

> Does any prior method perform **joint, non-pairwise compatibility over a complete candidate combination**,
> **and** learn to **select and maintain** among the results, **against a reactive evader**, in a
> **lane-constrained** domain with **vehicle bodies**?

A source refutes the claim only if it does **all** of that. A source doing any part of it strengthens the
prior art without refuting the conjunction — and several already do, which is why the components are
`KNOWN`.

## 4. Acceptance rule — fixed before searching

| Outcome | Condition |
|---|---|
| **`REFUTED`** | a primary record is found that implements the conjunction in §3 |
| **`DOCUMENTED_TECHNICAL_DIFFERENCE`** | all five families resolved to primary records, read at method level, and none implements the conjunction |
| **`POTENTIAL_DIFFERENCE`** (unchanged) | one or more families remain unresolved |

**A family that cannot be resolved stays `PENDING` and blocks the upgrade.** The plan is explicit that a
finite search cannot establish absence of prior art, so the third outcome is the expected one unless every
family closes. Reporting `PENDING` is a result, not a failure.

**Prohibited:** narrowing §3 to make a source non-refuting; upgrading a reading depth not actually achieved;
declaring a family closed because a search returned nothing.

## 5. Decisions to resolve

- **D11** — the conventional temporal cooperative planner. Must be *competent*, not nominal: master plan §8
  forbids selecting a weak planner or quoting published percentages from a different capture predicate.
- **D05** — the closest learned pursuit baseline. Its adaptation must state which control choices remain
  learned and which are supplied by designed structure.

Both may be recorded as **UNRESOLVED with a shortlist and the reason** if no candidate can be read deeply
enough to judge competence. A selection made without that evidence would be a guess presented as a decision.

## 6. Resource limits

Web search and primary-record retrieval only. **0 SUMO process starts, 0 episodes, 0 optimizer updates,
0 checkpoint loads, 0 TEST accesses.** No stage budget is consumed: W0's cap was the combined W0–W1 working
day, already reconciled, and this revision is recorded on its own line.

## 7. What a result does and does not establish

**Can establish:** that the conjunction **is** implemented elsewhere, which refutes the claim; or that
named families are resolved and do not implement it, which upgrades the status; or that families remain
unresolved, which leaves it where it is.

**Cannot establish:** absence of prior art. A finite search never does, and the reading-depth labels stay
honest about what was actually read.

## 8. Outputs

The standard package set, plus an updated `research/novelty/claim_evidence_matrix.csv`,
`search_log.jsonl` and `sources.bib`.
