"""The interaction half: blocking windows derived from participants' committed plans.

`constructive_arrival_set` takes `blocking_windows` as an INPUT and scopes out where they
come from. They come from the other participants, and that makes the problem circular:
when `i` can arrive depends on when the others occupy the lane, which depends on when they
can arrive, which depends on `i`.

This module states that circularity as an operator and searches for a mutually consistent
commitment set. It does NOT prove one exists.

**Why no existence theorem is available.** Kakutani's fixed-point theorem requires the
set-valued map to have CONVEX values. Arrival sets here are deliberately nonconvex - unions
of disjoint closed intervals, with the convex hull forbidden, because the hull would readmit
exactly the times a blocking window removed. The property that makes the representation
worth having is the property that removes the guarantee. A failed search therefore reports
`NOT_FOUND_ON_THIS_GRID`, never "no fixed point exists"; non-existence is asserted only
where a separate proof applies.

**The capacity constraint is joint, not pairwise.** Occupancy is not required to be pairwise
disjoint; it is required to fit. At every instant the occupants must satisfy
`lane_capacity_required_m`. On a 14.0 m lane with 5.0 m bodies at a 2.5 m gap that admits
two occupants and not three: every pair is fine and the triple is not, which is precisely
what a pairwise test cannot express.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from enum import Enum

from .compatibility import lane_capacity_required_m
from .schedule import TOLERANCE, ConstructiveWitness, constructive_arrival_set


class ConsistencyVerdict(str, Enum):
    WITNESS_VERIFIED = "WITNESS_VERIFIED"
    NOT_FOUND_ON_THIS_GRID = "NOT_FOUND_ON_THIS_GRID"
    PROVABLY_INCONSISTENT = "PROVABLY_INCONSISTENT"
    UNSOUND = "UNSOUND"


@dataclass(frozen=True)
class Participant:
    """One pursuer's approach to the shared lane."""

    participant_id: str
    distance_m: float
    initial_speed_mps: float
    speed_limit_mps: float
    max_acceleration_mps2: float
    max_deceleration_mps2: float


@dataclass(frozen=True)
class Lane:
    """The shared resource the commitments contend for."""

    lane_id: str
    length_m: float
    body_length_m: float
    min_gap_m: float

    def capacity(self) -> int:
        """How many bodies fit at once. Zero if not even one does."""
        count = 0
        while lane_capacity_required_m(count + 1, self.body_length_m, self.min_gap_m) <= (
            self.length_m + TOLERANCE
        ):
            count += 1
        return count


@dataclass(frozen=True)
class Commitment:
    """A chosen arrival time and the lane occupancy it induces."""

    participant_id: str
    arrival_s: float
    occupancy: tuple[float, float]


@dataclass(frozen=True)
class ConsistencyResult:
    verdict: ConsistencyVerdict
    commitments: tuple[Commitment, ...]
    witnesses: tuple[ConstructiveWitness, ...]
    max_concurrent: int
    capacity: int
    reason: str
    proof: str | None = None
    grid_size: int = 0
    combinations_examined: int = 0


def occupancy_window(arrival_s: float, dwell_s: float) -> tuple[float, float]:
    """The interval a participant occupies the lane, given its arrival.

    Occupancy starts at arrival and lasts the contract's dwell. It is deliberately NOT
    widened by a safety pad here: padding would be a second, undeclared safety margin on top
    of the capacity arithmetic, and two margins that both look like the answer are how a
    guard stops being checkable.
    """
    return (arrival_s, arrival_s + dwell_s)


def max_concurrent(windows: list[tuple[float, float]]) -> int:
    """Greatest number of windows overlapping at any instant, by sweep.

    A sweep, never a pairwise scan. Pairwise overlap counts cannot distinguish "three
    windows pairwise overlapping in sequence" from "three windows overlapping at one
    instant", and only the second violates capacity.

    Ends are treated as closing before starts open at the same instant: two vehicles, one
    leaving exactly as the other arrives, do not occupy the lane simultaneously.
    """
    events: list[tuple[float, int]] = []
    for low, high in windows:
        events.append((low, 1))
        events.append((high, -1))
    events.sort(key=lambda e: (e[0], e[1]))
    current = peak = 0
    for _, delta in events:
        current += delta
        peak = max(peak, current)
    return peak


def blocking_for(
    target: str, commitments: dict[str, Commitment], capacity: int
) -> tuple[tuple[float, float], ...]:
    """Windows during which `target` may NOT arrive, given everyone else's commitments.

    A window blocks only where the others already fill the lane. With capacity two, one
    other occupant blocks nothing; two do. This is where the joint constraint enters the
    per-participant problem, and it is why the blocking set cannot be built pairwise.
    """
    others = [c.occupancy for pid, c in commitments.items() if pid != target]
    if not others:
        return ()
    boundaries = sorted({t for window in others for t in window})
    blocked: list[tuple[float, float]] = []
    for low, high in zip(boundaries, boundaries[1:], strict=False):
        if high - low <= TOLERANCE:
            continue
        midpoint = (low + high) / 2.0
        occupants = sum(1 for a, b in others if a <= midpoint <= b)
        if occupants >= capacity:
            blocked.append((low, high))
    merged: list[tuple[float, float]] = []
    for low, high in blocked:
        if merged and low - merged[-1][1] <= TOLERANCE:
            merged[-1] = (merged[-1][0], high)
        else:
            merged.append((low, high))
    return tuple(merged)


