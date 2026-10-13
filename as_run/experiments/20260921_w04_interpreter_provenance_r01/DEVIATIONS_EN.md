# Deviations

## D-1. This package was not planned

It was opened because a test failed for a reason unrelated to what was being tested. The novelty work of the
same day triggered it; the two are recorded separately because they are different claim classes.

## D-2. The defect was found by a disagreement, not by a check

No guard detected this. It surfaced only because two runners were used on the same source and returned
different answers. **A single runner would not have found it**, and the project had been using a single
runner. Recorded because the lesson is about method, not about this bug.

## D-3. The corrected guard is not proof that other guards are sound

One check was found inert on the pinned interpreter. Nothing here establishes that the rest are not. What
can be said is narrower: the guards that had **no test that they fire** are the ones exposed to this failure
mode, and `test_source_hygiene.py` is now the only one with such a test throughout.

**Open item:** audit the remaining guards for the same absence.

## D-4. pytest was not added as a dependency

The simpler fix would be `uv add --dev pytest`. It was not taken: the tests are `unittest.TestCase`
throughout, so `python -m unittest` is the native runner and needs nothing installed. Adding a dependency to
fix a provenance defect would enlarge the pinned environment to work around a runner that was never required.

The trade-off is stated rather than hidden: `unittest` reports less than `pytest` does on failure.

## D-5. No resource was consumed

No simulator start, no episode, no optimizer update, no checkpoint load, no TEST access.
