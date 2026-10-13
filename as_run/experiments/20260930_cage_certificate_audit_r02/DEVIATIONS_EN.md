# Deviations — audit r02

1. r01 is void: M1 was implemented as "the evader is on an edge whose origin was a gate", which includes the edge it
   already occupied at certification. r02 implements the protocol text ("enters"): only edges entered after
   certification count.
2. Added after r01 and before r02, descriptive only: M1b (the evader leaves the network without crossing a gate),
   the count of certified cages with no gate at all, the gate crossed at escape, and per-step records of the window
   (`records.jsonl.gz`) for diagnosis. The primary reading (hold-condition M1, upper bound ≤ 0.10) is unchanged.
3. Known from r01 (it does not depend on M1): 28 of 427 certified cages had an empty gate set and 42 evaders left the
   network after certification. These are reported, not re-defined.
