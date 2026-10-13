# Protocol — MAPPO trained on the proximity endpoint r01 (A-125)

Pre-registered in A-125 (with its clarification) before any run. Script `scripts/train_mappo_prox.py`. Same MAPPO as
A-116 (MLP actor, the A-116 demonstrations, BC with the same seeds), fine-tuned for a fixed 2,048 episodes per seed
(two seeds) with reward +1 at the first instant any pursuer is within 5 m (body gap) of the evader; the episode is
truncated there. Test: salt PE19, 7 non-TEST cities, AVOIDANT/RANDOM, teams 3/5/7, 20 × 2; methods PLB, pursuit,
MAPPO-OC (A-116 selected MLP), and the best-validation and final checkpoints of both proximity runs; every episode
scored under OC, body ≤ 5 m and centre ≤ 5 m. Primary: (proximity − OC) of the final proximity-trained policies minus
the same gap for MAPPO-OC, family-clustered 95 % lower bound > 0. Smoke run on a scratch package completed end to end.
