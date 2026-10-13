# Protocol — first execution of the TraCI call surface

**Written before `TraciBackend` was implemented.** Frozen at the time of writing.

## What this is, and what it is not

This is the **first SUMO process started in this project root**. Before it, the only SUMO invocation was
`--version`.

**It is not a campaign.** O22 remains open, and its discharge condition blocks *native campaigns* until
native regression evidence exists under the new capture contract. A bounded, attended, instrumented run that
starts a process, exercises an interface and closes it is not a campaign, and claims nothing that O22 guards.

**It is not a capability trial.** No capture is attempted, no success is scored, no optimizer runs, no
checkpoint is loaded. The historical capability allowance is untouched. **No claim about physical feasibility
or about capture ability may be drawn from this package**, whatever the run shows.

**Claim class:** software correctness of the adapter against a real simulator, plus one empirical property of
SUMO itself.

## The question that makes this worth running

`state_restoration` is currently recorded as `SUPPORTED_AGAINST_A_FIXTURE_NOT_AGAINST_SUMO`. The fixture is
in-memory and restores exactly by construction. **SUMO is not obliged to.**

The assistance audit requires replay coupling: a run restored from a prefix must continue *identically*,
or a measured contrast between two arms confounds the intervention with simulator drift. That requirement
rests on an assumption **never tested**: that `simulation.saveState` / `simulation.loadState` yields a
byte-identical continuation, including SUMO's own random stream.

**If it does not, the assistance audit design is unsound and must change.** That is the finding this package
exists to obtain, in either direction.

## Method, fixed before implementing

1. `scripts/preflight.py` must pass. It blocks on a binary/binding version mismatch.
2. Start SUMO over the **TraCI socket** (`libsumo` is unavailable on this platform, recorded at W2).
3. Use one **TRAINING** map, read-only, from the legacy asset root. **No TEST map is opened.** No map is
   copied, modified or written.
4. Exercise **every** method of the `SimulatorBackend` protocol against the live process.
5. **Restoration test.** Advance `P` steps. Capture state. Advance `M` steps, recording the full trajectory
   of every vehicle. Restore. Advance `M` steps again, recording again. **Compare the two trajectories
   exactly**, not within a tolerance.
6. Close the process. Assert no process is left running.

## Acceptance rule, frozen before running

| Verdict | Condition |
|---|---|
| `SURFACE_EXERCISED_RESTORATION_EXACT` | Every protocol method executes, and the two trajectories are exactly equal |
| `SURFACE_EXERCISED_RESTORATION_INEXACT` | Every protocol method executes, and the trajectories differ |
| `SURFACE_INCOMPLETE` | A protocol method could not be executed |
| `PROCESS_FAILED` | SUMO could not be started or did not terminate cleanly |

**`SURFACE_EXERCISED_RESTORATION_INEXACT` is a real and publishable result**, and it is the one with
consequences. It must not be retried with a loosened comparison, a tolerance, or a different metric until it
passes. A tolerance introduced after seeing a failure is the failure being hidden.

## Prohibited in this package

- Any TEST-split map.
- Any optimizer update or checkpoint load.
- Any unattended or background run; the process is started and closed within one attended invocation.
- Weakening the exact-equality comparison in step 5 after seeing its result.
- Drawing any conclusion about capture, feasibility or assistance.

## Resource limits

| | |
|---|---|
| SUMO process starts permitted | 2 |
| Simulated seconds permitted | 120 |
| Optimizer updates permitted | 0 |
| Checkpoint loads permitted | 0 |
| TEST split accesses permitted | 0 |
