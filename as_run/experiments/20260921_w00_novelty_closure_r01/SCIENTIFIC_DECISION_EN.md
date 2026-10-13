# Scientific decision — W0 novelty closure

Experiment: `20260921_w00_novelty_closure_r01`. Date: 21 September 2026.

**Decision: `POTENTIAL_DIFFERENCE UNCHANGED; D11 RESOLVED; NOVELTY STILL NOT ESTABLISHED.`**

---

## 1. The headline

The composite claim stays exactly where it was. Under the rule frozen before the search,
`DOCUMENTED_TECHNICAL_DIFFERENCE` requires **all five** pending families resolved and read at method level.
**One closed. Four did not.**

That is the rule working as designed. It was written so that an unread family blocks the upgrade
*regardless of how the read ones turn out* — precisely so that a run of favourable readings could not be
converted into a novelty claim while the awkward sources stayed unopened.

**No source found in either search block implements the conjunction.** That is not evidence of absence. A
finite search never is, and three of the four open families failed for **access** reasons rather than for
lack of literature.

## 2. What closed: D11, and it closed well

**Continuous-time Conflict-Based Search (CCBS) is selected as the conventional temporal planner.**

It is **complete and optimal** — *"guarantees optimal solutions without the need to discretize time"* — it
models agent bodies, and it represents availability as safe intervals that are unions of disjoint
intervals.

Three consequences, pointing in different directions, all worth stating:

**It removes an objection in advance.** Master plan §8 forbids selecting a weak planner. An *optimal* one
settles that: a favourable W7 result cannot be dismissed as beating a poor baseline, and an unfavourable
one cannot be explained away as a tuning failure. This is the comparator that can actually hurt the claim,
which is why it is the right one.

**It strengthens claim C03 rather than refuting it.** CCBS resolves a conflict **pairwise**: *"CCBS
generates two new CT nodes, where it adds the constraint … to one node and the constraint … to the other."*
The state-of-the-art **optimal** continuous-time multi-agent planner therefore uses pairwise constraint
splitting, not a joint feasibility predicate over a candidate combination. The joint-versus-pairwise
distinction this project asserts is a real difference against the strongest available comparator — not
against a straw man. Finite case F1 already shows a pairwise-compatible, jointly-infeasible set; whether
that discrepancy matters on realised states is still the open empirical question.

**It does not refute the composite claim.** CCBS has **no adversary and no learned component**. It solves
goal-reaching, not selection and persistence against a reactive evader.

**The adaptation is substantial and must not quietly weaken it:** disk agents become 5 m × 1.8 m oriented
rectangles; free graph motion becomes lane-constrained motion under the action menu and safety interface;
goal-reaching becomes interception of a reactive evader. Optimality of the original does **not** transfer
to an adaptation of it, so competence verification on constructed solvable instances is still required.

## 3. What did not close, and why the reason matters

| Family | Status | Why |
|---|---|---|
| T-CARE | **NOT LOCATED** | Two independent queries returned nothing matching the identifier |
| Sequential pursuit-planning record | **NOT READ** | Candidate located; retrieval returned HTTP 403 |
| Full-method reads of Grasper, DualCL, DACOOP/DACOOP-A, PGTS | **NOT ACHIEVED** | DACOOP-A's PDF was an unparsable image stream |
| B06 method sections | **UPGRADE FAILED** | HTML 404; PDF extraction had already failed |
| Citation chasing on B03/B04/B06 | **NOT PERFORMED** | Not attempted in this block |

Three of these are **access failures, not absence of literature**, and the distinction is load-bearing.
"We could not read it" and "it does not exist" support entirely different conclusions, and only the first
is true here.

The B06 failure has a specific consequence carried forward: the H2 concession — that learned commitment and
termination in multi-agent pursuit is prior art — **stands**, because it rests on what that abstract states
explicitly. But any statement *distinguishing* this project's commitment mechanism from B06 **remains
blocked**, because distinguishing requires reading what the mechanism actually does.

## 4. D05 was deliberately left open

DACOOP-A resolved to IEEE RA-L 2023, learned attention over neighbours combined with a **designed**
artificial potential field, decentralized, multi-robot. **No learned baseline was selected.**

The asymmetry with D11 is deliberate. CCBS could be judged on the predicate that decides its selection —
whether it is *competent* — because completeness and optimality are stated in the method text. For D05 the
deciding predicate is **which control choices remain learned and which are supplied by designed
structure**, and for DACOOP-A that is exactly what an abstract cannot settle: it names both an attention
mechanism and a potential field without apportioning between them.

Master plan §8 requires that any adaptation state that apportionment, and warns against claiming a prior
method "lacks cooperation" merely because it contains designed structure. Selecting on abstract evidence
would be a guess presented as a decision.

## 5. Where the claim now stands

Components already `KNOWN` and not claimed: arrival-time coordination among pursuers; nonconvex safe
intervals with agent geometry; learned commitment and termination in multi-agent pursuit; KAN policies and
KAN explanations.

Surviving candidate contribution, unchanged: **the conjunction** — nonconvex arrival sets conditional on a
reactive evader's branches, joint compatibility over the *complete* candidate combination, a learned
selector that also decides persistence, and an endpoint separating physical capture from protocol-supported
assisted capture with `UNKNOWN` preserved.

Matrix after this revision: 27 rows — 8 `KNOWN`, 12 `POTENTIAL_DIFFERENCE`, 7 `PENDING`, **0**
`DOCUMENTED_TECHNICAL_DIFFERENCE`, **0** `EMPIRICALLY_VALIDATED`.

## 6. Next permitted task

Unchanged: **W4**, still blocked on D08, the D06 freeze, the unexercised TraCI surface, and the
non-existence of constructive arrival witnesses.

Novelty work that can still proceed in parallel, now enumerated with what each needs:

1. **T-CARE** — needs the original citation from whoever introduced the identifier into the master plan.
   It cannot be found by search alone.
2. **The sequential pursuit-planning record** and the **learned-pursuit full-method reads** — need
   institutional full-text access.
3. **Citation chasing on B03, B04 and B06** — needs no special access and was simply not done. This is the
   cheapest remaining item and should be next.
4. **D05** — blocked behind item 2.

## 7. What this decision does not authorize

No SUMO episode, optimizer run, checkpoint load or TEST access. No upgrade of any claim to
`DOCUMENTED_TECHNICAL_DIFFERENCE`. No treating a near-neighbour as a substitute for a named record. No
narrowing of the discriminating question to make a source non-refuting. And no implication that the absence
of a refutation is evidence of novelty — it is evidence that four families remain unread.
