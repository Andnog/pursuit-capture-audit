# Protocol — MARL pilot for certified coordinated caging (A-78)

Frozen before any pilot episode. SUMO only, legal control interface (A-76), physical-cage endpoint (A-72: safe region
≤ 2 junctions, every gate held, 10 s). Maps adelaide_cbd, toronto_downtown, washington_downtown (TRAINING); team 3;
evader AVOIDANT (A-62) at 1.5×; sigma 0.5.

Arms: **T** (candidates = escape gates) and **U** (candidates = 24 junctions the evader reaches soonest); identical
network (token scorer + CHASE/HOLD + centralized critic, `rl/policy.py`), features, budget and seeds. Per arm × seed
(1, 2): initial network → BC from the cut heuristic (300 demo episodes, salt `PD`, 15 epochs) → PPO (6,000 episodes,
batch 64, 4 epochs, clip 0.2, lr 3e-4, entropy 0.01, γ 0.99, λ 0.95; training scenarios salt `PT<seed>`).

Evaluation (greedy) on **reserved scenarios** (salt `PE`, 20 per map = 60, one SUMO seed each): initial, BC, final
checkpoints; baselines cut, individual, random-over-gates.

**Acquisition (pass/fail, per arm × seed):** paired Δ P(physical cage) final − initial on the 60 reserved scenarios,
bootstrap 95 % CI lower > 0. **Pilot passes** iff all four arm × seed runs pass. Descriptive only (not confirmatory):
T − U, final − BC, final − cut, final − random. A confirmatory study is sized after the pilot.
