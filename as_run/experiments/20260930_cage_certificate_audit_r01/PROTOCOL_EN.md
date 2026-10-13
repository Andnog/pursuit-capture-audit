# Protocol — physical-cage certificate audit r01 (A-83)

Frozen before any audit episode. Question: when the physical-cage certificate (A-72: safe region ≤ 2 junctions,
every gate held by a pursuer within 25 m at ≤ 2 m/s, 10 s) fires, is the evader actually trapped?

Population: every certified cage in the sealed pilot r03 evaluation (salt `PE3`, 120 scenarios) for checkpoints
T_seed1_final, T_seed2_final, U_seed1_final, U_seed2_final and the cut heuristic. Each episode is re-run in SUMO with
the same scenario and seed; it must reproduce the recorded certification time (reported). After certification the
simulation continues for 60 s under two conditions:

- **hold** (primary; tests the certificate's claim): from certification on, every pursuer keeps its last command
  (HOLD) — pursuers already stopped stay; pursuers still driving continue to their last target and stop there.
- **policy** (secondary): the policy keeps deciding (it was never trained past certification).

Measures per certified cage (evaluated at the 1 s controller steps in the 60 s after certification):

- **M1 escape** (primary): the evader enters an edge whose origin junction was a gate at certification time, i.e.
  it passes through the cage boundary.
- **M2 physically blocked**: the evader is at ≤ 0.5 m/s for ≥ 2 s with a pursuer as its immediate leader within 15 m.
- **M3 red-light confound**: at certification the evader is at ≤ 0.5 m/s at a red or yellow signal within 30 m, with
  no pursuer leader within 15 m.
- **M4 contact capture**: the D06 capture predicate (with A-57 alignment) holds anywhere in the trace.
- Also: evader speed at certification, time from certification to M2, share of the window with the certificate still
  valid, maximum displacement from the certification position.

Pre-declared reading: the certificate is **adequate** if the hold-condition escape rate has a 95 % bootstrap upper
bound ≤ 0.10 (pooled over the five policies). Otherwise the endpoint must be revised before any further MARL claim.
M2–M4 are descriptive. Development analysis on TRAINING maps only; no TEST data; no training.
