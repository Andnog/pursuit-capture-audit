# Scientific decision — offline delimitation (A-139; post hoc)

`DELIMITATION.json` holds the figures. Summary:

- **MAPPO-v3 training (sealed log).** 256 iterations, 16,384 attempted episodes. The number of valid episodes is
  determined uniquely in 192 iterations; overall it lies between 13,931 and 16,026. Between 6,492 and 7,399 sampled
  episodes did not reach the training objective (per run: about 1,000–1,230 in the six runs rewarded on OC, about
  120–140 in the two rewarded on proximity).
- **Captures on a decision tick (MAPPO-v2 test).** Learned controllers: 261 of 4,752 captures (5.5 %). PLB, which
  re-plans every second: 25 of 631 (4.0 %). Pursuit: 5 of 439 (1.1 %). A uniform spread over the tenths of a second
  would give 3.3 %.
- **Collisions in completed test rows.** First MAPPO study 0 of 9,984; MAPPO-v2 8 of 14,688; proximity study 0 of
  11,466; MAPPO-v3 0 of 22,904.
- **Erratum.** The registered design of the MAPPO-v3 test is 7 × 20 × 2 × 2 × 3 = 1,680 scheduled episodes per
  policy and 23,520 in all, which is what the sealed package contains (1,636 completed per policy). The figure 840 in
  its protocol is an arithmetic error.

**Reading.** The records bound how many training episodes could have trained a decision without a future, and show
that the capture-on-a-tick case is not rare. They cannot say which training episodes were affected, nor by how much
the trained policies changed. The measured incidence on the batches that can be replayed is in
`experiments/20261005_v3_first_batch_reconstruction_r01`.
