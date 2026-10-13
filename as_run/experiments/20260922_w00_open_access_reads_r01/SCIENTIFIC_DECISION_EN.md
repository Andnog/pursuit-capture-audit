# Scientific decision — open-access reads

## Verdict

`THREE_CONCESSIONS_NO_REFUTATION_D05_RESOLVED`. The composite claim C12 stays `POTENTIAL_DIFFERENCE`.
**The label did not move. The content behind it is materially smaller.** Four components were conceded
before this package; six are conceded after it.

## The access record was wrong

Four families were recorded on 21 September as blocked on access. **Three were not blocked.**

| Record | Recorded 21 Sep | Actual |
|---|---|---|
| DACOOP-A | "needs institutional full-text access" | **arXiv `2310.15699v2`, open**, with released code |
| GSTAM | not attempted | **ACM open access**; no subscription needed or used |
| ATT-D3RQN | "needs IEEE" | IEEE, reached with the proxy **already available** |

A direct `curl` on the ACM article returned HTTP 403 — **bot protection, not a paywall**. The browser reached
the same page with no credentials. A 403 was nearly recorded as an access blocker for an open-access article.

**Rule adopted:** before recording an access blocker, attempt the open route. Minutes to check; the cost of
not checking was a day of reasoning against a corpus that conceded more than it was recorded as conceding.

## D05 is resolved, negatively

DACOOP-A's learner selects only the **gains `(λ, η)` of a designed artificial potential field**, from 24
discrete pairs, every timestep. Three structural mismatches with this project's **frozen** domain:

1. **Capture is `d_E,i < d_c` for any one pursuer**, and the episode ends there. That is precisely the
   predicate D06 rejects — contact alone is not capture, coordination is required.
2. **Cooperation is encirclement** — the formation mechanism the Research lead explicitly ruled out.
3. **The evader is faster than the pursuers.** D08 froze an evader that never is.

To score DACOOP-A against this endpoint you must change its success criterion. **Changing a baseline's
success criterion to match your own manufactures the comparison.**

**Recommendation, reserved to the Research lead:** retain DACOOP-A as the *cited structural comparison* for
the learned-control family. The graph-and-time-native baseline is **CCBS** (D11, complete and optimal).

## GSTAM: the largest concession in the corpus

Recorded first, before anything that survives it.

**The setting is conceded.** Urban multi-vehicle pursuit with learned spatiotemporal reasoning is prior art.
So is the **motivation**: E03 states in print that urban roads *"impose strict motion constraints, confining
agents to predefined road networks"*, causing *"significant incompatibility between existing algorithms and
urban traffic."* That observation may not be presented as this project's own.

**C04 is conceded at its core.** GSTAM performs **implicit, time-varying, learned target allocation** via a
Task-Aware Mixture of Grouped Experts with a load-balancing loss against target collapse — framed explicitly
as **dynamic ST-MR-IA** task allocation. This is **closer to C04 than Riedmiller & Withopf**, the record that
has been blocking C04 on access. *A readable source concedes more than the unreadable one would have.*

**C05 is conceded as a finding, not merely as a mechanism.** GSTAM **measures** persistence: *"persistent
spatial lock-in"*, dominance of the same target throughout an interval, reported as evidence of *"sustained
pursuit intent rather than collaborating by chance."* H2 had already conceded the mechanism to B06 and the
concept to Jennings 1993. **It must now concede the empirical claim.**

## What survives, stated narrowly

- **C04 → the filter.** GSTAM allocates over *evaders* and applies **no feasibility filter**, because a grid
  cannot make an allocation physically infeasible. What remains claimable is the filter over the combination,
  not the learning of allocation.
- **H2 → explicit versus emergent.** GSTAM's persistence is a **by-product** of expert specialisation plus a
  balance regulariser, reported as a **diagnostic**. No commitment memory, no hysteresis, no switch margin,
  no mechanism holding a commitment against a momentarily better alternative.
- **Temporality is untouched.** No record in the corpus carries arrival times, windows or intervals. GSTAM's
  Temporal Mamba encodes a sliding window of **past** observations, not any agent's **future** reachable times.

## A pattern now confirmed three times

B06: *k* agents adjacent. GSTAM: ≥ 2 pursuers within radius `D`. Both are **cardinality counts on a grid**,
where any satisfiable count is physically realizable — so counting *is* a sound team-feasibility certificate
in those domains. The lane-capacity witness shows where counting stops certifying. **Three consecutive
sources share this shape**, which strengthens the argument and narrows it at the same time: the claim is
about a domain property, not about an oversight in the literature.

## Consequence for experiment design

**The J1-versus-J0 comparison must include a GSTAM-style emergent-persistence comparator, or it tests
nothing.** Comparing an explicit commitment mechanism against no persistence at all would be comparing
against a strawman the literature has already beaten.

This is a design requirement produced by W0, recorded prospectively, before any experiment.

## What this does not establish

Nothing about whether this project's method is better than any record here. Every finding is about
**comparability and attribution**. GSTAM's and DACOOP-A's results on their own problems stand untouched.
