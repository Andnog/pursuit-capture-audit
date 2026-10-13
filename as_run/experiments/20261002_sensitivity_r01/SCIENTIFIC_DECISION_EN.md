# Scientific decision — sensitivity study r01

**VOID (harness defect).** `Store.run` called the episode function of `run_ambush_optimization.py`, whose argument
layout differs: the pursuer speed factor (1.0) was read as the "single pursuer" argument, so every episode ran with
**no pursuers** (0 captures in 13,627 episodes). The fix passes the study's own episode function and asserts a valid
speed factor. The study is repeated unchanged as r02. Kept for the record.
