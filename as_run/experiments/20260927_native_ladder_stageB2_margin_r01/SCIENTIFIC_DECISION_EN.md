# Decision — native ladder, stage B2 (plans with margin)

**Rule not met: zero robust constructions** (4 coordinated: C2 1, C3 2, C5 1). Captures became more frequent per
scenario (C2 AVOIDANT 8/8 vs 4/8 in B) but every coordinated capture failed 0/5 under sigma 0.5.

**Post-hoc (development), not gated:**
1. Keying the AVOIDANT evader's sampled pair to a constant instead of the decision time turned the C5 case from 0/5 to
   5/5 under driver noise, but not the others: part of the fragility is the evader's designed randomness (level 2 picks
   the better of a random pair), which a single fixed trap cannot beat in every draw.
2. Capture probability over 10 seeds (sigma 0.5) for the 10 coordinated constructions of B and B2: **with helper
   37/100, helper removed 28/100** — a +9-point average helper effect, heterogeneous (+4 to −3 of 10 per case).

**Reading.** A deterministic "this trap always works" standard is the wrong instrument against a stochastic evader.
Coordination shows up as a modest increase in capture probability, which is the master plan's own estimand
(Δ = p_Z(J1) − p_Z(·)).
