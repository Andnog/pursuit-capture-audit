# Decision — fresh-start determinism and prefix coupling

**Claim class: one empirical property of SUMO.** No capture, no evader, no learning, no optimizer, no
checkpoint, no TEST map. **Nothing here supports a claim about physical feasibility or capture ability**, and
nothing here discharges O22.

## Verdict

`REPRODUCIBLE_AND_PREFIX_COUPLED`. **Replay by re-execution is viable.** The assistance audit is recoverable.

## What was asked, and answered

| | Question | Result |
|---|---|---|
| **Q1** | Two fresh starts, same seed, same commands — identical? | **Yes, exactly** |
| **Q2** | Two fresh starts identical up to decision `k`, different after — is the prefix still exactly equal? | **Yes, exactly** |
| **Q3** | *(control)* Do the arms actually differ after `k`? | **Yes** |

All comparisons by exact equality, never a tolerance.

**Q3 matters as much as the others.** Without it Q2 would be vacuous: a prefix trivially matches if the
command change had no effect. It had one — 3.56 m of separation on `p1` at the very first frame past the
divergence point.

## The result that was not expected

**Q1 passed under SUMO's own defaults**, with Krauss driver imperfection at its stochastic `sigma = 0.5`.
The declared diagnostic arm with deterministic car-following was **never needed** and did not run.

So SUMO's randomness is *seeded and reproducible across fresh starts*. It is not reproducible across
`loadState` — which is exactly the asymmetry that killed the previous design (A-37) and rescues this one.
**The random stream is deterministic; the state file merely fails to carry it, along with the two decimals it
also fails to carry.**

## Consequence for the assistance audit

The audit compares two arms from a shared prefix and needs that prefix identical. It now has a mechanism:
**re-execute the prefix rather than restore it.**

The contrast bounds stay **logical, not statistical**, because the prefix is exactly equal rather than
approximately so. Nothing has to be widened to absorb a restoration artefact, because there is no
restoration.

**Cost, stated plainly.** Re-execution is `O(prefix)` per comparison where restore was `O(1)`. For a 300 s
episode compared at many decision points this is a real budget item, and it should be planned for rather than
discovered later. Measured here: 90.3 simulated seconds across three arms cost 0.237 s of CPU, so the cost is
small in absolute terms at this scale.

## Limits of this result

Stated because they bound what may be built on it:

- **Three vehicles, one route, one map (`adelaide_cbd`), thirty decisions.** Nothing about larger teams,
  multiple routes, or other networks.
- **No vehicle entered or left the network** during the run. Insertion and removal are events that could
  interact with the random stream, and they are **untested**.
- **No evader, no learning, no selection.** Commands were a scripted function of the decision index.
- **The divergent arm issued the same number of TraCI calls**, differing only in value. This does not
  threaten Q2 — the prefix is by definition before any difference — but arms that differ in the *number* of
  calls after `k` are untested for their own post-divergence behaviour.
- **One SUMO version, one platform.** 1.21.0 over the TraCI socket, `libsumo` unavailable.

## What this does not establish

Nothing about capture, assistance, feasibility or benefit. O22 remains open. The interaction half of the
constructive problem remains unimplemented.
