# Deviations

Experiment: `20260921_w00_novelty_closure_r02`. Stage: W0 revision.

---

## D-27 — The planned method could not be executed, and a weaker one was substituted

**What happened.** The protocol specified **forward citation traversal** of records B03, B04 and B06. No
forward-citation index was reachable with the available tools: web search returns ranked topical matches,
not a citation graph. A **topic-proximity search** was run instead.

**Why it matters.** These are not the same instrument. Citation traversal enumerates works that
*demonstrably build on* a record, which is why it was chosen as the check most likely to surface a
refutation. Topic search returns whatever ranks highly for a phrase, and can miss a citing work entirely
while returning unrelated matches.

**Effect on the verdict.** The family is recorded **`FAMILY_OPEN`, not closed.** Under the frozen rule,
closing requires *"forward citations of all three records examined"*; none were obtained.

**Why it was not recorded as closed anyway.** The search returned nothing implementing the conjunction, so
recording "closed, no refutation found" would have been convenient and would have reduced the open-family
count. It would also have been exactly the substitution this protocol prohibits: a weaker instrument's
silence presented as a stronger instrument's finding.

**What would close it.** A citation index — Scopus, Web of Science, Semantic Scholar or Google Scholar.
This remains the cheapest open family in effort, but it is no longer reachable with what is available here.

---

## D-28 — A relevant record was found anyway, and it narrows a claim

**What happened.** The substituted search surfaced **DT-GAT** (Scientific Reports, 2026): hierarchical
graph-attention allocation with *"learnable edge-feature biases that embed spatial reachability and
interception urgency directly into attention computation"*, plus a Gumbel-Softmax allocation head.

**Assessment against the conjunction.** It does **not** implement it — scalar reachability features rather
than interval sets, per-edge soft assignment rather than joint feasibility over a candidate combination, no
commitment mechanism, and free-flying drones rather than lane-constrained vehicles.

**But it narrows claim C04 to `KNOWN`.** *Learned selection informed by reachability* is now prior art.
What remains distinct is interval-valued **joint** compatibility, learned **persistence**, and the
lane-constrained vehicle contract. This is the fourth component of the original claim to be conceded.

**Reading-depth caveat, recorded rather than glossed.** The publisher page requires authentication
(HTTP 303 to an identity provider). The method details come from **indexed secondary summaries, not the
primary text**, and the record is labelled `METHOD_DESCRIPTION_FROM_SECONDARY_SUMMARY` — a depth weaker
than `METHOD_LEVEL_TARGETED`. The concession is made on that basis; a *distinction* from DT-GAT would
require the primary text.

---

## Deviations that did not occur

No SUMO process start, no episode, no optimizer update, no checkpoint load, no TEST access. The
discriminating question was not narrowed to make DT-GAT non-refuting — it fails four separate predicates.
No reading depth was upgraded beyond what was read. No family was declared closed on a weaker instrument's
silence.