def _candidate_times(
    participant: Participant,
    horizon_s: float,
    grid: int,
    blocking: tuple[tuple[float, float], ...],
) -> tuple[list[float], ConstructiveWitness | None]:
    """Times this participant could commit to, given `blocking`, sampled on a grid.

    The witness carries the discharged `UNDER` label; the grid samples it. A time is offered
    only if it lies inside a verified interval of that witness.
    """
    witness = constructive_arrival_set(
        participant.participant_id,
        participant.distance_m,
        participant.initial_speed_mps,
        participant.speed_limit_mps,
        participant.max_acceleration_mps2,
        participant.max_deceleration_mps2,
        horizon_s,
        blocking_windows=blocking,
    )
    if witness is None:
        return [], None
    times: list[float] = []
    for low, high in witness.arrival_set.intervals:
        if high - low <= TOLERANCE:
            times.append(low)
            continue
        for index in range(grid):
            times.append(low + (high - low) * index / max(1, grid - 1))
    return sorted(set(times)), witness


def solve_mutual_consistency(
    participants: list[Participant],
    lane: Lane,
    horizon_s: float,
    dwell_s: float,
    grid: int = 9,
) -> ConsistencyResult:
    """Search for a commitment set in which every choice is reachable given the others.

    Enumeration over a grid, deliberately. A cleverer search would be faster and would make
    a negative result harder to interpret; here a failure means exactly "not on this grid",
    which is a statement whose limits are visible.

    **A failed search never licenses a claim of non-existence.** Non-existence is returned
    only from a proof that does not depend on the grid: a participant unreachable before any
    blocking at all, or a lane too short to hold even one body.
    """
    capacity = lane.capacity()
    if capacity < 1:
        return ConsistencyResult(
            verdict=ConsistencyVerdict.PROVABLY_INCONSISTENT,
            commitments=(),
            witnesses=(),
            max_concurrent=0,
            capacity=capacity,
            reason="the lane cannot hold a single body",
            proof=(
                f"one body requires "
                f"{lane_capacity_required_m(1, lane.body_length_m, lane.min_gap_m)} m "
                f"and the lane is {lane.length_m} m"
            ),
        )

    unblocked: dict[str, ConstructiveWitness] = {}
    for participant in participants:
        _, witness = _candidate_times(participant, horizon_s, grid, ())
        if witness is None:
            return ConsistencyResult(
                verdict=ConsistencyVerdict.PROVABLY_INCONSISTENT,
                commitments=(),
                witnesses=(),
                max_concurrent=0,
                capacity=capacity,
                reason=f"{participant.participant_id} cannot reach the station at all",
                proof=(
                    "its arrival set is empty with NO blocking windows, so no assignment by "
                    "anyone else can make it reachable: blocking only removes times"
                ),
            )
        unblocked[participant.participant_id] = witness

    options = [_candidate_times(p, horizon_s, grid, ())[0] for p in participants]
    examined = 0
    for combination in itertools.product(*options):
        examined += 1
        commitments = {
            p.participant_id: Commitment(p.participant_id, t, occupancy_window(t, dwell_s))
            for p, t in zip(participants, combination, strict=True)
        }
        windows = [c.occupancy for c in commitments.values()]
        peak = max_concurrent(windows)
        if peak > capacity:
            continue

        verified: list[ConstructiveWitness] = []
        consistent = True
        for participant in participants:
            blocking = blocking_for(participant.participant_id, commitments, capacity)
            times, witness = _candidate_times(participant, horizon_s, grid, blocking)
            chosen = commitments[participant.participant_id].arrival_s
            if witness is None or not _contains(witness, chosen):
                consistent = False
                break
            verified.append(witness)
        if not consistent:
            continue

        return ConsistencyResult(
            verdict=ConsistencyVerdict.WITNESS_VERIFIED,
            commitments=tuple(commitments[p.participant_id] for p in participants),
            witnesses=tuple(verified),
            max_concurrent=peak,
            capacity=capacity,
            reason=(
                "every committed time lies in its participant's arrival set recomputed "
                "against the others, and joint occupancy never exceeds capacity"
            ),
            grid_size=grid,
            combinations_examined=examined,
        )

    return ConsistencyResult(
        verdict=ConsistencyVerdict.NOT_FOUND_ON_THIS_GRID,
        commitments=(),
        witnesses=(),
        max_concurrent=0,
        capacity=capacity,
        reason="no commitment set on this grid was mutually consistent",
        proof=None,
        grid_size=grid,
        combinations_examined=examined,
    )


def _contains(witness: ConstructiveWitness, time_s: float) -> bool:
    return any(
        low - TOLERANCE <= time_s <= high + TOLERANCE for low, high in witness.arrival_set.intervals
    )
