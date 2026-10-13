"""Arrival-time models, and the direction each one can honestly claim.

This is the module the rest of the method has been waiting for. W2 built the machinery that
CONSUMES arrival sets; W3 built the generator that enumerates over them; nothing produced
them. It matters which direction a model achieves, because METHOD_SPEC_EN.md section 2.3
makes the two rules asymmetric:

- **Rule A** - `SUPPORTED` requires every participating set to be `UNDER`.
- **Rule B** - `REJECTED` requires every participating set to be `OVER`.

The direction is a property OF THE MODEL, not an annotation a caller may set. A model that
computes an earliest arrival cannot be relabelled `UNDER` by an optimistic caller, and the
type system here does not let it be.

The structural point, which no amount of better prediction changes: an `UNDER`-approximation
asserts that every time in the set is ACHIEVABLE. Achievability is a statement about what a
vehicle can be made to do, so it needs a schedule that could be executed - not a forecast of
what will happen. A free-flow estimate gives a lower bound on travel time and therefore an
`OVER`-approximation of reachable arrivals. Only a constructive schedule yields `UNDER`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .reachability import ArrivalSet
from .types import Direction


@dataclass(frozen=True)
class ArrivalQuery:
    """What a model is asked about: one participant reaching one station."""

    participant: str
    distance_m: float
    current_speed_mps: float
    speed_limit_mps: float
    max_acceleration_mps2: float
    max_deceleration_mps2: float
    horizon_s: float


@dataclass(frozen=True)
class ArrivalEstimate:
    """A model's answer, with its own account of what it does and does not bound."""

    arrival_set: ArrivalSet
    covered: bool
    earliest_s: float | None
    certified_upper_bound_s: float | None
    reason: str

    @property
    def direction(self) -> Direction:
        return self.arrival_set.direction


@runtime_checkable
class ArrivalModel(Protocol):
    """Every model must state its direction and justify it."""

    @property
    def model_id(self) -> str: ...

    @property
    def declared_direction(self) -> Direction: ...

    @property
    def direction_justification(self) -> str: ...

    def estimate(self, query: ArrivalQuery) -> ArrivalEstimate: ...


def free_flow_time_s(query: ArrivalQuery) -> float | None:
    """Earliest arrival ignoring every other vehicle.

    Accelerate at the bound to the speed limit, then cruise. Returns `None` when the
    distance cannot be covered within the horizon.
    """
    if query.distance_m <= 0:
        return 0.0
    speed, limit, accel = (
        query.current_speed_mps,
        query.speed_limit_mps,
        query.max_acceleration_mps2,
    )
    if accel <= 0 or limit <= 0:
        return None
    accel_time = max(0.0, (limit - speed) / accel)
    accel_distance = speed * accel_time + 0.5 * accel * accel_time * accel_time
    if accel_distance >= query.distance_m:
        # Solve 0.5*a*t^2 + v*t - d = 0 for the positive root.
        disc = speed * speed + 2.0 * accel * query.distance_m
        time_s = (math.sqrt(disc) - speed) / accel
    else:
        time_s = accel_time + (query.distance_m - accel_distance) / limit
    return time_s if time_s <= query.horizon_s else None


@dataclass(frozen=True)
class FreeFlowArrivalModel:
    """Earliest arrival with no interaction modelled.

    **Direction: OVER.** Interaction can only delay a vehicle, so the free-flow time is a
    lower bound on travel time and the set `[t_ff, horizon]` CONTAINS every achievable
    arrival plus times that are not achievable once other vehicles are present.

    Under Rule B this model can REJECT an opportunity - an empty intersection of
    over-approximations proves the true sets cannot intersect either. Under Rule A it can
    never SUPPORT one. That asymmetry is the whole point, and it is not a limitation of this
    implementation: it follows from what a free-flow estimate means.
    """

    speed_limit_mps: float = 13.89
    horizon_s: float = 300.0

    @property
    def model_id(self) -> str:
        return "free_flow_v1"

    @property
    def declared_direction(self) -> Direction:
        return Direction.OVER

    @property
    def direction_justification(self) -> str:
        return (
            "Interaction only delays; free-flow time is a lower bound on travel time, so the "
            "reported arrival set contains the achievable one. It can reject, never support."
        )

    def estimate(self, query: ArrivalQuery) -> ArrivalEstimate:
        earliest = free_flow_time_s(query)
        if earliest is None:
            return ArrivalEstimate(
                arrival_set=ArrivalSet.build(query.participant, [], Direction.OVER),
                covered=False,
                earliest_s=None,
                certified_upper_bound_s=None,
                reason="distance_not_coverable_within_horizon",
            )
        return ArrivalEstimate(
            arrival_set=ArrivalSet.build(
                query.participant, [(earliest, query.horizon_s)], Direction.OVER
            ),
            covered=True,
            earliest_s=earliest,
            # There is no upper bound: an arbitrarily slow arrival is possible under
            # interaction, and nothing here certifies a latest achievable arrival.
            certified_upper_bound_s=None,
            reason="free_flow_lower_bound_no_certified_upper_bound",
        )


