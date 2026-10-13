# Deviations — ambush learning r01

1. **Interrupted chunk.** The first training chunk stopped when the previous session ended (MLP seed 1 at 896
   episodes). Training resumed from the saved state; the state is saved after every PPO iteration, so nothing was
   lost.
2. **Test-resume defect.** Failed test episodes (scenario placement) were written without their scenario keys, and the
   next chunk crashed while reading them. The fix records the keys of failed episodes; keyless legacy failure rows
   are ignored on resume and in the summary. Their scenarios are re-attempted, fail again and are recorded with keys.
   No successful episode is affected.
