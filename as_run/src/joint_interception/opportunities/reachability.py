"""Reachable arrival-time sets as canonical unions of disjoint closed intervals.

Implements METHOD_SPEC_EN.md section 2. The convex hull of a union is never substituted
for the union: doing so would declare unreachable times reachable.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .types import Direction

TOLERANCE = 1e-9

Interval = tuple[float, float]


def canonicalize(intervals: Iterable[Sequence[float]]) -> tuple[Interval, ...]:
    """Return a sorted, disjoint, non-adjacent, non-empty tuple of closed intervals.

    Empty intervals (a > b) are dropped. Touching or overlapping intervals are merged, so
    the result of this function applied twice equals the result applied once.
    """
    cleaned = []
    for item in intervals:
        low, high = float(item[0]), float(item[1])
        if high < low - TOLERANCE:
            continue
        cleaned.append((low, high))
    if not cleaned:
        return ()
    cleaned.sort()
    merged: list[Interval] = [cleaned[0]]
    for low, high in cleaned[1:]:
        last_low, last_high = merged[-1]
        if low <= last_high + TOLERANCE:
            merged[-1] = (last_low, max(last_high, high))
        else:
            merged.append((low, high))
    return tuple(merged)


def intersect(left: Sequence[Interval], right: Sequence[Interval]) -> tuple[Interval, ...]:
    """Exact intersection of two canonical unions, by linear merge. Cost O(len+len)."""
    out: list[Interval] = []
    i = j = 0
    while i < len(left) and j < len(right):
        low = max(left[i][0], right[j][0])
        high = min(left[i][1], right[j][1])
        if high >= low - TOLERANCE:
            out.append((low, high))
        if left[i][1] < right[j][1]:
            i += 1
        else:
            j += 1
    return canonicalize(out)


def intersect_all(sets: Sequence[Sequence[Interval]]) -> tuple[Interval, ...]:
    """Intersection over several canonical unions.

    An empty collection returns the empty union rather than a universal set: nothing was
    constrained, so nothing is established.
    """
    if not sets:
        return ()
    result = canonicalize(sets[0])
    for other in sets[1:]:
        result = intersect(result, canonicalize(other))
        if not result:
            break
    return result


def total_width(union: Sequence[Interval]) -> float:
    """Sum of interval lengths. NOT the quantity that governs dwell feasibility."""
    return sum(high - low for low, high in union)


def max_contiguous(union: Sequence[Interval]) -> float:
    """Longest single interval.

    Dwell feasibility uses this, because the capture predicate requires CONTINUOUS dwell.
    A union of two 2 s windows does not provide a 3 s dwell.
    """
    if not union:
        return 0.0
    return max(high - low for low, high in union)


def convex_hull(union: Sequence[Interval]) -> tuple[Interval, ...]:
    """The convex hull of a union.

    Provided ONLY so that the hull relaxation can be compared against the exact
    computation in the finite examples. It must never be used as an arrival set: it
    declares the gaps reachable.
    """
    if not union:
        return ()
    return ((union[0][0], union[-1][1]),)


def all_under(directions: Iterable[Direction]) -> bool:
    """Rule A precondition: only under-approximations may certify existence."""
    seen = list(directions)
    return bool(seen) and all(d is Direction.UNDER for d in seen)


def all_over(directions: Iterable[Direction]) -> bool:
    """Rule B precondition: only over-approximations may certify non-existence."""
    seen = list(directions)
    return bool(seen) and all(d is Direction.OVER for d in seen)


@dataclass(frozen=True)
class ArrivalSet:
    """A reachable arrival-time set with its mandatory approximation direction."""

    participant: str
    intervals: tuple[Interval, ...]
    direction: Direction

    @staticmethod
    def build(
        participant: str, intervals: Iterable[Sequence[float]], direction: Direction
    ) -> ArrivalSet:
        return ArrivalSet(participant, canonicalize(intervals), direction)
