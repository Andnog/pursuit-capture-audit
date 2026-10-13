# Deviations

## D-1. The declared limit of two SUMO process starts was exceeded — three were used

`PROTOCOL_EN.md` permitted **2**. Three arms ran, so **3** processes were started.

**Why.** Arm A failed. Arm B isolated randomness and also failed, with a signature — identical speeds,
positions off by a constant 0.003 m — that pointed at write precision. Arm C tested that directly.

**What was not done.** The protocol file was **not edited**. It stays frozen as written, with the limit it
declared, and this deviation stands against it. The alternative — quietly raising a limit I had written
hours earlier — is exactly the drift the resource ledger exists to prevent.

**What was not relaxed.** The exact-equality comparison, unchanged across all three arms. The prohibition on
TEST maps, on optimizer updates, on checkpoint loads and on unattended running, all observed. Total cost:
three attended processes, 78.3 simulated seconds, 0.48 CPU seconds.

**Where it stopped.** A fourth arm — determinism from a fresh start — was **not** run, though it is cheap and
the question is open. One deviation in a package can be justified; a second would make the declared limit
decorative. That question gets its own package.

## D-2. The first run is preserved verbatim

`first_run_record.json` holds the single-arm run exactly as executed, before the diagnostic arms existed.
Its verdict was `SURFACE_EXERCISED_RESTORATION_INEXACT` and it stands. Nothing was retried in the hope of a
different answer: arm A is byte-for-byte the same experiment, and it failed the same way.

## D-3. The runner's automated diagnosis is wrong and is kept

It concluded the divergence was *"not explained by write precision"*. It was. The runner could only compare
arm outcomes, and raising `--precision` did not reach the fields that mattered. Both the wrong automated
statement and the corrected evidenced one are in `result.json`.

## D-4. Two defects in code written in this package, found before running

`TraciBackend` was written with `_classes` and `_state_path` as **class-level mutable attributes**, which
every instance in a process would have shared — precisely the silent cross-run coupling the assistance audit
must not have. Moved to per-instance initialisation. `math` was used without being imported.

Both were caught by reading the code and by lint before any SUMO process started, not by a test. **There is
still no test that would have caught the shared-mutable-state defect.**

## D-5. A `--seed` is passed and its effect is unverified

`--seed 20260922` is on every command line. Whether SUMO honours it for the full trajectory is the fresh-start
determinism question, which is untested. The flag is recorded, not relied upon.

## D-6. Bounded and attended

No unattended run, no background process, no heartbeat. Each process was started and closed within one
attended invocation, and the `finally` block closes the connection on any path.
