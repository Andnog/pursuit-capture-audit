"""Simulator backends, adapter, snapshot and evader.

The adapter is written against the `SimulatorBackend` protocol rather than against TraCI
directly, so its contract behaviour can be validated without starting a simulator. W3
validates it offline; the TraCI call surface is exercised for the first time at W4, under
that stage's gate.
"""
