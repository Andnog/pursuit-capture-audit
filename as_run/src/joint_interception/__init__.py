"""Joint interception opportunities: research implementation.

This package is written afresh for the `doctoral_joint_interception` project. It imports
nothing from any legacy runtime and depends only on the Python standard library at W1.

Implemented at W1 (finite abstraction only):
  - opportunities.types        verdict algebra and the Opportunity record
  - opportunities.reachability  canonical interval unions and approximation direction
  - opportunities.compatibility joint and pairwise compatibility predicates
  - policies.memory             commitment memory and the selection rule
  - evaluation.assistance_audit assistance accounting over finite outcome tables

Not implemented: simulator adapter, evader, safety admission against real geometry,
capture judge, learners, metrics, statistics. Those are W2 and later.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
