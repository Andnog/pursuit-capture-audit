# Protocol — F1: caging feasibility probe (A-70)

Frozen before any F1 run. Maps C1–C5 (controlled), 20 scenarios each (salt `F1`), evader AVOIDANT (A-62 input) at
speed factor 1.0 and 1.2, strategies cut / individual / pursuit, 5 SUMO seeds (7001–7005, sigma 0.5). Certificate as in
A-70 (K = 2 junctions, margin 0.5 s, persistence 10 s). Contact capture (D06 + A-57, any pursuer) reported alongside.

**Criteria (all must hold for "F1 passes"):**
1. *Achievable, not trivial:* pooled P(caged | cut) in [0.10, 0.95] at one or both speeds.
2. *Requires coordination:* pooled paired Δ = P(caged | cut) − P(caged | individual), bootstrap over scenarios,
   95 % CI lower bound > 0, at one or both speeds.
Reported, not gated: cut − pursuit, per-map results, contact captures, collisions, hard braking.
If F1 passes: the question change (A-70) is proposed for recording; if not: stop and decide.
