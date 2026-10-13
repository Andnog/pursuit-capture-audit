# Protocol — MAPPO for the multi-agent ambush r01 (A-103)

Frozen before any gated episode. Approved by the Research lead ("do it so nothing is left pending"): a standard
multi-agent RL method (MAPPO) against the optimised planner.

**Agents and actions** (`native/mappo_ambush.py`). Each pursuer is an agent. Every 3 s each agent independently picks
one token:
- a blocking slot: one passenger lane of one exit of one of the next 4 predicted junctions, at most 18 slots;
- CHASE;
- STAY.

Each slot token has 12 agent-specific features: own slack, best teammate slack, teammates targeting it, depth, exit
rank, lane, junction lanes, exits, own target, in place. The agent context has 7 features.

**Learning.**
- Parameter-sharing actor, **MLP or KAN** head (`rl/mappo_policy.py`; the KAN layer is verified against pykan,
  A-100). Centralised critic over a 7-feature global state.
- Shared team reward: +1 on trapping, −0.005 per tick; γ 0.99, GAE λ 0.95.
- BC from the A-99 planner (teacher mode, 300 episodes, salt `PD13`, 15 epochs).
- Then MAPPO: batch 64 episodes, 4 epochs, clip 0.2, lr 3e-4, entropy 0.01, up to 4,096 episodes per run.
- Runs: heads MLP and KAN × seeds 1–3. Training on TRAINING cities, settings AVOIDANT/RANDOM × teams 3/5.

**Breakers (as A-96).**
- Validation every 8 iterations on 192 episodes (salt `PV13`); the score is the mean of the last two validations.
- **Run breaker:** after ≥ 1,536 episodes, a run stops when the smoothed score has gone 4 validations without
  improving by ≥ 0.02.
- **Global breaker:** seeds 2–3 are skipped if no seed-1 head beats the better of teacher mode and the planner by
  ≥ 0.02 in validation.

**Test** (salt `PE13`; 7 cities; 20 scenarios × 2 seeds; AVOIDANT/RANDOM; teams 3, 5, 7; full 300 s; D06). Policies:
the planner (A-99, `c2_15`), teacher mode, pursuit, a random-slot control, and each run's best checkpoint.
**Primary (per head):** MAPPO (averaged over seeds) − planner, pooled; passes if the CI lower bound is > 0.

Resumable chunks ≤ 25 min. Budget ≈ 25 CPU-h. TEST cities closed.
