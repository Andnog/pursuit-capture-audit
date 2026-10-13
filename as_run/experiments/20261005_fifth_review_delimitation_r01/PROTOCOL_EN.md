# Offline delimitation of the fifth review's findings from sealed records (A-139; post hoc)

**Post hoc and descriptive.** Written on 5 October 2026 and run after the figures had been seen during development of
the script; nothing here was registered before it was computed. `scripts/delimit_fifth_review.py` reads sealed logs
and result files and simulates nothing.

It reports what the retained records can reconstruct about the training of the learning studies, and what they
cannot:

1. **Denominators of MAPPO-v3 training.** The sealed log stores, per iteration, the success, OC and proximity rates
   of the 64 attempted episodes, rounded to three decimals, and not the number of valid episodes. A denominator
   n ≤ 64 is a candidate if each of the three rates equals round(k / n, 3) for some integer k. The script reports in
   how many iterations the candidate is unique, the range of valid episodes, and the range of episodes that did not
   reach the training objective (each of which, if it ran to the horizon, trained one decision without a future under
   the earlier contract).
2. **Captures on a decision tick.** The test rows of MAPPO-v2 store the capture instant. The script counts the
   captures whose instant is a multiple of the 3 s decision period, for the learned controllers (which decide every
   3 s from 0 s), and for PLB and pursuit as a reference.
3. **Collisions.** The number of completed test rows with the collision flag, in the four learning packages.
4. **Erratum.** The arithmetic of the MAPPO-v3 test schedule against the figure in its sealed protocol.

Limits: the candidate denominators assume that the logged rates were computed over the same valid episodes, which
the source confirms (`train_mappo_v3.rate`). Test rows describe greedy evaluation, not sampled training episodes.
