# Protocol: citation chasing with Scopus access (W0 revision r03)

Experiment ID: `20260921_w00_novelty_closure_r03`. Created: 21 September 2026. Stage: **W0 revision**.
Continues `…_r02`, which recorded the citation-chasing family `FAMILY_OPEN` because no citation index was
reachable.

## 1. What changed

The Research lead supplied institutional access: **Scopus via the Universidad Panamericana proxy**
(`scopus.up.elogim.com`), reached from `biblioteca.up.edu.mx`. The session was **already authenticated**;
no credentials were entered by the agent.

`r02`'s `FAMILY_OPEN` verdict was correct when it was recorded — the index genuinely was unreachable and a
topic-proximity search could not substitute. It is **superseded here, not retracted.**

## 2. The discriminating question, unchanged

> Does any prior method perform **joint, non-pairwise compatibility over a complete candidate combination**,
> **and** learn to **select and maintain** among the results, **against a reactive evader**, in a
> **lane-constrained** domain with **vehicle bodies**?

Verbatim from `r01`. Narrowing it to make a source non-refuting remains prohibited.

## 3. Acceptance rule — fixed before searching

| Outcome | Condition |
|---|---|
| **`REFUTED`** | a citing work implements the conjunction |
| **`FAMILY_CLOSED`** | forward citations of **all three** records screened |
| **`FAMILY_PARTIAL`** | citations screened for some records only |
| **`FAMILY_OPEN`** | no usable citation data obtained |

**Screening is at title-and-abstract depth.** Any candidate that appears to implement the conjunction is
promoted to method level before being treated as a refutation: a refutation asserted from an abstract would
be as unsound as a novelty claim asserted from one.

**Closing this family does not upgrade the composite claim.** The `r01` rule requires all five families.

## 4. Declared limits

Scopus indexes what it indexes. A citing work outside its coverage — an arXiv preprint with no indexed
version, for instance — will not appear. **"Screened" means the citations Scopus returns were screened.**

## 5. Resource limits

Literature search only. **0 SUMO process starts, 0 episodes, 0 optimizer updates, 0 checkpoint loads,
0 TEST accesses.** No stage budget consumed.
