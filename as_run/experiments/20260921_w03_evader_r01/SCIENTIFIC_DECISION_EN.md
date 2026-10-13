# Scientific decision — scripted evader levels (W3 completion)

Experiment: `20260921_w03_evader_r01`. Date: 21 September 2026.

**Decision: `W3 ARTIFACT COMPLETE; DIFFICULTY ORDERING VERIFIED MONOTONE; D06 DEAD-END RULE IS NOW CHECKABLE.`**

---

## 1. What this completes

`simulator/evader.py` is a W3 artifact that W3 closed **without**, recorded as deviation D-14: D08 was
unresolved, and writing an evader then would have meant inventing the policy the plan requires be
justified. D08 was frozen on 21 September, so the artifact is now built **to the decision** rather than to
a guess.

All six frozen checks pass; 34 tests within them; 262 across the project on both the pinned and a bare
interpreter; lint clean.

## 2. What was verified

**The three levels behave as declared and differ in difficulty.** Over 200 seeds on a branch where one
continuation is open and the other a cul-de-sac:

| Level | Dead-end rate |
|---|---|
| 1 `RANDOM` | 0.470 |
| 2 `AVOIDANT` | 0.275 |
| 3 `OPTIMAL_ESCAPE` | 0.000 |

Monotone, and asserted as such by a test rather than left to inspection.

**Decisions are reproducible, and reproducible in the way replay needs.** The same `(level, seed)`
reproduces exactly. Randomness is **keyed on the decision index**, not sequential — so a restored prefix
reproduces the same choice regardless of what else consumed randomness. W3 showed a shared seed does not
couple two runs after divergence; a sequential stream here would have reintroduced exactly that problem.

**The information boundary holds.** `choose` receives the decision index, the current edge and the
pursuers' **current** nodes. No future route, no oracle, no judge output, at any level.

## 3. The part that matters most: D06's dead-end rule is now checkable

The capture contract admits a cul-de-sac capture as **coordinated** only if the evader was **forced**
there, with evidence no better exit existed where it entered. That evidence can only come from the
evader's own decision record, so **every decision logs its full admissible set**, not just the choice.

`was_forced_into_dead_end` returns forced only when **every** alternative at the entry decision was itself
a dead end. It audits the decision *before* the cul-de-sac, because that is where alternatives existed —
auditing the dead-end decision itself would always conclude "no choice available" and make the rule vacuous.

**This is deliberately conservative.** A pursuer team might block an escapable alternative without that
alternative being a cul-de-sac, and this test would not credit them. Crediting that needs occupancy
evidence at the entry decision, which this module does not have. **The strict reading is the one that
cannot over-credit**, and over-crediting is the failure mode that matters for an endpoint.

## 4. A defect that measurement caught, and reading did not

The first run showed level 2 entering dead ends **75.5%** of the time against **47%** for level 1 — the
harder level was easier. Graph distance rates a cul-de-sac as maximally safe, because no pursuer can reach
it. True, and suicidal.

The code looked reasonable and its unit tests passed. Only running all three levels over 200 seeds and
comparing the rates exposed it. **A difficulty knob that is not monotone makes every cross-level comparison
meaningless**, and results labelled "harder" would have come from an easier task.

Fixed by sharing one escape score across levels 2 and 3, with monotonicity now asserted directly.

## 5. What this does not establish

**Not that any of this runs against a real network.** No SUMO process was started. The topology is a small
in-memory directed graph, **not** one of the 12 audited OSM networks. Wiring the evader to a real network
is W4.

Not physical feasibility, assistance, learning, benefit, transfer or novelty.

## 6. Where W4 now stands

D06, D08 and D04 are resolved, and the sealed historical TEST set is identified. **W4's decision blockers
are cleared.** What remains is implementation:

1. **First execution of the TraCI surface** — written at W3, never exercised. Expect defects there.
2. **The interaction half of the constructive problem** — blocking windows derived from participants'
   committed plans, a fixed-point problem, on a real lane network. The single-vehicle half is closed in the
   abstraction.
3. **Wiring the evader to a real network** — the 12 audited maps are available and hash-verified.
4. **D15** — the split decision. The legacy 4/4/4 assignment is audited and available, but adopting it
   adopts the legacy exposure with it.

## 7. What this decision does not authorize

No SUMO episode, optimizer run, checkpoint load or TEST access. The historical TEST four —
`chicago_loop`, `melbourne_cbd`, `salt_lake_city`, `minneapolis_downtown` — remain closed. No weakening of
the coordination requirement or the dead-end rule to admit a capture that was not forced.
