# Protocol — scan of the capture instants used by the hold audit (A-137, fifth review F5-2 and F5-5)

**Registered before launch, 5 October 2026.** Deterministic replays of sealed episodes; no new episode, no TEST city.

## Why

The fifth review (`reviews/20261005_fifth_review/REVIEW_ES.md`, F5-2) showed that the helper that returned the capture
instant of the hold audit, `scripts/audit_d06_persistence._witness`, does not reset a pursuer's run when the pursuer is
absent from a frame. On a constructed trace it returns 2.1 s where the first continuous 2 s run completes at 4.1 s. The
audit froze the pursuers at that instant, so a wrong instant would mean a hold audit started before a valid capture.
The review did not establish whether any of the 1,433 audited captures is affected. Traces were not stored, so the
question cannot be answered offline.

## What is run

Each of the 1,433 rows of `experiments/20261003_d06_persistence_audit_r01/results.jsonl` (PLB, junction ambush and
pursuit captures of the A-99 test, salt PE11, seven non-TEST cities) is replayed once: the natural run only, 300 s,
with the dispatch bookkeeping that was in force when the audit ran (`DISPATCH_MODE = "legacy"`, A-119). Script:
`scripts/scan_capture_instants.py`. A development check on the first 18 tasks was run before registration to test the
script (18 of 18 reproduced, written outside the package).

For each replay the script records:

1. the sealed instant and finisher of the audit row;
2. the earlier helper recomputed on the replayed trace;
3. the corrected extractor, `joint_interception.evaluation.capture_time.earliest_capture`, which resets a run when the
   pursuer or the evader is absent or a value is invalid;
4. the independent judge applied to each pursuer alone, `judge_earliest_capture`;
5. the frames in which each team vehicle is absent, separating gaps inside its record from a final disappearance;
6. the first invalid value of the trace, if any (non-finite, negative speed, non-positive dimension; F5-5);
7. the collisions with their times.

## Reading rule (fixed now)

- A capture is **unaffected** if the replay reproduces the sealed instant and finisher and the corrected extractor and
  the judge give the same instant. Its hold audit, its extended follow-up (addendum 1), its witness verification
  (addendum 2) and its active-escape probe (addendum 3), which all used that instant, then stand as sealed.
- A capture is **affected** if the corrected instant differs from the sealed one. Affected captures are listed by key.
  Their sealed rows are not edited and not replaced; their hold audit would be repeated at the corrected instant in a
  separate addendum, and the article would report both.
- A replay that does not reproduce the sealed instant, or that fails, is **not verified** and is listed.
- Counts of absent frames, invalid values and collisions are descriptive.

No threshold is tuned and nothing is selected. The outcome is reported whatever it is.

## Scope not covered

- Capture instants of the held-out TEST evaluation (`capture_t` in `20261003_test_confirmation_r01`) were computed by
  the same kind of helper. They are stored but enter no reported number, and TEST is not replayed.
- Training episodes of the learning studies cannot be replayed: the weights of each iteration were not stored.
