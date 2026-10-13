# Protocol — learned ambush selection r01 (A-96)

Frozen before any gated episode. Approved by the Research lead ("yes; add something so we do not waste time or compute
if it is not improving by a minimum threshold"). Goal: can reinforcement learning improve on the ambush rule (A-94/95),
and can a KAN head make the learned policy interpretable?

**Learner.** At each decision the controller (`native/ambush_learning.py`) offers options:
- chase;
- keep the current plan;
- for each of the next 4 predicted junctions: a full lane-level block, and partial blocks of the predicted exit or the
  two predicted exits, whenever the team suffices and the assignment slack is ≥ −4 s.

Each option is a 12-feature token; the context has 6 features. A scorer (`rl/option_policy.py`) maps
[token, context] to a logit; the head is an **MLP** (64-64) or a **KAN** (B-spline Kolmogorov-Arnold layers 18→8→1,
cubic, 8 grid intervals). The critic is an MLP for both. The teacher is the ambush rule: keep a valid plan, else the
nearest full block with slack ≥ 2 s, else chase.

**Training** (TRAINING cities only; evader level and team cycle over AVOIDANT/RANDOM × 3/5; equal speeds; terminal
reward +1 on trapping, −0.005 per decision, γ 0.98):
- Behaviour cloning on 400 rule episodes (salt `PD9`), 20 epochs.
- PPO: batch 64 episodes, 4 epochs, clip 0.2, lr 3e-4, entropy 0.01, up to 4,096 episodes per run.
- Runs: heads MLP and KAN × seeds 1, 2, 3, in the order MLP s1, KAN s1, MLP s2, …

**Validation and circuit breakers.**
- Every 8 PPO iterations (512 episodes), the greedy policy is validated on 192 episodes (TRAINING cities, salt `PV9`).
  The score is smoothed as the mean of the last two validations.
- **Run breaker:** after ≥ 1,536 episodes, a run stops if the smoothed score has not improved by ≥ 0.02 for 4
  consecutive validations. The checkpoint kept is the best smoothed one.
- **Global breaker:** if after seed 1 neither head's best smoothed score exceeds the rule's validation score by
  ≥ 0.02, seeds 2–3 are skipped.

**Test** (fresh salt `PE9`; 7 cities incl. DEVELOPMENT; 20 scenarios × 2 SUMO seeds × 4 settings; full 300 s; D06):
the rule, the A-95 ambush planner, pursuit, a random-option control, and each run's best checkpoint.

**Primary (per head):** paired Δ D06, learned (averaged over its seeds) − rule, pooled over settings; bootstrap 95 %
CI over scenario-settings; passes if lower bound > 0. Secondary: per setting, KAN − MLP, learned − pursuit,
learned − A-95, learned − random option.

**Interpretability (post-test, descriptive):** KAN first-layer edge functions per feature, and permutation importance
of each feature on recorded decisions, with a random-initialised KAN as control.

Resumable chunks ≤ 25 min. Budget ≤ 12 CPU-h for training plus ≈ 3 CPU-h for the test. TEST cities closed.