@dataclass(frozen=True)
class ConstructiveArrivalModel:
    """Arrival times backed by a schedule the vehicle could actually execute.

    **Direction: UNDER, and only when a schedule is supplied.** This is the only route to an
    under-approximation. A constructive witness asserts achievability, which is what Rule A
    requires; a forecast cannot, however accurate it becomes.

    With no schedule the model reports `UNKNOWN` coverage rather than falling back to a
    free-flow guess. Falling back would silently convert an unsupportable claim into a
    supportable-looking one, which is exactly the failure this direction machinery exists to
    prevent.
    """

    schedules: dict[str, tuple[float, float]] = None  # participant -> (earliest, latest)
    horizon_s: float = 300.0

    @property
    def model_id(self) -> str:
        return "constructive_v1"

    @property
    def declared_direction(self) -> Direction:
        return Direction.UNDER

    @property
    def direction_justification(self) -> str:
        return (
            "Every reported time is backed by an executable schedule, so every time in the "
            "set is achievable. This is what Rule A requires and what a forecast cannot give."
        )

    def estimate(self, query: ArrivalQuery) -> ArrivalEstimate:
        schedule = (self.schedules or {}).get(query.participant)
        if schedule is None:
            return ArrivalEstimate(
                arrival_set=ArrivalSet.build(query.participant, [], Direction.UNDER),
                covered=False,
                earliest_s=None,
                certified_upper_bound_s=None,
                reason="no_constructive_schedule_supplied",
            )
        earliest, latest = schedule
        return ArrivalEstimate(
            arrival_set=ArrivalSet.build(query.participant, [(earliest, latest)], Direction.UNDER),
            covered=True,
            earliest_s=earliest,
            certified_upper_bound_s=latest,
            reason="schedule_backed_interval",
        )


@dataclass(frozen=True)
class RecordedProfileModel:
    """Replays a recorded point hypothesis, so its declared direction can be tested.

    **Direction: PREDICTION.** A point hypothesis with no certified error bound supports
    neither verdict. This model exists so the historical arrival model's own recorded
    behaviour can be checked against the direction it would need in order to be useful.
    """

    @property
    def model_id(self) -> str:
        return "recorded_profile_v1"

    @property
    def declared_direction(self) -> Direction:
        return Direction.PREDICTION

    @property
    def direction_justification(self) -> str:
        return (
            "A point hypothesis without a certified error bound bounds the truth in neither "
            "direction, so it can neither support nor reject."
        )

    def estimate(self, query: ArrivalQuery) -> ArrivalEstimate:
        earliest = free_flow_time_s(query)
        if earliest is None:
            return ArrivalEstimate(
                arrival_set=ArrivalSet.build(query.participant, [], Direction.PREDICTION),
                covered=False,
                earliest_s=None,
                certified_upper_bound_s=None,
                reason="distance_not_coverable_within_horizon",
            )
        return ArrivalEstimate(
            arrival_set=ArrivalSet.build(
                query.participant, [(earliest, earliest)], Direction.PREDICTION
            ),
            covered=True,
            earliest_s=earliest,
            certified_upper_bound_s=None,
            reason="point_hypothesis_no_certified_error_bound",
        )


@dataclass(frozen=True)
class ScheduledArrivalModel:
    """Generates its own constructive witnesses instead of being handed them.

    **Direction: UNDER, and the label is earned per query.** Where `ConstructiveArrivalModel`
    accepts schedules supplied from outside — a W4 offline construction, say — this model
    builds them from the vehicle's kinematic limits and verifies each one by integration
    before reporting the interval.

    Scope, stated rather than implied: motion along a one-dimensional path with bounded
    acceleration. No junctions, lane changes, traffic or signals, and no accounting for
    other participants' committed plans. `blocking_windows` is the hook through which that
    interaction will enter, and supplying it is what makes the resulting set nonconvex.
    """

    speed_limit_mps: float = 13.89
    max_acceleration_mps2: float = 2.6
    max_deceleration_mps2: float = 4.5
    horizon_s: float = 300.0
    blocking_windows: tuple[tuple[float, float], ...] = ()

    @property
    def model_id(self) -> str:
        return "scheduled_v1"

    @property
    def declared_direction(self) -> Direction:
        return Direction.UNDER

    @property
    def direction_justification(self) -> str:
        return (
            "Each reported interval is built from executable speed profiles that are "
            "verified by integration before the interval is returned, so every reported "
            "time is achievable rather than forecast."
        )

    def estimate(self, query: ArrivalQuery) -> ArrivalEstimate:
        from .schedule import constructive_arrival_set

        witness = constructive_arrival_set(
            participant=query.participant,
            distance_m=query.distance_m,
            initial_speed_mps=query.current_speed_mps,
            speed_limit_mps=self.speed_limit_mps,
            max_acceleration_mps2=self.max_acceleration_mps2,
            max_deceleration_mps2=self.max_deceleration_mps2,
            horizon_s=self.horizon_s,
            blocking_windows=self.blocking_windows,
        )
        if witness is None:
            # No verified schedule exists, so nothing is reported. Falling back to a
            # free-flow guess here would convert an unsupportable claim into a
            # supportable-looking one, which is the failure the direction rules prevent.
            return ArrivalEstimate(
                arrival_set=ArrivalSet.build(query.participant, [], Direction.UNDER),
                covered=False,
                earliest_s=None,
                certified_upper_bound_s=None,
                reason="no_verified_schedule_exists",
            )
        return ArrivalEstimate(
            arrival_set=witness.arrival_set,
            covered=True,
            earliest_s=witness.earliest_s,
            certified_upper_bound_s=witness.latest_s,
            reason=f"verified_schedules_on_{witness.verified_sample_count}_sampled_times",
        )


def can_support(models: list[ArrivalModel]) -> bool:
    """Whether a set of models could ever yield a `SUPPORTED` verdict under Rule A."""
    return bool(models) and all(m.declared_direction is Direction.UNDER for m in models)


def can_reject(models: list[ArrivalModel]) -> bool:
    """Whether a set of models could ever yield a `REJECTED` verdict under Rule B."""
    return bool(models) and all(m.declared_direction is Direction.OVER for m in models)
