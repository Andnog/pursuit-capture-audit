# Deviations

Experiment: `20260921_w00_novelty_closure_r01`. Stage: W0 revision.

**The acceptance rule was frozen before any query was executed, and was not adjusted after the results
came in.** The verdict it produced is the unchanged status, which is the rule working rather than failing.

---

## D-21 — Four of five families could not be closed, and three failed for retrieval reasons

**What happened.** Only D11 closed. The others failed as follows:

| Family | Failure |
|---|---|
| T-CARE | Two independent queries returned nothing matching the identifier |
| Sequential pursuit-planning record | Candidate located, retrieval returned **HTTP 403** |
| Full-method reads | DACOOP-A's PDF returned an **unparsable image-based stream** |
| B06 method sections | HTML returned **HTTP 404**, PDF extraction had already failed |
| Citation chasing | Not attempted within this block |

**Why it matters.** Three of the four are **access failures, not absence of literature.** That distinction
is load-bearing: "we could not read it" and "it does not exist" are different statements, and only the
first is true here. Recording them as generic `PENDING` would blur them.

**Effect on results.** The composite claim stays at `POTENTIAL_DIFFERENCE`. Per the frozen rule an unread
family blocks the upgrade regardless of how the read ones turn out.

**What would close them.** Institutional full-text access for the paywalled records; the original citation
for T-CARE from whoever introduced the identifier into the master plan; and a citation-chasing pass, which
needs no special access and was simply not done.

---

## D-22 — A near-neighbour was returned for T-CARE and was NOT substituted

**What happened.** The T-CARE query returned *Target-Aware Safety-Residual Reinforcement Learning for
Cooperative Multi-UAV Pursuit* (TASRP, `10.3390/machines14070733`), a different method in a UAV domain.

**Why it is recorded.** Accepting a plausible near-match for a named record is how a pending family
silently becomes a closed one. It is recorded at `DISCOVERY_ONLY` with an explicit note that it must not be
substituted, in `search_log.jsonl`, `sources.bib` and the claim matrix.

---

## D-23 — D11 was resolved while D05 was deliberately left open

**What happened.** CCBS was selected as the conventional planner on method-level evidence. DACOOP-A was
resolved only to venue and abstract, and **no learned baseline was selected.**

**Why the asymmetry is correct.** CCBS could be judged on the predicate that matters for selection —
whether it is *competent* — because completeness and optimality are stated in the method text. For D05 the
predicate that matters is **which control choices remain learned and which are supplied by designed
structure**, and for DACOOP-A that is precisely the distinction an abstract cannot settle: it names both an
attention mechanism and an artificial potential field without apportioning between them.

Selecting on that basis would be a guess presented as a decision.

---

## Deviations that did not occur

No SUMO process start, no episode, no optimizer update, no checkpoint load, no TEST access. No reading
depth was upgraded beyond what was actually read. No family was declared closed because a search returned
nothing. The discriminating question was not narrowed. No inherited counter was reset, and no earlier
sealed package was written to.
