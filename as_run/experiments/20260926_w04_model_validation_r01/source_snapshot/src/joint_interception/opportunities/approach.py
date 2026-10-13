"""The approach model: an earliest arrival a vehicle can actually achieve on a network.

The finite abstraction gave one distance, one speed limit and bounded acceleration. A-42
showed why that fails: the speed limit ignored SUMO's INTERNAL junction lanes, which are far
slower than the edges they connect, so the abstraction demanded a speed the vehicle is never
permitted to hold. Seven of twelve routes fell to the observation resolution once that was
corrected, and the residual is consistent with traffic signals.

This module models the approach as it is: an ordered chain of lanes, each with its own
length and speed limit, internal junction lanes included, with signal-controlled links that
hold a vehicle until green.

**Signal programs are deterministic and there is no background traffic, so a release time is
a LOOKUP, not a prediction.** That is what keeps `UNDER` earnable here: the model is not
guessing when the light changes, it is reading the program the simulator will follow.

What this module does NOT do: queues, other vehicles, actuated or adaptive programs, or
lane changes. Each is a reason a real arrival could be later than computed, and each is
recorded rather than assumed away.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

TOLERANCE = 1e-9


@dataclass(frozen=True)
class Segment:
    """One lane on the approach, with the signal that guards its entry, if any."""

    lane_id: str
    length_m: float
    speed_limit_mps: float
    is_internal: bool = False
    #: Signal controlling ENTRY to this segment, as (tls_id, link_index).
    signal: tuple[str, int] | None = None


@dataclass(frozen=True)
class SignalProgram:
    """A fixed-time program: phase durations and the state string per phase."""

    tls_id: str
    phase_durations: tuple[float, ...]
    phase_states: tuple[str, ...]
    offset: float = 0.0

    @property
    def cycle_s(self) -> float:
        return sum(self.phase_durations)

    def is_green(self, link_index: int, time_s: float) -> bool:
        """Is `link_index` permitted to proceed at `time_s`?

        `G` and `g` are go. Yellow is NOT treated as go: entering on yellow is a judgement
        the model must not make on the vehicle's behalf, and treating it as go would produce
        arrival times the simulator may refuse to honour.
        """
        if self.cycle_s <= 0:
            return True
        phase = self._phase_at(time_s)
        state = self.phase_states[phase]
        if link_index < 0 or link_index >= len(state):
            return True
        return state[link_index] in "Gg"

    def state(self, link_index: int, time_s: float) -> str:
        """The raw state character for `link_index` at `time_s` ('G', 'g', 'y', 'r', ...)."""
        if self.cycle_s <= 0:
            return "G"
        phase_state = self.phase_states[self._phase_at(time_s)]
        if link_index < 0 or link_index >= len(phase_state):
            return "G"
        return phase_state[link_index]

    def next_green_s(self, link_index: int, time_s: float) -> float:
        """Earliest time at or after `time_s` when `link_index` may proceed.

        Returns `time_s` when it is already green. Scans one full cycle of phase boundaries;
        a link that is never green in any phase yields `inf` rather than a wrong answer.
        """
        if self.is_green(link_index, time_s):
            return time_s
        if self.cycle_s <= 0:
            return time_s
        boundaries = self._boundaries_from(time_s)
        for candidate in boundaries:
            if self.is_green(link_index, candidate + TOLERANCE):
                return candidate
        return math.inf

    def _phase_at(self, time_s: float) -> int:
        position = (time_s - self.offset) % self.cycle_s
        for index, duration in enumerate(self.phase_durations):
            if position < duration - TOLERANCE:
                return index
            position -= duration
        return len(self.phase_durations) - 1

    def _boundaries_from(self, time_s: float) -> list[float]:
        position = (time_s - self.offset) % self.cycle_s
        elapsed = 0.0
        out: list[float] = []
        for duration in self.phase_durations:
            elapsed += duration
            if elapsed > position + TOLERANCE:
                out.append(time_s + (elapsed - position))
        for duration in self.phase_durations:
            elapsed += duration
            out.append(time_s + (elapsed - position))
        return out


def traverse(
    length_m: float,
    entry_speed_mps: float,
    speed_cap_mps: float,
    exit_speed_cap_mps: float,
    accel: float,
    decel: float,
) -> tuple[float, float]:
    """Fastest legal traversal of one segment. Returns `(duration_s, exit_speed_mps)`.

    Accelerate, optionally cruise at the cap, then decelerate only as much as the next
    segment's entry limit requires. Closed form per phase, so the result is exact rather
    than the accumulation of a numerical step.
    """
    if length_m <= TOLERANCE:
        return 0.0, min(entry_speed_mps, speed_cap_mps, exit_speed_cap_mps)

    v0 = min(entry_speed_mps, speed_cap_mps)
    vexit_cap = min(exit_speed_cap_mps, speed_cap_mps)

    # Highest speed reachable that still allows slowing to `vexit_cap` by the segment end.
    peak_squared = (2 * accel * decel * length_m + decel * v0**2 + accel * vexit_cap**2) / (
        accel + decel
    )
    peak = min(speed_cap_mps, math.sqrt(max(0.0, peak_squared)))

    if peak < v0 - TOLERANCE:
        # Cannot hold entry speed: the segment is a deceleration throughout.
        exit_speed = math.sqrt(max(0.0, v0**2 - 2 * decel * length_m))
        exit_speed = min(exit_speed, vexit_cap)
        average = (v0 + exit_speed) / 2.0
        return (length_m / average if average > TOLERANCE else math.inf), exit_speed

    accel_distance = max(0.0, (peak**2 - v0**2) / (2 * accel))
    exit_speed = min(peak, vexit_cap)
    decel_distance = max(0.0, (peak**2 - exit_speed**2) / (2 * decel))
    cruise_distance = length_m - accel_distance - decel_distance

    if cruise_distance < -TOLERANCE:
        # No room for both ramps at this peak; the peak already accounts for that, so any
        # residue is numerical. Clamp rather than let it leak into the reported time.
        cruise_distance = 0.0

    duration = 0.0
    if accel > TOLERANCE:
        duration += (peak - v0) / accel
    if peak > TOLERANCE:
        duration += cruise_distance / peak
    if decel > TOLERANCE:
        duration += (peak - exit_speed) / decel
    return duration, exit_speed


def earliest_arrival_on_approach(
    segments: list[Segment],
    programs: dict[str, SignalProgram],
    initial_speed_mps: float,
    accel: float,
    decel: float,
    start_time_s: float = 0.0,
    final_distance_m: float | None = None,
    max_iterations: int = 12,
) -> dict:
    """Earliest arrival the vehicle can actually achieve along this chain of lanes.

    **A fixed point over which signals require a stop.** Stopping at a line is not free: the
    vehicle must brake during the PRECEDING segment, which takes longer than passing through
    at speed, which changes when it reaches the line, which can change whether the light was
    red in the first place. Computing the pass once and hoping would quietly understate the
    time, so the set of stopping signals is iterated until it stabilises.

    Convergence is not guaranteed - a signal can oscillate in and out of the stopping set -
    so the iteration is bounded and a failure to stabilise is REPORTED, never rounded off
    into a plausible-looking number.

    The result is ACHIEVABLE, not optimal: waiting at a red and then proceeding is one
    strategy, and a slower approach that catches the next green earlier may exist. `UNDER`
    needs achievability, so that gap is recorded rather than closed.
    """
    stopping: set[int] = set()
    for iteration in range(max_iterations):
        outcome = _single_pass(
            segments,
            programs,
            initial_speed_mps,
            accel,
            decel,
            start_time_s,
            final_distance_m,
            stopping,
        )
        if not outcome["reachable"]:
            return outcome
        required = outcome["_required_stops"]
        if required == stopping:
            outcome.pop("_required_stops")
            outcome["stop_set_iterations"] = iteration + 1
            outcome["stop_set_converged"] = True
            return outcome
        stopping = required

    outcome.pop("_required_stops", None)
    outcome["stop_set_iterations"] = max_iterations
    outcome["stop_set_converged"] = False
    outcome["reachable"] = False
    outcome["reason"] = (
        "the set of signals requiring a stop did not stabilise within the iteration bound; "
        "no achievable time is reported rather than reporting an unstable one"
    )
    return outcome


def _single_pass(
    segments: list[Segment],
    programs: dict[str, SignalProgram],
    initial_speed_mps: float,
    accel: float,
    decel: float,
    start_time_s: float,
    final_distance_m: float | None,
    stopping: set[int],
) -> dict:
    """One forward pass, braking to a standstill before every segment in `stopping`."""
    time = start_time_s
    speed = initial_speed_mps
    waits: list[dict] = []
    required: set[int] = set()
    remaining = final_distance_m

    for index, segment in enumerate(segments):
        length = segment.length_m
        if remaining is not None:
            if remaining <= TOLERANCE:
                break
            length = min(length, remaining)

        if segment.signal is not None:
            tls_id, link_index = segment.signal
            program = programs.get(tls_id)
            if program is not None and not program.is_green(link_index, time):
                required.add(index)
                release = program.next_green_s(link_index, time)
                if release == math.inf:
                    return {
                        "reachable": False,
                        "reason": f"link {link_index} of {tls_id} is never green",
                        "time_s": math.inf,
                        "_required_stops": required,
                    }
                waits.append(
                    {
                        "tls_id": tls_id,
                        "link_index": link_index,
                        "arrived_at_line_s": round(time, 6),
                        "released_at_s": round(release, 6),
                        "waited_s": round(release - time, 6),
                    }
                )
                time = release
                speed = 0.0

        # Exit speed must be zero when the NEXT segment is one we have to stop before.
        if index + 1 in stopping:
            next_cap = 0.0
        elif index + 1 < len(segments):
            next_cap = segments[index + 1].speed_limit_mps
        else:
            next_cap = segment.speed_limit_mps

        duration, speed = traverse(length, speed, segment.speed_limit_mps, next_cap, accel, decel)
        time += duration
        if remaining is not None:
            remaining -= length

    return {
        "reachable": True,
        "time_s": time,
        "elapsed_s": time - start_time_s,
        "exit_speed_mps": speed,
        "signal_waits": waits,
        "total_wait_s": round(sum(w["waited_s"] for w in waits), 6),
        "_required_stops": required,
    }
