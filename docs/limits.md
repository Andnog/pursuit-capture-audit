# Limits

What the study does not show, grouped by the kind of validity that each limit affects.

**What operational capture measures.** It is an operational near-stop endpoint. It admits slow following behind a
pursuer (about 3 % of episodes for a team that does not pursue), it requires no rear blocker, and its band of 0.3
to 2 m is tied to the minimum gap that the simulated evader keeps. Its persistence was tested against scripted
evaders and the simulator's own lane changing; an active lane-change probe released 15 of 1 433 captures.
Reversing and U-turns in the middle of a street were not simulated, which favours blocking.

**The simulator.** Every result comes from one microscopic simulator. SUMO moves vehicles along lanes with a
car-following law and discrete lane changes. It has no tyre or steering dynamics, and its drivers do not ram, mount
kerbs or drive against traffic. Two checks probe this from inside the simulator: with a different position update
and with a different car-following model, predictive lane blocking minus pursuit is +0.140 [0.103, 0.177] and
+0.118 [0.079, 0.158], against +0.126 [0.090, 0.164] with the model used throughout; with background traffic it is
+0.094 [0.060, 0.130]. These checks do not replace a different simulator or field data.

**The evaders.** All are scripted and decide from the current positions of the pursuers. The evader tuned against
the controller is a rule with seven hand-chosen features and 33 candidates; a stronger evader may exist. Learned
evaders were not evaluated, and no game-theoretic best response was computed.

**Inference.** There are eight held-out cities, in two sets that were each evaluated once and are not pooled; the
advantage of the controller differs between the sets, and we did not identify why. Some cities of the development
phase informed design. Registration is internal, through sealed packages with checksums; it is not externally
timestamped.

**The published environments.** The audits used the released configurations, which differ from the ones reported
in those articles, did not train the published learners, and cover two environments of one research group.

**Reproducibility.** Packages store the hashes of their sources, not complete copies, so the code at launch of some
earlier studies cannot be recovered in full. Replays reproduced every sealed outcome that was run again.
