# Protocol — first training batch of every MAPPO-v3 run, reconstructed with a ledger (A-139, fifth review F5-1 and F5-6)

**Registered before launch, 5 October 2026.** Deterministic replays of training episodes of a sealed study. Nothing is
trained. TRAINING cities only (Adelaide, Toronto, Washington, Seattle); no TEST city and no held-out B city.

## Why

The fifth review found that the training loop of `scripts/train_mappo_v3.py` trained decisions that had no future
inside the episode and applied the collision penalty from an episode-level flag (F5-1), and that its log cannot
reconstruct the denominators and events of training (F5-6). The review reproduced the first defect on eight rollouts
and on constructed cases, and did not measure its incidence.

The weights of the training iterations of MAPPO-v3 were not stored, so its training episodes cannot be replayed, with
one exception. The first batch of a run was sampled with the stored imitation start (the critic warm-up of arm W
changes the critic only, and the actor alone determines the sampled actions), from scenarios, SUMO seeds and sampling
seeds that the script defines.

## What is run

`scripts/reconstruct_v3_first_batches.py` replays the first 64 sampled episodes of each of the eight runs
(`train_mappo_v3.train_tasks(name, start, 0, 64)`; 512 episodes; salts `PT23…`) with the controller of MAPPO-v3, and
passes each trace through `train_mappo_v4.measure`. That function computes the corrected capture instant and the
transitions of the corrected contract, and records what the earlier contract did with the same episode: the decisions
it trained, how many of them had no future inside the episode, whether the capture fell on a decision tick, whether a
collision outside the trained interval was penalised, and whether the earlier capture instant differs from the
corrected one.

## Reproduction criterion (fixed now)

The sealed log of MAPPO-v3 stores, for iteration 1 of every run, the success, OC and proximity rates of its batch,
rounded to three decimals. A run is **reproduced** if the reconstructed batch gives the same three rounded rates. The
incidence figures of a run that is not reproduced are reported as such and are not used to describe the historical
batch.

## Outcomes (descriptive; no hypothesis test)

Per run and overall: attempted, failed and valid episodes; end reasons (objective, horizon, evader exit); decisions
trained by the earlier contract and how many had no future; captures on a decision tick; episodes with a collision,
inside and outside the trained interval; capture instants that differ; frames with a vehicle absent inside its record.

## Limits

One batch per run describes the start of training. Later batches were sampled by updated policies that were not
stored. The figures do not say how much the defects changed the trained policies.
