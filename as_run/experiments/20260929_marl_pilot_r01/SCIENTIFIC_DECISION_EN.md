# Decision — MARL pilot r01: VOID (crash)
Stopped at PPO iteration 5 of arm T seed 1 (320 episodes): a vehicle momentarily on no road (parking transition) made
the engine query lane "_0"; one episode's exception stopped the whole pilot. Fixed: such a step is skipped for that
vehicle; episode failures are caught, counted and logged. Measured throughput (~1 episode/s, ~8 CPU s per episode)
would take 6,000 PPO episodes per run to ~56 CPU-h, above the approved ~40: r02 uses **4,000** (declared deviation,
budget-driven; the partial r01 training log is not used for any decision).
