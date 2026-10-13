"""The Specification pattern for capture rules.

A capture rule is a conjunction of conditions on a pursuer and an evader at one instant. Writing
each condition as a small object, and the rule as their composition, keeps three things apart that
studies often merge: what is measured (`PairState`), what is required of it (`Condition`), and how
long it must hold (the dwell, in `operational.py`). It also lets a rule say *which* condition
failed, which is what a reader needs in order to understand a success rate.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ..domain.geometry import Body, body_gap_m, heading_difference_rad


@dataclass(frozen=True)
class PairState:
    """What a capture rule may look at: one pursuer and the evader at one instant.

    Attributes:
        valid: Whether both bodies carry finite values in their physical range.
        gap_m: Smallest distance between the two bodies; 0 if they overlap.
        pursuer_speed_mps: Speed of the pursuer.
        evader_speed_mps: Speed of the evader.
        heading_difference_rad: Absolute difference of the headings, in ``[0, pi]``.
        along_m: Position of the pursuer ahead of the evader, along the pursuer's heading.
        lateral_m: Offset of the evader from the pursuer's longitudinal axis.
    """

    valid: bool
    gap_m: float
    pursuer_speed_mps: float
    evader_speed_mps: float
    heading_difference_rad: float
    along_m: float
    lateral_m: float

    @classmethod
    def measure(cls, pursuer: Body, evader: Body) -> PairState:
        """Measure a pursuer and an evader once, for every condition of a rule."""
        if not (pursuer.is_valid() and evader.is_valid()):
            return cls(False, math.nan, math.nan, math.nan, math.nan, math.nan, math.nan)
        dx, dy = pursuer.x - evader.x, pursuer.y - evader.y
        cos_h, sin_h = math.cos(pursuer.heading_rad), math.sin(pursuer.heading_rad)
        return cls(
            valid=True,
            gap_m=body_gap_m(pursuer, evader),
            pursuer_speed_mps=pursuer.speed_mps,
            evader_speed_mps=evader.speed_mps,
            heading_difference_rad=heading_difference_rad(pursuer.heading_rad, evader.heading_rad),
            along_m=dx * cos_h + dy * sin_h,
            lateral_m=abs(-dx * sin_h + dy * cos_h),
        )


class Specification(Protocol):
    """Anything that can say whether a pair satisfies it, and if not, why."""

    def first_failure(self, state: PairState) -> str | None:
        """Return the name of the first condition that fails, or ``None`` if all hold."""
        ...


@dataclass(frozen=True)
class Condition:
    """One named requirement on a pair."""

    name: str
    test: Callable[[PairState], bool]

    def first_failure(self, state: PairState) -> str | None:
        """Return this condition's name if it fails."""
        return None if self.test(state) else self.name


@dataclass(frozen=True)
class AllOf:
    """A conjunction of specifications, evaluated in order."""

    parts: tuple[Specification, ...]

    def first_failure(self, state: PairState) -> str | None:
        """Return the name of the first part that fails."""
        for part in self.parts:
            failure = part.first_failure(state)
            if failure is not None:
                return failure
        return None

    def is_satisfied_by(self, state: PairState) -> bool:
        """Tell whether every part holds."""
        return self.first_failure(state) is None
