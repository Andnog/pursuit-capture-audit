# Protocol — commitment study r01 (A-106)

Frozen before any episode. Approved by the Research lead ("confirm the 3-s effect, then we write").

**Question.** Does holding the planner's lane orders (blockers and pre-positioned pursuers) for `commit_s` seconds,
instead of re-planning every controller step, improve capture? This replicates the incidental A-105 finding (teacher
mode 0.403 vs planner 0.365) in a dedicated, pre-registered test, with a dose-response.

**Design.**
- Planner: A-99 `c2_15`, with `commit_s` ∈ {1, 2, 3, 5}. 1 = re-plan every step, the A-99 planner. Chasers follow
  the evader every step in all variants.
- Scenarios: fresh salt `PE14`; 7 cities; 20 scenarios × 2 SUMO seeds; evader AVOIDANT and RANDOM; teams 3, 5 and 7;
  full 300 s; D06.

**Primary:** commit 3 s − commit 1 s, pooled and paired over scenario-cells; bootstrap 95 % CI lower bound > 0.

**Secondary (descriptive):** 2 s and 5 s against 1 s (dose-response); per-cell 3 s − 1 s.

Resumable chunks ≤ 25 min. Budget ≈ 10 CPU-h. TEST cities closed.
