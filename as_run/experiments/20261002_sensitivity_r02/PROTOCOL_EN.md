# Protocol — sensitivity study r02 (A-101; r01 void, harness defect): tuning for 7 pursuers; faster pursuers

Frozen before any gated episode. Approved by the Research lead (option B; "run it all at once, overnight if needed").
Descriptive sensitivity analysis: what it takes to reach higher capture rates. It does not replace the A-99 primary
result.

**Part A — parameters tuned for 7 pursuers.**
- One generation of the A-98 search on TRAINING cities, teams of 7, evader AVOIDANT and RANDOM, salt `PO7`:
  24 random configurations, plus the A-99 optimum (`c2_15`) and the defaults.
- Successive halving: 48 → 144 → 384 episodes per configuration, keeping 8 and then 3.
- **Breaker:** the tuned configuration is used only if it beats both `c2_15` and the defaults by ≥ 0.02 on round 3;
  otherwise the better of those two is kept.
- Fresh validation: salt `PV12`, 192 episodes each.

**Part B — test.** Salt `PE12`; 7 cities incl. DEVELOPMENT; 20 scenarios × 2 SUMO seeds; full 300 s; D06.
- **Team 7, pursuers at 1.0×:** tuned, `c2_15`, defaults, pursuit.
- **Pursuer speed factor 1.0×, 1.1× and 1.2×** (evader 1.0×), teams 3 and 5: `c2_15` and pursuit. The planners'
  time model uses the pursuers' true speed factor.

**Reported:** capture with bootstrap CIs; tuned − `c2_15`, tuned − defaults and tuned − pursuit for team 7; for each
speed, `c2_15` − pursuit and `c2_15`'s gain over 1.0×.

Resumable chunks ≤ 25 min. Budget ≈ 20 CPU-h. TEST cities closed.
