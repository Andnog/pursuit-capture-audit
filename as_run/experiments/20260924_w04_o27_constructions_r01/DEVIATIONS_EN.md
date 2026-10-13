# Deviations

## D-1. The coordination criterion was amended before any real case, by the Research lead

`PROTOCOL_AMENDMENT_EN.md`. A synthetic control showed the `b1`-only rule certifying a single-pursuer capture.

## D-2. The declared model changed eight times before the run, and has known defects after it

Each change fixed a defect found by reading a failure on a baseline or a control, each is under a test, and
all preceded the first real case. After the run, two classes of defect remain known: chained internal lanes,
and emergency braking or persistent overlap under some construction maneuvers.

## D-3. The runner did not record what stopped each search, nor why verifications failed

Recovered by a diagnostic rerun on identical code, recorded as analysis and not as a second attempt at the
gate. The rerun reproduced 5 of 8 cases exactly; the other 3 hit their CPU budget.

## D-4. The reproducibility caveat recorded before the run materialized

A search that stops on CPU time depends on machine speed. Every verified result remains deterministic from its
recorded plan.

## D-5. Nothing native, no TEST
