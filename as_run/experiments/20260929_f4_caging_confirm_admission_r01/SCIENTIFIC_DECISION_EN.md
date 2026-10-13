# Decision — F4 r01: VOID (crash)
The run stopped after 2,004 of 2,880 runs: the admission check queried the lane of a pursuer parked off the lane (no
lane id). Fixed in `native/engine.py`; r02 repeats F4 unchanged otherwise. The partial results are not analysed.
