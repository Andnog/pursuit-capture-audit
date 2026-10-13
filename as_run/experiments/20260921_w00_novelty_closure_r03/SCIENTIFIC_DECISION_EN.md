# Scientific decision — citation chasing with Scopus access

Experiment: `20260921_w00_novelty_closure_r03`. Date: 21 September 2026.

**Decision: `FAMILY_PARTIAL; NO REFUTATION FOUND; THREE NEW CLOSE RECORDS BLOCK H2 AND C04 DISTINCTNESS.`**

---

## 1. Access obtained, and what it changed

The Research lead supplied **Scopus via the Universidad Panamericana proxy**. The session was already
authenticated; no credentials were entered by the agent.

`r02` recorded the citation-chasing family `FAMILY_OPEN` because no citation index was reachable and a
topic-proximity search could not substitute for one. **That verdict was correct when it was made.** It is
superseded here, not retracted — the instrument arrived, not a better reading of the old evidence.

## 2. What the citation chase found

**B06 — dynamic-termination hierarchical MARL — appears twice in Scopus**: the AAMAS 2019 proceedings
version (5 citations) and the PRICAI 2019 LNCS version (8 citations, open access).

All **8** forward citations of the PRICAI version were screened. Their domains: multi-UAV cooperative
search, asynchronous macro-actions under partial observability, option-based asynchronous policy gradient,
aerial search with explicit coordination modelling, stochastic resource collection, asynchronous
actor-critic, a textbook, and one unrelated architectural-design paper.

**None implements the conjunction.** None represents interval-valued arrival sets, and none performs joint
non-pairwise compatibility over a candidate combination.

This is the first time the project has screened *citing* works rather than topically similar ones, and it
is the check that was chosen precisely because it was most likely to refute. It did not.

## 3. A structural finding that narrows where a refutation could live

Query Q12 — learned interception under temporal constraints — returned **8 documents, all of them
aerospace, missile-guidance or maritime**: diving-manoeuvre guidance, multi-UAV cooperative control,
terminal-time-constrained interception guidance, multi-aircraft cooperative interception, USV cooperative
defence, region protection, kill-vehicle modulator tuning, missile head-on interception.

**Learned interception under temporal constraints is a guidance literature.** It coordinates *scalar*
times-to-go in free space. It does not represent interval-valued arrival sets on a road network, and it has
no joint compatibility predicate over a candidate combination.

That reinforces the B03 finding from an independent direction, and it sharpens the map: if a refutation
exists, it is unlikely to be in the guidance literature. It would be in learned multi-vehicle pursuit on
road networks — which is where the next finding sits.

## 4. Three new close records, and they block two claims

Query Q14 — the tight domain query — returned **19** documents, a precise set. Three are genuinely close
and **none was previously in the corpus**:

| Id | Record | Why it is close |
|---|---|---|
| **E01** | *Brain-Inspired Hierarchical **Memory** Distributional SAC for Cooperative Multi-Autonomous **Vehicle** Pursuit* (IEEE IoT J, 2026) | hierarchical **memory** in cooperative multi-**vehicle** pursuit — directly adjacent to H2's persistence mechanism |
| **E02** | *GSTAM: Spatial-Temporal Mamba for Cooperative Multi-Vehicle Pursuit* (2026, open access) | spatial-temporal representation for the same task |
| **E03** | *ATT-D3RQN: Attention-Based Deep RL for **Urban** Pursuit-Evasion Games* (2025) | explicitly urban pursuit-evasion with learned attention |

All three are at `TITLE_AND_METADATA` depth. **They are not treated as refutations** — a refutation
asserted from a title would be as unsound as a novelty claim asserted from one.

**But E01 is now a blocker.** Alongside B06, it blocks any statement *distinguishing* this project's
commitment mechanism from prior work: B06 established learned termination in *abstract* pursuit, and E01
appears to place hierarchical memory in *vehicle* pursuit. If it does what its title suggests, H2's
remaining distinctness narrows again.

## 5. Where the claim stands

**Unchanged at `POTENTIAL_DIFFERENCE`**, and the rule is why: closing requires all five families, and
citation chasing is `FAMILY_PARTIAL` — B06 screened, B03 and B04 not.

Matrix: 31 rows — 11 `KNOWN`, 12 `POTENTIAL_DIFFERENCE`, 8 `PENDING`, **0**
`DOCUMENTED_TECHNICAL_DIFFERENCE`, **0** `EMPIRICALLY_VALIDATED`.

**The trend named in A-20 continues.** No component was conceded in this pass, but three records appeared
that could concede one on reading. The judgement A-20 anticipated — whether the conjunction is a
contribution or an application — is closer, not further.

## 6. Next permitted task

**W4** remains the next stage. Its decision blockers are cleared; implementation work remains.

**Novelty work now reachable rather than blocked**, in priority order:

1. **Read E01 at method level.** It blocks an H2 distinctness claim and is the single most consequential
   unread record.
2. **Read E02 and E03.** E02 is open access.
3. **Forward citations of B03 and B04**, plus the 5 AAMAS citations of B06.
4. **The remaining families** — T-CARE, the sequential pursuit-planning record, the learned-pursuit
   full-method reads, D05. All now reachable through the same access.

## 7. What this decision does not authorize

No SUMO episode, optimizer run, checkpoint load or TEST access. No upgrade of any claim to
`DOCUMENTED_TECHNICAL_DIFFERENCE`. No treatment of E01–E03 as refutations on title evidence, and no
statement distinguishing this project's commitment mechanism from E01 until it is read.
