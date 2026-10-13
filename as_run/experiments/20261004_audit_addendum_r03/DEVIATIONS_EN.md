# Deviations — audit addendum r03

1. **Runner change during the run (no effect on episode logic).** The first background block was stopped at its
   time limit, with 2,721 rows written: one chunk completed, and the next chunk produced no result for about 1.5 h.
   - A 3-minute probe chunk then ran normally (2,721 → 3,139).
   - From the next chunk on, `main()` uses `run_with_timeout`: results are awaited with a 30 s timeout, and a chunk is
     abandoned after 15 min without any result. The pool is then terminated, and unfinished tasks are retried in the
     next chunk.
   - The episode functions, the task list and the analysis are unchanged.
   - `inputs.json` records the script hash at launch; the final hash is recorded at sealing.
2. The rows already written are kept. The results file was checked after the stop: 2,721 lines, all valid JSON.
