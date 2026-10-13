# Protocol: citation chasing on B03, B04 and B06

Experiment ID: `20260921_w00_novelty_closure_r02`. Created: 21 September 2026. Stage: **W0 revision**.
Continues `…_r01`, which closed D11 and left four families open.
**Acceptance rule frozen before any query was executed.**

## 1. Why this specific item, and why now

`r01` named citation chasing as the cheapest remaining family: it needs no institutional access, unlike the
two blocked on paywalls, and unlike T-CARE it does not depend on recovering a citation from outside the
project.

It is also **the check most likely to refute the claim**. The three method families this project concedes
as prior art are:

- **B03** — cooperative salvo guidance: arrival-time coordination among pursuers;
- **B04** — continuous-time multi-agent pathfinding: nonconvex safe intervals with agent geometry;
- **B06** — dynamic-termination hierarchical MARL: learned commitment in pursuit.

The composite claim is precisely the **conjunction** of what these separately establish. A paper that
combined them would cite them, so their forward citations are where a refutation would live if one exists.
Looking there first is the honest ordering: it is the search most able to end the project's claim, not the
one most likely to confirm it.

## 2. The discriminating question, unchanged

> Does any prior method perform **joint, non-pairwise compatibility over a complete candidate combination**,
> **and** learn to **select and maintain** among the results, **against a reactive evader**, in a
> **lane-constrained** domain with **vehicle bodies**?

Unchanged from `r01` verbatim. Narrowing it to make a source non-refuting is prohibited.

## 3. Acceptance rule — fixed before searching

| Outcome | Condition |
|---|---|
| **`REFUTED`** | a citing work implements the conjunction |
| **`FAMILY_CLOSED`** | forward citations of all three records examined at title-and-abstract level, none implementing the conjunction |
| **`FAMILY_PARTIAL`** | citations examined for some records only |
| **`FAMILY_OPEN`** | no usable citation data obtained |

**Closing this family does not upgrade the composite claim.** Three other families remain open, and the
`r01` rule requires all five. Even a clean sweep here leaves the status at `POTENTIAL_DIFFERENCE`.

**Reading depth is title-and-abstract for screening.** Any candidate that appears to implement the
conjunction is promoted to method level before being treated as a refutation — a refutation asserted from
an abstract would be as unsound as a novelty claim asserted from one.

## 4. Declared limits

Forward-citation coverage depends on what the available indexes return, which is neither complete nor
stable. A citing work that exists but is not indexed will not be found. **This family closing means "the
citations reachable here were screened", not "no citing work does this".**

## 5. Resource limits

Web search and primary-record retrieval only. **0 SUMO process starts, 0 episodes, 0 optimizer updates,
0 checkpoint loads, 0 TEST accesses.** No stage budget consumed.

## 6. Outputs

The standard package set, plus updates to `search_log.jsonl`, `claim_evidence_matrix.csv` and
`sources.bib` where records are added.
