# Scientific decision — first training batch of every MAPPO-v3 run, reconstructed (A-139)

**Run:** 6 October 2026, about 03:35 to 03:38 local time, one chunk, 9 workers. 512 scheduled replays; 499 valid and
13 placement failures (`ValueError: scenario could not place the team`), which are part of the original batches.
Nothing was trained.

## Reproduction (criterion fixed in the protocol)

**8 of 8 runs reproduced.** For every run, the success, OC and proximity rates of the reconstructed batch equal the
three rounded rates that the sealed log of MAPPO-v3 stores for iteration 1 (for example `W_mlp_s1`: 0.377, 0.377,
0.951, that is 23, 23 and 58 of 61 valid episodes). The figures below therefore describe the historical first batches.

## Incidence of the defects in those batches (earlier contract)

| Quantity | Count |
|---|---:|
| Valid episodes | 499 |
| Decisions trained by the earlier contract | 31,433 |
| of which had no future inside the episode | 201 (0.64 %) |
| Episodes with such a decision | 201 of 499 (40 %) |
| — decision at the 300 s horizon | 187 |
| — decision at a capture that fell on a decision tick (arms W and F) | 11 of 148 captures (7.4 %) |
| — decision at a first proximity that fell on a decision tick (arm P) | 3 of 117 |
| Episodes with a collision at any time | 0 |
| Episodes penalised for a collision outside the trained interval | 0 |
| Capture instants that differ between the earlier helper and the corrected extractor | 0 of 204 |
| Frames with a vehicle absent inside its record | 0 |
| Episodes ending by evader exit before the horizon | 47 |

Per run (valid; without future; captures on a tick): `W_mlp_s1` 61; 31; 1. `W_mlp_s2` 63; 28; 5. `P_mlp_s1` 62; 1; 0.
`P_mlp_s2` 63; 3; 0. `F_mlp_s1` 63; 33; 1. `F_mlp_s2` 62; 36; 1. `F_kan_s1` 63; 33; 1. `F_kan_s2` 62; 36; 2.

Under the corrected contract the same 499 episodes give 31,232 transitions: exactly the 201 decisions without a
future are dropped, and no other decision changes status.

## Reading

- **F5-1, horizon branch: frequent and small per episode.** In the runs rewarded on OC, about half of the episodes
  (186 of 374) ended at the horizon, and each of them trained one decision without a future, about one in a hundred
  of its decisions, with a time cost of −0.005 and a value target that the critic had to fit.
- **F5-1, capture-on-a-tick branch: not rare.** 11 of 148 captures (7.4 %) completed exactly on a decision tick, more
  than the 1 in 30 that a uniform spread would give. In those episodes the +1 went to the decision taken after the
  capture was complete, and the decision that led to the capture received only a bootstrapped share.
- **F5-1, collision branch: not observed.** No collision occurred in these 499 episodes, so the episode-level flag
  penalised nothing here. Its incidence in later batches is unknown.
- **F5-2: not observed.** No capture instant differs and no vehicle is absent inside its record.

## Limits

- One batch per run, sampled by the imitation starts. Later batches were sampled by updated policies whose weights
  were not stored; their incidence is bounded only by the sealed log (A-139, offline delimitation).
- These counts say how often the earlier contract assigned a reward to the wrong decision or trained a decision
  without a future. They do not say how much the trained policies changed because of it. That would need a
  repetition of training with the corrected loop.
- `scripts/train_caging_pilot.py` (changed by A-138 at 21:09 on 5 October, map identifiers of `assets/osm_b` only) is
  recorded in `inputs.json` at its current hash.
