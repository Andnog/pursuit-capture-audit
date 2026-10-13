# Protocol — ambush-planner study r01 (A-94)

Frozen before any gated episode. Approved by the Research lead ("try to make them cooperate; time-boxed").
Question: does an explicit cooperative planner, the junction ambush with lane-level blocking (hammer and anvil),
produce cooperation on real cities where gate assignment and pursuit did not?

**Planner** (`src/joint_interception/native/ambush.py`, frozen at launch).
- Predicts the evader's next 4 junctions (greedy on its lead over the nearest pursuer).
- At the nearest junction where the team can occupy every passenger lane of every legal exit before the evader
  (conservative time model: 1.3 × free-flow + 3 s, margin 2 s), it sends blockers to stop in those lanes.
- The remaining pursuers chase.
- With no feasible junction, every pursuer chases.

The development history before launch is recorded in A-94 (three implementation fixes, development scenarios with salt
`DEVA` only).

**Setting.** 7 cities (4 TRAINING, 3 DEVELOPMENT), fresh salt `PA1`, 20 scenarios per city × 2 SUMO seeds, equal
speeds, legal interface, 300 s. Evader AVOIDANT and RANDOM. Teams 3 and 5. Runs: ambush team, pursuit team, and the
ambush planner with each single pursuer alone (same start).

**Primary S1 (cooperation).** Synergy = ambush team D06 − [1 − Π_i (1 − p_i)] over the ambush singles,
seed-averaged per scenario. Cooperation is detected in a cell if the Bonferroni-adjusted (4 cells) CI lower bound
is > 0.

**S2.** Ambush team − pursuit team.

**Descriptive.** Plan feasibility share, trap types, and the structural blockability of each network
(`STRUCTURAL_junction_blockability.json`: share of arrival edges whose junction can be closed lane by lane by 1/2/3/5
pursuers).

Executed in resumable chunks of at most 30 min. Budget ≈ 6 CPU-h. TEST closed.
