# Deviations

## D-1. The open-loop arm was the wrong experiment, and it was A-40's only arm

A-40 commanded a time-indexed profile and measured where the vehicle landed. Once a vehicle falls behind,
every later command corresponds to a position it is not at, so an early deviation is amplified by the
execution method rather than by the physics.

The non-monotone errors in the first run of this package made that visible: Seattle route 0 gave +34.6 s at
`1.0x`, +3.1 s at `1.5x`, and **+62.1 s at `2.0x`**. A more relaxed schedule arriving far later is not
plausible physics; it is a symptom of open-loop execution.

The closed-loop arm was added for that reason, and it is what the verdict is now judged on. **The open-loop
arm is kept and reported**, because A-40's numbers were open-loop and discarding it would make the two
packages incomparable.

The arms are not the same experiment: they differ on 22 of 48 rows.

## D-2. A-40's mechanism claim is withdrawn by this package

A junction census on one route is not evidence of a mechanism. The correlation over 48 measurements is 0.02.
Recorded prominently rather than quietly dropped, because A-40 stated it with confidence and a reader of the
sealed package would otherwise carry it forward.

## D-3. The declared process limit was respected

150 permitted, **116** used. The previous two packages each exceeded their own limit; this one declared
headroom in advance for exactly the case that occurred — a first arm that turned out to need a second.

## D-4. Route and map selection was fixed before any error was seen

Four TRAINING maps named in the protocol; routes taken in the deterministic order the search returns them,
which depends only on edge identifiers. No route was chosen or dropped after its error was known.

## D-5. The feasibility detector was checked before its output was believed

The logged values were consistent with a boundary artifact. Probing `arrival_at` at and around the earliest
possible time established that it returns a profile at exactly that time and `None` only strictly below.
Checked before the result was written up, not after a reviewer asked.

## D-6. The first replication run is superseded, not hidden

The first run used `--routes-per-map 4` and the open-loop arm only, giving 48 open-loop measurements. Its
rows are preserved in `arm_open_loop.json`. The sealed run uses 3 routes per map with both arms.
