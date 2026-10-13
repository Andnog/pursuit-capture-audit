# Protocol amendment — the coordination criterion

**Date:** 2026-09-25. **Decided by the Research lead.** **Made before any real O27 case was run.**
`PROTOCOL_EN.md` is not edited; this file amends it.

## Change

A complete construction now requires **both**:

1. **The D12 `b1` contrast is positive** — unchanged: the helper runs `b1` for the 5 decisions before the
   witness start and the capture fails.
2. **A necessity check** — the same plan with the helper **never acting** (physically present, holding at its
   start, no teleport) does **not** capture.

## Verdicts, replacing the protocol's table

| Verdict | Condition |
|---|---|
| `CONSTRUCTED` | both contrasts positive |
| `B1_CONTRAST_WITHOUT_NECESSITY` | `b1` positive, but the capture happens without the helper — the substitute *disrupted* it |
| `NECESSARY_BUT_B1_NULL` | the helper was needed, but a 5-decision substitution does not reveal it |
| `CAPTURE_NOT_COORDINATED` | neither |
| `NO_WITNESS_WITHIN_CAP` | no verified factual capture within budget |

The W4 gate still requires two `CONSTRUCTED` among the four AVOIDANT cases.

## Why — evidence from synthetic controls, not from any real case

On a hand-built junction with cycles (`positive_control_network.py`), the `b1`-only rule labelled a capture
**coordinated** that one pursuer achieved alone: the substitute cut in and blocked the evader, while the plan
with the helper never acting still captured. 124 such cases at AVOIDANT.

The same control produced **396** captures at OPTIMAL_ESCAPE where the helper **was** necessary and `b1` was
null. The window was not the cause — the evader's last decision fell inside it (median 4.6 s before the
witness start), and re-anchoring the window on that decision recovered 0 of 396. The helper's contribution
was **positional and established early**: it spends ~10 s reaching its cover, and during any five decisions
near the evader's choice it is still physically on the covered edge whatever `b1` commands.

## Consequence stated in advance

Under this rule a construction needs a helper whose contribution is **late** enough for a 5-decision
substitution to undo it. Early positional coordination will register as `NECESSARY_BUT_B1_NULL`. That is a
property of the frozen rules, recorded now so a low `CONSTRUCTED` count is not later read as infeasibility.
