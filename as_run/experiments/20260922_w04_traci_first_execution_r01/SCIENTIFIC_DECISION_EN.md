# Decision — first execution of the TraCI call surface

**Claim class: software correctness, plus one empirical property of SUMO.** No capture was attempted, no
success scored, no optimizer run, no checkpoint loaded, no TEST map opened. **Nothing here supports a claim
about physical feasibility or capture ability**, and nothing here discharges O22.

## Verdict

`SURFACE_EXERCISED_RESTORATION_INEXACT`.

The call surface works. **The assumption underneath the assistance audit does not.**

## The surface

Every method of the `SimulatorBackend` protocol executed against a live SUMO 1.21.0 process over the TraCI
socket, on `adelaide_cbd`, a **TRAINING** map, opened read-only and neither copied nor modified.

One result worth keeping: **a commanded speed is a request, not a guarantee.** SUMO's safety layer was left
ON, so `setSpeed` may execute slower than asked. The backend reads the executed speed back rather than
assuming it. That is the same proposed-versus-executed separation the task contract already requires of the
action layer, and it now holds against a real simulator rather than a fixture.

## The finding

`state_restoration` was recorded as `SUPPORTED_AGAINST_A_FIXTURE_NOT_AGAINST_SUMO`. The fixture restores
exactly by construction. **SUMO does not.**

Three arms, all compared by **exact equality**, never within a tolerance:

| Arm | Configuration | Exact? |
|---|---|---|
| A | SUMO defaults (Krauss `sigma` = 0.5, stochastic) | **No** |
| B | Deterministic car-following (`sigma` = 0) | **No** |
| C | `sigma` = 0 **and** `--precision 12` | **No** |

### Cause, established from the state files the run wrote

SUMO 1.21.0 serialises a vehicle's `pos` and `speed` with a **fixed two-decimal format**, and **`--precision`
does not govern those fields**. Arm C proves it: `departPos` went to twelve decimals while `pos` and `speed`
stayed at two.

```
<vehicle id="p2" ... departPos="25.000000000000" ... pos="31.23 26.23 1.39" speed="13.89 13.89" .../>
```

So `loadState` restores a state **rounded to 1 cm and 1 cm/s**, and the simulation then proceeds *correctly
from the wrong state*.

**The arithmetic closes exactly.** Saved position 31.23 m; one step at 13.89 m/s over 0.1 s gives
`31.23 + 1.389 = 32.619` m — precisely the restored value observed. The true value was 32.622 m. Residual
**0.003 m**, the rounding error and nothing else. Arms B and C are numerically identical, as they must be if
the flag never reaches these fields.

**This is divergence by construction, not by chance.** No seed and no determinism setting repairs it.

## Consequence

**The assistance audit's replay coupling cannot rest on `saveState` / `loadState`.**

The audit compares two arms from a shared prefix. If restoring that prefix already perturbs the state by a
centimetre, the measured contrast confounds the intervention with a restoration artefact. The contrast
bounds are *logical*, not statistical — they cannot absorb an unmodelled perturbation by widening.

**The audit design must change.** The obvious candidate is replay by **re-execution** from the episode start
under a fixed seed and an identical command sequence, rather than by state restore. **Whether SUMO is
deterministic from a fresh start is a different question**, and it gets its own frozen protocol and
acceptance rule rather than being folded into this package.

## What the runner got wrong, kept alongside what is right

The runner's automated diagnosis concluded *"not explained by randomness or by write precision"*, because
raising `--precision` changed nothing. **Raising the flag did not change the fields that matter.** The
corrected diagnosis comes from parsing the state files the run itself wrote — analysis of existing artifacts,
not a new execution. Both statements are preserved in `result.json`.

An automated verdict that can only compare arm outcomes will misattribute a cause whenever the knob it turns
is the wrong knob. Worth remembering before trusting the next one.

## What this does not establish

- Nothing about capture, assistance, feasibility or any benefit.
- Nothing about O22, which remains open.
- Nothing about whether SUMO is deterministic from a fresh start — untested here.
- Nothing about maps other than `adelaide_cbd`, or about more than three vehicles on one route.
