# MAPPO-v3: the learning block repeated with a corrected implementation (A-133, R4-A)

**Registered in:** `governance/AMENDMENTS_EN.md`, A-133, before any run.

**Why.** The fourth independent review found that, in all earlier learning studies, the critic's input was built
after the actions of the decision step (so the baseline depended on the actions it judged), and that sampling was not
controlled by the declared seed. Conclusions about fine-tuning drawn from those studies are withdrawn. This study
repeats the block with a corrected controller.

**Corrected controller** (`native/mappo_ambush_v3.py`, tests in `tests/test_mappo_v3.py`).
- The critic's global state is recorded before any agent of the step has chosen.
- Sampling uses the controller's own generator, seeded per episode; nothing global is read or consumed.
- The actor is sequential, as before, and is documented as such.

**Imitation starts.** The four stored imitation checkpoints of A-116 (MLP and KAN heads, seeds 1 and 2). Behaviour
cloning uses neither the critic nor sampling. The script refuses to start if a stored checkpoint is not its
imitation start.

**Arms.**
- **F, fixes only:** fine-tuning as in A-116 with the corrected controller. MLP and KAN heads, two seeds each.
- **W, fixes and critic warm-up:** as F, preceded by 256 sampled episodes with the actor frozen, on which the critic
  alone is fitted to Monte Carlo returns. MLP head, two seeds.
- **P, proximity reward:** as A-125 with the corrected controller: reward at the first body gap of 5 m or less,
  episode truncated there, fixed 2,048 episodes, no early stop. MLP head, two seeds.

Reward for F and W: +1 at OC capture (episode truncated there), −0.005 per decision, −1 on collision. Hyperparameters
as A-116: learning rate 3e-4, entropy 0.01, clip 0.2, 4 epochs, 64 episodes per update, GAE (0.99, 0.95); validation
every 512 episodes on 192 scenarios (salt PV23); for F and W at least 1,536 and at most 4,096 episodes, patience 4,
minimum gain 0.02 on the two-point moving average. Run order: W, P, F.

**Test** (salt PE23, seven non-TEST cities, 20 scenarios × 2 SUMO seeds × AVOIDANT/RANDOM × teams 3/5/7; 840 episodes
per policy): PLB, pursuit, the four imitation starts, the selected and final policy of every F and W run, the final
policies of P. A selected checkpoint that is its own start is not run twice. All policies are evaluated greedily and
scored under OC, body gap ≤ 5 m and centre distance ≤ 5 m.

**Primary 1.** Arm W: selected checkpoint minus its imitation start, OC, averaged over the two seeds per cell;
family-clustered 95 % lower bound > 0. (If the breaker keeps the start, the difference is zero and the primary is
not met.)

**Primary 2.** (Body-gap proximity − OC) of the final P policies minus the same gap for their imitation starts,
averaged over seeds per cell; family-clustered 95 % lower bound > 0.

**Secondary.** Primary 1's contrast for arm F (MLP, KAN); final minus start for every run; validation curves; W
against F; learned controllers against PLB; PLB against pursuit under each endpoint.

**Reading fixed in advance.**
- Two seeds per arm describe these runs; they do not estimate variability between training runs.
- A difference that is not detected is not a demonstration of equivalence.
- Whatever the outcome, earlier fine-tuning results are reported as obtained with a defective implementation.

**Execution note.** Before the run, the script was executed end to end outside the evidence tree with a reduced
configuration (16–32 training episodes per run, one validation scenario per setting, one test scenario per city and
team of 3). That check used the registered salts, so its 16 validation and 196 test episodes are a subset of the
registered sets. Nothing was tuned on it and the design above was not changed.
