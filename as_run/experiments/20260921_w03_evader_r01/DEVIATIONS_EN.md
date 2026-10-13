# Deviations

Experiment: `20260921_w03_evader_r01`. Stage: W3 completion.

---

## D-29 — The difficulty ordering was inverted, and measurement caught it

**What happened.** The first run reported dead-end rates of **47% for level 1 (RANDOM)** and **75.5% for
level 2 (AVOIDANT)**. The supposedly *harder* level walked into cul-de-sacs far more often than random —
so it was substantially **easier** for the pursuers.

**Cause.** Level 2 scored each continuation by graph distance to the nearest pursuer. A cul-de-sac has no
onward edges, so pursuers cannot reach it, so it scored as **maximally safe**. That is literally true and
strategically suicidal. Level 3 already carried a dead-end penalty; level 2 did not.

**Why it would have been damaging.** The evader level is the knob that sets task difficulty. A non-monotone
knob would have made every cross-level comparison meaningless — and worse, results at "level 2" would have
looked like an *easier* task while being labelled harder.

**Resolution.** Levels 2 and 3 now share one `_escape_score` carrying the dead-end penalty. Level 2 stays
suboptimal through *which* open direction it picks, not by trapping itself. Rates are now
**0.470 → 0.275 → 0.000**, monotone. A test asserts monotonicity directly, so a regression fails rather than
being discovered by inspection.

**This was found by measuring, not by reading.** The code looked reasonable and its unit tests passed; only
running all three levels over 200 seeds and comparing exposed it.

---

## D-30 — Two sentinels with opposite meanings collapsed to the same value

**What happened.** Unreachable distance and dead-end penalty were both encoded as `-1.0` when scores were
written into the decision record.

**Why it matters.** They are *opposite* outcomes. Unreachable means no pursuer can get there — the safest
result for the evader. A dead end is the worst. Collapsing them corrupted both the choice and the audit
record, which reports the scores.

**Resolution.** `UNREACHABLE_SCORE = 1e9` and `DEAD_END_PENALTY = -1.0`, with a test asserting they differ
and that unreachable scores high rather than low.

---

## D-31 — Four failed source edits from string-matching reformatted code

**What happened.** Four successive patches silently failed or half-applied because `ruff format` had
reflowed the code they were matching. One aborted mid-script on an assertion, so an *earlier* successful
replacement in the same script was never written either — leaving `_avoidant` completely unpatched while
its sibling method was updated, which is how the inverted ordering survived a round of "fixes".

**Why it matters.** A silent no-op patch is worse than a failed one: the subsequent test run measures the
old behaviour while the operator believes the new one is in place.

**Resolution.** Switched to line-range editing after inspecting the actual file. This is the fifth occasion
in this project where a mechanical text edit damaged or failed to apply to source; the standing lesson is
already recorded in amendment A-09 and is reinforced here: **inspect before patching, and never assume the
text you wrote is the text on disk.**

---

## Deviations that did not occur

No SUMO process start, no episode, no optimizer update, no checkpoint load, no TEST access. No frozen
decision was altered: the implementation follows D08 as frozen. No earlier sealed package was written to.
