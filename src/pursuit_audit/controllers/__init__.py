"""Decision kernels of the pursuit controllers, as pure functions.

A controller of the study is a loop around the simulator: it reads the state, decides, and sends
commands. The decisions themselves need no simulator. They are written here as functions of plain
values (a road graph, travel times, positions), so that they can be read, tested and reused:

- `prediction`: the path that the evader is predicted to take;
- `blocking`: which pursuer closes which exit lane of a junction, and whether the team is in time;
- `prepositioning`: where the pursuers that are not needed for an ambush go to wait.

Each kernel is tested against the planner that ran in the study (`as_run/src/.../native`), on
random road graphs.
"""

from .blocking import Assignment, Lane, assign_blockers, stop_point_cost
from .prediction import Edge, Link, PathStep, RoadGraph, exit_order, predict_path
from .prepositioning import PrepositioningRule, Target, preposition

__all__ = [
    "Assignment",
    "Edge",
    "Lane",
    "Link",
    "PathStep",
    "PrepositioningRule",
    "RoadGraph",
    "Target",
    "assign_blockers",
    "exit_order",
    "predict_path",
    "preposition",
    "stop_point_cost",
]
