# Deviations

## D-1. The first run was void, and the protocol caught it

Every measured gap read −25.0 m against intended gaps of 0.30–3.0 m. Both vehicles had departed at position 0,
the second was plausibly never inserted, and `moveTo` did not apply. Preserved as `first_run_record.json`.

Without the protocol's rule to read the gap back, the run would have reported **no collision at any gap** —
the opposite of the truth, and a result that would have validated D06.

## D-2. A second question was added inside the declared limit

The first finding raised whether changing collision detection would suffice. It would not, and that is only
knowable by measuring car-following. One of the two remaining permitted starts was used for it. Five starts
of six, two of them void.

## D-3. No remedy was chosen

D06 is frozen and is the Research lead's. The admission module's minGap gap is recorded and deliberately not
patched, because the right patch depends on the remedy.

## D-4. Nothing was relaxed

Safety checks stayed on. No TEST map, optimizer update or checkpoint load.
