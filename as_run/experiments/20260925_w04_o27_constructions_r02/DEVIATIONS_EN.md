# Deviations — O27 r02

None from the protocol. The search ran once, to completion, on the code whose hashes `inputs.json` records;
the hashes were re-checked after the run and all matched. No source was modified while it ran.

## Found after the run

- **Declared-model defect:** a hold on the edge after an internal lane is not anticipated while the vehicle is
  on that internal lane (`diagnostics_counterfactual.json`). Found by examining the one safety failure in each
  CONSTRUCTED case's b1 counterfactual. It was invisible to the pre-launch legality checks, which ran baselines
  without plans and therefore without holds, and to the unit test for holds across a link, whose internal lane
  has zero length.
- **No git history.** The project directory is not a repository, so `source_snapshot/` preserves copies of
  every hashed source as executed. They are records, not modules to import.
