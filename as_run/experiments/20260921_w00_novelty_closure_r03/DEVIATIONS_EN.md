# Deviations

Experiment: `20260921_w00_novelty_closure_r03`. Stage: W0 revision.

---

## D-32 — One query was executed and deliberately NOT screened

**What happened.** Query Q13 (`urban OR road network OR SUMO OR lane` × `pursuit OR interception OR
capture` × `reinforcement learning` × `cooperative OR joint OR coordination`) returned **164** documents.
The top results were traffic-signal control, urban digital twins, vehicle-offloading and water-resource
allocation: `capture` and `lane` match a large unrelated literature.

**What was done.** Recorded as `TOO_BROAD_NOT_SCREENED`. It is **not** reported as a result.

**Why this is recorded rather than dropped.** Screening a convenient subset of 164 and reporting "no
refutation found" would have been a stronger-sounding claim than the evidence supports. An executed query
whose results were not examined is a fact about the search, and hiding it would misrepresent coverage.

---

## D-33 — The family is `FAMILY_PARTIAL`, not closed, and the reason is coverage not effort

**What happened.** B06's forward citations were screened — all 8 for the PRICAI version. **Not** retrieved:
the 5 citing works of the AAMAS version, and the forward citations of B03 and B04.

**Why it matters.** Under the frozen rule, closing requires forward citations of **all three** records.
Reporting `FAMILY_CLOSED` on one of three would overstate the search.

**What changed from r02.** The blocker is no longer *access*. Scopus is available, so the remaining work is
**reachable** — it simply was not done in this pass. That is a materially better position and is recorded
as such.

---

## D-34 — A browser popup blocked navigation mid-session

**What happened.** A page-opened popup appeared during the Scopus session, after which the agent could no
longer navigate the tab. Clicking and form entry continued to work, so the remaining queries were run
through the in-page advanced-search editor instead.

**Effect on results.** None. Every query recorded here was executed and its result read. The popup limited
throughput, not correctness.

**Note.** The agent did not and may not drive or close a page-opened popup. No credentials were entered at
any point; the Scopus session was already authenticated when it was reached.

---

## Deviations that did not occur

No SUMO process start, no episode, no optimizer update, no checkpoint load, no TEST access. The
discriminating question was not narrowed. No reading depth was upgraded beyond what was read — the three
new records are recorded at `TITLE_AND_METADATA` and explicitly block the claims they touch. No family was
declared closed on partial coverage.
