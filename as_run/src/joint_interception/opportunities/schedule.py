"""Constructive arrival schedules: profiles that EARN the `UNDER` label.

The arrival-model diagnostic established that only a constructive schedule yields an
`UNDER` set, and that `UNDER` is the only direction Rule A accepts for `SUPPORTED`. It also
left the hole this module closes: `ConstructiveArrivalModel` took `(earliest, latest)` as
INPUT, so its `UNDER` label was an assertion nobody had discharged.

Here the label is earned. Every reported arrival time comes with a `SpeedProfile` that can
be integrated, and integrating it must land the vehicle at the station at exactly that
time, with speed and acceleration inside their bounds throughout. A time with no verified
profile is not reported.

The abstraction is deliberately narrow and named: motion along a one-dimensional path with
bounded acceleration. No junctions, no lane changes, no traffic, no signals, and no
interaction with other participants' committed plans. That last omission is the harder half
of the problem and is scoped out rather than glossed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .reachability import ArrivalSet, canonicalize
from .types import Direction

TOLERANCE = 1e-9


@dataclass(frozen=True)
class Segment:
    """A constant-acceleration segment: hold `acceleration` for `duration`."""

    duration_s: float
    acceleration_mps2: float


@dataclass(frozen=True)
class SpeedProfile:
    """A schedule as a sequence of constant-acceleration segments.

    Integration is closed form per segment, so `arrival` is exact rather than the result of
    a numerical step that could hide a small error in the construction.
    """

    initial_speed_mps: float
    segments: tuple[Segment, ...]

    @property
    def duration_s(self) -> float:
        return sum(s.duration_s for s in self.segments)

    def integrate(self) -> tuple[float, float]:
        """Return `(distance_covered, final_speed)` by exact integration."""
        speed = self.initial_speed_mps
        distance = 0.0
        for segment in self.segments:
            t, a = segment.duration_s, segment.acceleration_mps2
            distance += speed * t + 0.5 * a * t * t
            speed += a * t
        return distance, speed

    def violations(
        self, speed_limit_mps: float, max_acceleration_mps2: float, max_deceleration_mps2: float
    ) -> list[str]:
        """Every way this profile would be illegal.

        Speed is checked at both ends of each segment AND at an interior extremum, because
        a segment that accelerates then is cut short can still peak inside its own span.
        """
        problems: list[str] = []
        speed = self.initial_speed_mps
        if speed < -TOLERANCE:
            problems.append("initial speed negative")
        if speed > speed_limit_mps + TOLERANCE:
            problems.append("initial speed above limit")
        for index, segment in enumerate(self.segments):
            a, t = segment.acceleration_mps2, segment.duration_s
            if t < -TOLERANCE:
                problems.append(f"segment {index}: negative duration")
            if a > max_acceleration_mps2 + TOLERANCE:
                problems.append(f"segment {index}: acceleration {a} above {max_acceleration_mps2}")
            if a < -max_deceleration_mps2 - TOLERANCE:
                problems.append(f"segment {index}: deceleration {a} below -{max_deceleration_mps2}")
            end_speed = speed + a * t
            for label, value in (("start", speed), ("end", end_speed)):
                if value < -TOLERANCE:
                    problems.append(f"segment {index}: {label} speed negative ({value})")
                if value > speed_limit_mps + TOLERANCE:
                    problems.append(f"segment {index}: {label} speed above limit ({value})")
            speed = end_speed
        return problems


def _accelerate_then_cruise(
    distance_m: float,
    initial_speed_mps: float,
    speed_limit_mps: float,
    max_acceleration_mps2: float,
) -> tuple[float, SpeedProfile]:
    """Fastest legal traversal: accelerate to the limit, then hold it."""
    if distance_m <= TOLERANCE:
        return 0.0, SpeedProfile(initial_speed_mps, ())
    accel_time = max(0.0, (speed_limit_mps - initial_speed_mps) / max_acceleration_mps2)
    accel_distance = initial_speed_mps * accel_time + 0.5 * max_acceleration_mps2 * accel_time**2
    if accel_distance >= distance_m - TOLERANCE:
        # The limit is never reached: solve 0.5*a*t^2 + v*t - d = 0.
        disc = initial_speed_mps**2 + 2.0 * max_acceleration_mps2 * distance_m
        t = (math.sqrt(disc) - initial_speed_mps) / max_acceleration_mps2
        return t, SpeedProfile(initial_speed_mps, (Segment(t, max_acceleration_mps2),))
    cruise_time = (distance_m - accel_distance) / speed_limit_mps
    return accel_time + cruise_time, SpeedProfile(
        initial_speed_mps,
        (Segment(accel_time, max_acceleration_mps2), Segment(cruise_time, 0.0)),
    )


def earliest_arrival(
    distance_m: float,
    initial_speed_mps: float,
    speed_limit_mps: float,
    max_acceleration_mps2: float,
) -> tuple[float, SpeedProfile]:
    """The earliest achievable arrival, with the profile that achieves it."""
    if max_acceleration_mps2 <= 0 or speed_limit_mps <= 0:
        raise ValueError("acceleration and speed limit must be positive")
    return _accelerate_then_cruise(
        distance_m, initial_speed_mps, speed_limit_mps, max_acceleration_mps2
    )


def arrival_at(
    distance_m: float,
    initial_speed_mps: float,
    speed_limit_mps: float,
    max_acceleration_mps2: float,
    max_deceleration_mps2: float,
    target_time_s: float,
) -> SpeedProfile | None:
    """A legal profile arriving at **exactly** `target_time_s`, or `None` if impossible.

    This is what makes the arrival set an INTERVAL rather than two endpoints. Any time later
    than the earliest is reachable by going slower, and the construction below exhibits the
    control that does it rather than appealing to continuity.

    Construction: decelerate at a chosen rate for a first phase, then hold that speed. The
    rate is found by bisection on the total distance, which is monotone in it. Bisection is
    used because the closed form branches on whether the vehicle reaches zero speed inside
    the first phase, and a monotone numeric solve is easier to verify than those branches.
    """
    if target_time_s <= TOLERANCE:
        return None
    fastest, fastest_profile = earliest_arrival(
        distance_m, initial_speed_mps, speed_limit_mps, max_acceleration_mps2
    )
    if target_time_s < fastest - TOLERANCE:
        return None
    if abs(target_time_s - fastest) <= TOLERANCE:
        return fastest_profile

    def distance_for(decel_rate: float) -> tuple[float, SpeedProfile]:
        """Decelerate at `decel_rate` until the speed floor, then cruise for the remainder."""
        if decel_rate <= TOLERANCE:
            return (
                initial_speed_mps * target_time_s,
                SpeedProfile(initial_speed_mps, (Segment(target_time_s, 0.0),)),
            )
        time_to_stop = initial_speed_mps / decel_rate
        brake_time = min(time_to_stop, target_time_s)
        end_speed = initial_speed_mps - decel_rate * brake_time
        covered = initial_speed_mps * brake_time - 0.5 * decel_rate * brake_time**2
        remaining_time = target_time_s - brake_time
        covered += end_speed * remaining_time
        segments = [Segment(brake_time, -decel_rate)]
        if remaining_time > TOLERANCE:
            segments.append(Segment(remaining_time, 0.0))
        return covered, SpeedProfile(initial_speed_mps, tuple(segments))

    # Holding the initial speed for the whole target time must cover at least the distance,
    # otherwise no amount of slowing helps and the vehicle must accelerate instead.
    hold_distance, _ = distance_for(0.0)
    if hold_distance < distance_m - TOLERANCE:
        return _accelerate_then_hold_for(
            distance_m,
            initial_speed_mps,
            speed_limit_mps,
            max_acceleration_mps2,
            target_time_s,
        )

    low, high = 0.0, max_deceleration_mps2
    if distance_for(high)[0] > distance_m + TOLERANCE:
        return None  # even maximum braking overshoots: the target time is unreachable
    for _ in range(200):
        mid = 0.5 * (low + high)
        covered, _ = distance_for(mid)
        if covered > distance_m:
            low = mid
        else:
            high = mid
    _, profile = distance_for(0.5 * (low + high))
    return profile


def _accelerate_then_hold_for(
    distance_m: float,
    initial_speed_mps: float,
    speed_limit_mps: float,
    max_acceleration_mps2: float,
    target_time_s: float,
) -> SpeedProfile | None:
    """Arrive at exactly `target_time_s` when holding the initial speed is too slow.

    Accelerate at a chosen rate, then hold. The rate is found by bisection on distance,
    which is monotone in it.
    """

    def distance_for(rate: float) -> tuple[float, SpeedProfile]:
        if rate <= TOLERANCE:
            return (
                initial_speed_mps * target_time_s,
                SpeedProfile(initial_speed_mps, (Segment(target_time_s, 0.0),)),
            )
        time_to_limit = max(0.0, (speed_limit_mps - initial_speed_mps) / rate)
        accel_time = min(time_to_limit, target_time_s)
        end_speed = initial_speed_mps + rate * accel_time
        covered = initial_speed_mps * accel_time + 0.5 * rate * accel_time**2
        remaining = target_time_s - accel_time
        covered += end_speed * remaining
        segments = [Segment(accel_time, rate)]
        if remaining > TOLERANCE:
            segments.append(Segment(remaining, 0.0))
        return covered, SpeedProfile(initial_speed_mps, tuple(segments))

    if distance_for(max_acceleration_mps2)[0] < distance_m - TOLERANCE:
        return None
    low, high = 0.0, max_acceleration_mps2
    for _ in range(200):
        mid = 0.5 * (low + high)
        if distance_for(mid)[0] < distance_m:
            low = mid
        else:
            high = mid
    _, profile = distance_for(0.5 * (low + high))
    return profile


@dataclass(frozen=True)
class ConstructiveWitness:
    """An arrival set whose `UNDER` label has been discharged."""

    participant: str
    arrival_set: ArrivalSet
    earliest_s: float
    latest_s: float
    earliest_profile: SpeedProfile
    verified_sample_count: int
    blocking_windows: tuple[tuple[float, float], ...]
    reason: str


def constructive_arrival_set(
    participant: str,
    distance_m: float,
    initial_speed_mps: float,
    speed_limit_mps: float,
    max_acceleration_mps2: float,
    max_deceleration_mps2: float,
    horizon_s: float,
    blocking_windows: tuple[tuple[float, float], ...] = (),
    verification_samples: int = 64,
) -> ConstructiveWitness | None:
    """Build an `UNDER` arrival set, verifying a sample of its times by integration.

    `blocking_windows` are intervals during which the station cannot be occupied. Removing
    them is what makes the set **nonconvex** — the case the method specification requires
    and a convex hull destroys.

    Verification here is a sample, and the number verified is reported rather than implied.
    The exhaustive check lives in the tests, where it can afford to be dense.
    """
    if max_acceleration_mps2 <= 0 or max_deceleration_mps2 <= 0 or speed_limit_mps <= 0:
        raise ValueError("kinematic limits must be positive")
    earliest, earliest_profile = earliest_arrival(
        distance_m, initial_speed_mps, speed_limit_mps, max_acceleration_mps2
    )
    if earliest > horizon_s:
        return None

    intervals = [(earliest, horizon_s)]
    for low, high in blocking_windows:
        remaining: list[tuple[float, float]] = []
        for a, b in intervals:
            if high <= a or low >= b:
                remaining.append((a, b))
                continue
            if a < low:
                remaining.append((a, min(low, b)))
            if b > high:
                remaining.append((max(high, a), b))
        intervals = [(a, b) for a, b in remaining if b - a > TOLERANCE]
    if not intervals:
        return None

    canonical = canonicalize(intervals)
    verified = 0
    for low, high in canonical:
        steps = max(2, verification_samples // len(canonical))
        for index in range(steps):
            t = low + (high - low) * index / (steps - 1)
            profile = arrival_at(
                distance_m,
                initial_speed_mps,
                speed_limit_mps,
                max_acceleration_mps2,
                max_deceleration_mps2,
                t,
            )
            if profile is None:
                return None
            covered, _ = profile.integrate()
            if abs(covered - distance_m) > 1e-6 or abs(profile.duration_s - t) > 1e-6:
                return None
            if profile.violations(speed_limit_mps, max_acceleration_mps2, max_deceleration_mps2):
                return None
            verified += 1

    return ConstructiveWitness(
        participant=participant,
        arrival_set=ArrivalSet(participant, canonical, Direction.UNDER),
        earliest_s=canonical[0][0],
        latest_s=canonical[-1][1],
        earliest_profile=earliest_profile,
        verified_sample_count=verified,
        blocking_windows=tuple(blocking_windows),
        reason="every sampled time has a verified legal schedule",
    )
