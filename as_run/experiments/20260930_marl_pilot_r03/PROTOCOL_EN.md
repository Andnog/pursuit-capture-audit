# Protocol — MARL pilot r03 (A-81; follows r02 NOT_PASSED and the A-80 fixes)

Frozen before any pilot episode; approved by the Research lead (option A, 2026-09-30). SUMO only, legal control
interface (A-76), physical-cage endpoint (A-72: safe region ≤ 2 junctions, every gate held, 10 s). Maps adelaide_cbd,
toronto_downtown, washington_downtown (TRAINING); team 3; evader AVOIDANT (A-62) at 1.5×; sigma 0.5.

Arms: **T** (candidates = escape gates) and **U** (candidates = 24 junctions the evader reaches soonest); identical
network (token scorer + CHASE/HOLD + centralized critic, `rl/policy.py`), 9 token features (A-80), event-driven
decisions, budget and seeds. Per arm × seed (1, 2): initial network → BC from the stateless cut (`cut_label`,
300 demonstration episodes, salt `PD`, 30 epochs) → PPO (4,000 episodes, batch 64, 4 epochs, clip 0.2, lr 1e-4,
entropy coefficient 0.001 on the per-pursuer mean entropy, γ 0.99, λ 0.95; training scenarios salt `PT<seed>`).

Evaluation (greedy) on **fresh reserved scenarios**: salt `PE3`, 40 per map = 120, one SUMO seed each (9500 + index).
The earlier reserved set (salt `PE`) was used by the A-80 development checks and is not used here. Checkpoints
evaluated: initial, BC, final; baselines: cut (stateful), cut_label (stateless), individual, random-over-gates.

**Primary (unchanged from r02), pass/fail per arm × seed:** paired Δ P(physical cage) final − initial on the 120
reserved scenarios, bootstrap 95 % CI lower bound > 0. **Pilot passes** iff all four arm × seed runs pass.
Note: after BC this test is expected to pass; it is kept for continuity with r02 and is not evidence that RL adds value.

**Pre-registered secondary (reported for every run, no pass/fail):** final − BC (does PPO improve on imitation?),
final − cut, and T − U per seed (descriptive only; two seeds cannot support a T vs U claim — that needs the
confirmatory study). Also reported: true emergencies (> 7 m/s²), collisions, failed episodes.

Budget estimate ≈ 20 CPU-h (8 workers, ≈ 2.5 h wall), measured from the A-80 PPO check. Sources are not modified
while the run is in progress. No TEST data.
