# Post hoc comparison of the two held-out evaluations

**Status: post hoc, descriptive.** Written on 6 October 2026 after the results of TEST (A-110) and of HELD-OUT B
(A-138) had both been read. Nothing here is confirmatory, no interval is corrected for multiplicity, and no episode
is run.

**Why.** The registered primary of HELD-OUT B is met with an estimate smaller than the TEST estimate. A reader will
ask whether the two differ by more than sampling error and which cities carry the result.

**What is computed** (`scripts/posthoc_heldout_b_vs_test.py`, from the two sealed `results.jsonl`).
- Each contrast in each set with the same code path and pooling as the HELD-OUT B summary (AVOIDANT and RANDOM
  evaders, teams of 3, 5 and 7, family-clustered 95 % percentile intervals).
- TEST minus HELD-OUT B for each contrast: the two sets are resampled independently by family, 10,000 times.
- Per-city rates and PLB − pursuit for the eight cities.

**What is not done.** The two sets are not pooled into one estimate (A-138 registered that they would not be). No
cause is tested for the difference between cities.

**Check of the code path.** On TEST it returns +0.145 for PLB − pursuit and +0.102 [0.053, 0.151] for PLB − junction
ambush, the figures of the sealed TEST analysis. The TEST body-gap contrast is +0.666 here and +0.679 in the sealed
TEST analysis because that one pooled three evaders and this one pools two, as HELD-OUT B registered.
