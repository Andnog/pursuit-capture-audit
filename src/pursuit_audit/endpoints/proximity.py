"""Proximity endpoints: success at the first instant a distance falls to a threshold.

Which distance is part of the rule. Three are in use and they are not interchangeable:

- ``body``: between the two vehicle bodies;
- ``centre``: between the two body centres;
- ``front``: between the two front bumpers, which is what a simulator's "position" usually is.

Each is a strategy registered under its name, so a study that uses another distance can add it
without touching the scoring code.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from ..domain.geometry import Body, body_gap_m, centre_distance_m, front_distance_m
from ..domain.trace import Frame

Distance = Callable[[Body, Body], float]

DISTANCES: dict[str, Distance] = {
    "body": body_gap_m,
    "centre": centre_distance_m,
    "front": front_distance_m,
}


def register_distance(name: str, distance: Distance) -> None:
    """Register a distance under a name, for use in a `ProximityRule`.

    Raises:
        ValueError: If the name is already taken.
    """
    if name in DISTANCES:
        raise ValueError(f"distance {name!r} is already registered")
    DISTANCES[name] = distance


@dataclass(frozen=True)
class ProximityRule:
    """A proximity endpoint: a distance and the threshold at which it counts as a capture."""

    threshold_m: float
    kind: str = "body"

    def __post_init__(self) -> None:
        if self.kind not in DISTANCES:
            known = ", ".join(sorted(DISTANCES))
            raise ValueError(f"unknown distance kind {self.kind!r}; known kinds: {known}")

    @property
    def name(self) -> str:
        """Return a short label, such as ``body_5m``."""
        return f"{self.kind}_{self.threshold_m:g}m"

    def distance(self, pursuer: Body, evader: Body) -> float:
        """Return the rule's distance between a pursuer and the evader."""
        return DISTANCES[self.kind](pursuer, evader)


@dataclass
class ProximityResult:
    """The verdict of a proximity rule on one trace."""

    reached: bool
    time_s: float | None = None
    pursuer: str | None = None
    minimum_m: float = math.inf


def proximity(
    frames: list[Frame],
    evader: str,
    rule: ProximityRule,
    pursuers: list[str] | None = None,
) -> ProximityResult:
    """Find the first instant at which a pursuer is within the rule's threshold of the evader."""
    result = ProximityResult(reached=False)
    for frame in frames:
        evader_body = frame.vehicles.get(evader)
        if evader_body is None or not evader_body.is_valid():
            continue
        for pursuer_id, pursuer_body in sorted(frame.vehicles.items()):
            if pursuer_id == evader or not pursuer_body.is_valid():
                continue
            if pursuers is not None and pursuer_id not in pursuers:
                continue
            distance = rule.distance(pursuer_body, evader_body)
            result.minimum_m = min(result.minimum_m, distance)
            if distance <= rule.threshold_m and not result.reached:
                result.reached, result.time_s, result.pursuer = True, frame.time_s, pursuer_id
    return result
