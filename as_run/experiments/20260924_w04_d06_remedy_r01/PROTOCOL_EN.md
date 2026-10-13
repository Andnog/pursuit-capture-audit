# Protocol — does the D06 remedy make capture satisfiable in SUMO, without weakening safety?

**Written before the probe was implemented.**

## What changed, by the Research lead's decision (A-46)

- Collision means **physical overlap**: `--collision.mingap-factor 0`, frozen in `configs/domain_v1.json`.
- Per-class min_gap: **pursuers 2.5 m, evader 1.0 m**.
- **D06 unchanged.** Safety checks **stay on**.

A remedy that is consistent on paper is not yet a remedy. A-45 showed D06 passing every consistency check
while being impossible in the simulator.

## Three arms, each in its own fresh process, all started with the contract's own simulator arguments

| Arm | Set-up | Must show |
|---|---|---|
| 1 | Evader stopped; pursuer closes from behind | Pursuer rests **outside** the band (> 2.00 m); **no collision** |
| 2 | Pursuer stopped ahead; evader closes from behind | Evader rests **inside** the band; **no collision**; the **independent capture judge** returns `SUPPORTED` over the held interval |
| 3 | Two bodies forced into overlap | A collision **is** reported — so "no collision" in arms 1–2 is not a detector that stopped working |

Arm 1 tests that the historical lesson survives: a trailing pursuer cannot satisfy the separation condition.
Arm 2 tests that capture is now possible. Arm 3 is the control without which arms 1 and 2 prove nothing.

The judge receives the recorded physical trace and the frozen contract, never a policy. **Coordination is
not tested here** — it is a team property, and a single blocking pursuer is deliberately not a coordinated
capture. This package tests only that the physical predicate can be satisfied.

## Acceptance rule, frozen before running

| Verdict | Condition |
|---|---|
| `REMEDY_VERIFIED` | Arm 1 outside the band with no collision; arm 2 inside the band, no collision, judge `SUPPORTED`; arm 3 reports a collision |
| `REMEDY_FAILED` | Any arm fails; the failing arm is named |

## Prohibited

Disabling safety checks. Changing D06. Any TEST map, optimizer or checkpoint.

## Resource limits

SUMO process starts permitted: **6** (three needed; headroom for a void run, declared in advance).
