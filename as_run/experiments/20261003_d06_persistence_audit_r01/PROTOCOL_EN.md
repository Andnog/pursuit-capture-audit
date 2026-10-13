# Protocol — D06 persistence audit r01 (A-108)

Pre-registered in `governance/AMENDMENTS_EN.md` (A-108) before the run. Script `scripts/audit_d06_persistence.py`.

- Population: every D06-positive test episode of `plus_opt` (c2_15), `ambush_a95` and `pursuit` in the sealed A-99
  test (`experiments/20261002_ambush_optimization_r01`, salt PE11): 1,433 episodes.
- Natural replay: the sealed episode, unchanged (determinism check). t_c = first frame at which any pursuer's
  continuous D06 run reaches the 2 s dwell.
- Frozen replay: identical until t_c; from the first controller step at or after t_c every pursuer is held at speed 0
  and no new command is issued.
- Escape: evader more than 10 m from its t_c position within 60 s (or leaving the network).
- Primary, per method: frozen escape ≤ 0.10.
- Consequence rule: persistent capture (reproduced D06, no frozen escape) recomputed for every test episode; the A-99
  claims stand only if their CI conclusions are unchanged.
- Secondary: natural-continuation escape; red/yellow signal within 40 m at the freeze; another lane of the evader's
  edge with no pursuer ahead at the freeze.
