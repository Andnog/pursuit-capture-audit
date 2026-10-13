# Protocol — MARL trap pilot r04 (A-86): decisive test of the MARL line

Frozen before any episode. Approved by the Research lead (option 3: run the decisive MARL test in full, with a
patience circuit breaker, while the methodological manuscript is drafted).

**Question.** Can a learned team policy trap the evader more often than the cut heuristic under the direct A-84
endpoint? If not, the MARL line is closed.

Environment as r03 (SUMO, legal control interface, adelaide_cbd / toronto_downtown / washington_downtown TRAINING,
3 pursuers, evader AVOIDANT 1.5×, sigma 0.5), except the terminal reward: **+1 when the evader is trapped** —
immobilised ≤ 0.5 m/s for 10 s with a pursuer leader within 15 m and no red/yellow signal within 30 m (A-84). The
certificate potential Φ = −log(1 + |safe|) is kept as shaping; the certificate no longer ends the episode or gives a
terminal reward. Episodes end at trapping, collision (−1) or 300 s.

Arms T and U, seeds 1 and 2. Per run: BC from the stateless cut (300 demonstration episodes, salt `PD`, 30 epochs) →
PPO (batch 64, 4 epochs, clip 0.2, lr 1e-4, entropy 0.001, γ 0.99, λ 0.95; training salt `PT<seed>`) up to **8,000
episodes**.

**Validation and circuit breaker.** Every 8 PPO iterations (512 episodes) the greedy policy is evaluated on a
validation set (salt `PV`, 30 scenarios per map = 90). The best-validation checkpoint is kept (improvement ≥ 0.011,
one scenario). After at least 2,048 episodes, a run stops early only if validation has not improved for **6
consecutive validations** (3,072 episodes) **and** its best validation P(trapped) is not above the cut's on the same
set. Runs above the cut continue to 8,000 episodes.

**Test.** Fresh scenarios (salt `PE5`, 60 per map = 180), one SUMO seed each, endpoint P(trapped) = immobilised or
D06 contact capture. Policies: cut, individual, random-over-gates; per run BC, best-validation and last checkpoints.

**Primary (per arm):** paired Δ P(trapped), best-validation checkpoint (averaged over the two seeds per scenario)
minus cut; bootstrap 95 % CI over scenarios. The arm passes if the lower bound > 0. **The MARL line continues only if
at least one arm passes**; otherwise it is closed and the thesis proceeds with the methodological contribution.
Secondary (descriptive): best − individual, best − BC, last − cut, T − U, cut − individual.

Budget: ≤ 75 CPU-h (≈ 9.5 h wall with 8 workers); the breaker can shorten it. No TEST data.
