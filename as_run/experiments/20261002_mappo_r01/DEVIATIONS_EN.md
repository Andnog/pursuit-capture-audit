# Deviations — MAPPO r01

1. **Test-harness defect (fixed and re-run).** In random-slot mode the controller called the actor although no
   network is loaded. The exception left the TraCI connection open, and later episodes with the same connection label
   in the same worker failed ("Connection … is already active"). In the first test pass 7,792 test episodes failed
   for that reason.
   - **Fix:** random mode draws uniformly without a network, and `replay` closes the TraCI connection on any
     exception.
   - The failed rows are archived in `results_failed_run1.jsonl` and re-run; successful rows were kept, because
     episodes are deterministic per scenario and seed.
   - Earlier studies were checked: their only failures are scenario-placement errors, with no cascade.
2. Training and validation were unaffected: no random-mode episodes, and models were always present.
