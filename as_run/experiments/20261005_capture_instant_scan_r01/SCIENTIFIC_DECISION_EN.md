# Scientific decision — scan of the capture instants used by the hold audit (A-139)

**Run:** 5 October 2026, 21:10 to about 22:20 local time, one chunk, 9 workers. 1,433 scheduled replays, 1,433
completed, 0 failed. The protocol and `inputs.json` of this package call the amendment "A-137"; it is A-139 (the label
was assigned concurrently to other work, see A-139 in `governance/AMENDMENTS_EN.md`).

## Result, under the reading rule fixed in the protocol

| Check | Count |
|---|---:|
| Replay reproduces the sealed capture instant and finisher | 1,433 of 1,433 |
| Episode judged a capture by the engine's judge | 1,433 of 1,433 |
| Sealed instant = earlier helper = corrected extractor = judge (per pursuer) | 1,433 of 1,433 |
| Corrected extractor and judge name the same pursuer | 1,433 of 1,433 |
| Captures **affected** (corrected instant differs from the sealed one) | **0** |
| Replays not verified | 0 |

**Decision.** No capture instant of the hold audit is affected by finding F5-2. The hold audit
(`20261003_d06_persistence_audit_r01`), the completion of its follow-up (addendum 1), the witness verification
(addendum 2) and the active-escape probe (addendum 3), which all start from these instants, stand as sealed. No hold
audit is repeated.

## What the scan also shows

- **The condition that breaks the earlier helper does occur.** In 4 of 1,433 traces a pursuer is absent from some
  frames and present again later: `p4` for 25 frames (2.5 s) in the two SUMO replicates of
  `plus_opt|sapporo_grid|14|AVOIDANT|5`, and `p6` for 4 frames (0.4 s) in the two replicates of
  `plus_opt|washington_downtown|6|AVOIDANT|7`. In all four the absent pursuer is not the finisher, and the four
  computations of the instant agree. The reviewer's counterexample is therefore not hypothetical for this engine; it
  did not change any audited instant.
- In 29 traces the evader is absent in the last frame only (it leaves the network at the end of the trace); this is a
  final disappearance, not a gap.
- **Invalid values (F5-5):** none in 4,284,032 frames (no non-finite value, no negative speed, no non-positive
  dimension).
- **Collisions:** none in the 1,433 episodes.

## Limits

- The scan covers the captures of the hold audit. Other historical traces were not stored and were not replayed. In
  particular the capture instants stored by the held-out TEST evaluation were computed by a helper of the same kind;
  they enter no reported number and TEST was not replayed.
- Four agreeing computations show that the instant is the first complete 2 s run under the predicate; they say
  nothing new about what the predicate measures.
- `scripts/train_caging_pilot.py`, imported through `audit_cage_certificate.py`, was changed by A-138 at 21:09,
  before this run started and after the development check; it is not in `inputs.json`. The change adds map
  identifiers of `assets/osm_b` with `setdefault` and cannot alter the seven maps used here. Every replay reproduced
  its sealed instant.
- The development check of 18 replays mentioned in the protocol was written outside the package and is not evidence.
