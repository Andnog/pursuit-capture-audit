# Deviations

## D-1. None on resources

Six SUMO process starts were permitted; **three** were used. Three hundred simulated seconds were permitted;
90.3 were used. The declared diagnostic arm was not needed, because the primary question passed under SUMO's
defaults.

The previous package (`20260922_w04_traci_first_execution_r01`) exceeded a limit of two because a failure
pointed at a cause worth testing. **That headroom was declared in advance here instead of taken later**, and
then went unused.

## D-2. The control was specified before the result, not after

`Q3` — that the arms genuinely differ after the divergence point — was written into the runner in the same
edit as `Q2`, before either was run. A control added after seeing `Q2` pass would carry far less weight, and
`Q2` alone is the kind of check that passes for the wrong reason.

## D-3. The runner reuses helpers from the previous package's script

`pick_route`, `digest`, `first_difference` and `training_map` are imported from
`scripts/run_traci_first_execution.py` rather than copied. The comparison function is therefore **literally
the same code** that produced the negative result in A-37, which is the point: a positive result here cannot
come from a quietly different comparison.

## D-4. A negative result would have been reported as readily

The protocol fixed `NOT_REPRODUCIBLE` and `REPRODUCIBLE_PREFIX_NOT_COUPLED` as publishable verdicts before
the run, and recorded that either would mean the audit design must change again. The rule was written when
the expected outcome was genuinely unknown — the immediately preceding package on the same subsystem had
returned a negative.

## D-5. Bounded and attended

No unattended run, no background process. Every arm closes its connection in a `finally` block. No TEST map,
no optimizer update, no checkpoint load.
