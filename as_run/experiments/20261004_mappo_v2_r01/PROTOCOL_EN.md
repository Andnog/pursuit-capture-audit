# Protocol — MAPPO v2 r01 (A-116)

Pre-registered in A-116 before launch; Research lead's explicit authorisation to reopen learning once. Script
`scripts/train_mappo_v2.py` (tests `tests/test_mappo_v2.py`, 9 passing), controller `native/mappo_ambush_v2.py`.
Smoke run on a scratch package verified demos → BC → PPO → test → summary. Teacher fidelity in smoke: 0.1 % of
planner blocks unrepresentable with 40 slots. Two seeds per head; run breaker only; test salt PE17 on 7 non-TEST
cities; primary per head: best-validation v2 checkpoint − PLB, family-clustered, 97.5 %.
