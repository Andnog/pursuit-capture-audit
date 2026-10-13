# Protocol — pre-positioning ambush with gradient-free optimisation r01 (A-98)

Frozen before any gated episode. Approved by the Research lead ("yes; we can increase the number of pursuers and
anything else so it works better; you can leave it running overnight").

**Planner** (`native/ambush_plus.py`). The A-94 ambush plus pre-positioning: when no full ambush is active, `chasers`
pursuers keep chasing and the others wait in the lanes of the predicted exits of junctions `pre_k_min..pre_k_max`
ahead (if they can arrive `pre_margin` s before the evader). Parameters: depth, margin_s, slow, startup_s, hold_m,
chasers, pre_k_min, pre_k_max, pre_margin, prepos_during_plan. Development check (salt `DEVB`, not gated, 29 scenarios
per cell, AVOIDANT): defaults 0.35 / 0.48 / 0.48 vs A-95 ambush 0.31 / 0.41 / 0.45 for teams 3 / 5 / 7.

**Search** (TRAINING cities only; evader AVOIDANT/RANDOM × teams 3/5; equal speeds; success = trapped or D06; episodes
end at trapping):
- **Generation 1:** 32 uniformly sampled configurations plus the defaults, with successive halving:
  - round 1: 48 episodes each; 8 survivors;
  - round 2: +144 episodes; 3 survivors;
  - round 3: +384 episodes; 1 survivor.
  Ranking is by mean success over all rounds so far; every configuration uses the same episodes.
- **Breaker:** if the generation-1 best does not beat the defaults by ≥ 0.02 on round 3, generation 2 is skipped and
  the defaults are carried forward.
- **Generation 2:** 16 Gaussian perturbations of the best (σ = 15 % of each range; integers ±1), the best, and the
  defaults, with the same halving.
- **Validation:** final vs defaults on fresh scenarios (salt `PV11`, 192 episodes each).

**Test** (fresh salt `PE11`; 7 cities incl. DEVELOPMENT; 20 scenarios × 2 SUMO seeds; evader AVOIDANT and RANDOM;
teams **3, 5 and 7**; full 300 s; D06). Runs: optimised planner, default pre-positioning planner, A-95 ambush, pursuit,
and the optimised planner with each single pursuer alone.

**Primary:** optimised − A-95 ambush, pooled over the 6 cells (paired, bootstrap 95 % CI over scenario-cells); passes if
the lower bound is > 0. **Secondary:**
- per-cell contrasts against A-95, pursuit and the defaults;
- default − A-95;
- synergy of the optimised planner (team − [1 − Π(1 − p_i)]), with cooperation declared in a cell if the
  Bonferroni-adjusted (6 cells) lower bound is > 0.

Teams of 7 use pursuer ids p6, p7 under the same placement rule (nested: p1–p5 start where they do in a team of 5).
Resumable chunks ≤ 25 min. Budget ≈ 6 CPU-h search + ≈ 25 CPU-h test. TEST cities closed.
