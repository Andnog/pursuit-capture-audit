# Decision — the D06 remedy works in SUMO

**Claim class: satisfiability of the capture predicate in the simulator.** No TEST map, no optimizer, no
checkpoint. Safety checks on throughout.

## Verdict

`REMEDY_VERIFIED`, on the first run.

| Arm | Result |
|---|---|
| 1 · pursuer trails a stopped evader | rests at **2.501 m** — outside the band; **no collision**; judge **`REJECTED`** |
| 2 · evader stops behind a stopped pursuer | rests at **1.001 m** — inside the band; **no collision**; judge **`SUPPORTED`**, 17.2 s witness |
| 3 · control: bodies forced to overlap | collision **reported** |

## What each arm establishes

**Arm 1 — the historical lesson survives by construction.** A pursuer that merely follows the evader cannot
satisfy the separation condition. This is the property the contract encoded from O26, preserved rather than
traded away.

**Arm 2 — capture is now possible.** The frozen physical predicate is satisfied in SUMO with safety checks on
and without a collision, judged by the independent capture judge on the recorded trace. Capture happens when
the evader is brought to rest against a pursuer ahead of it: **interception, not chase.**

**Arm 3 — the "no collision" results mean something.** The detector still reports genuine overlap.

## Not established

**Coordination.** A single blocking pursuer is deliberately *not* a coordinated capture; the frozen
coordination requirement asks for more than one pursuer's decisions. That is O27's job. Also not tested:
capture with a moving evader, across a junction, or laterally.

## A defect fixed on the way

The judge ran on geometry the backend now reports correctly. Before this package, `TraciBackend` passed SUMO's
**front-bumper** position to a **centred** rectangle, shifting every body half a length forward. On one lane
with one heading that cancels, which is why no earlier native test noticed; across a junction it misplaced
bodies by up to a body length. No sealed result depended on absolute positions.
