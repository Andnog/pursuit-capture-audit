"""Transition contract for decision-level training (A-137, fifth review, finding F5-1).

A controller that decides every few seconds records one decision tick per decision: the
observation and the action taken at time t_k. Training needs TRANSITIONS, not ticks:

    observation at t_k, action at t_k, the interval (t_k, t_end_k] during which the action was in
    force, the reward earned in that interval, and whether the trained interval ends there.

The trained interval of an episode ends at the first terminal event: the training objective is
reached (`event_s`: operational capture, or first proximity when that is the reward), or the
simulation ends (`trace_end_s`: horizon or evader exit).

Rules, each fixing one defect of the earlier code (`train_mappo_v2.truncate_ticks` and
`episode_rewards`, both kept unchanged):

1. A decision is trainable only if it is taken strictly before the end of the trained interval.
   A decision at or after the end has no future inside the episode: it is a terminal observation,
   kept for the record and never trained. The earlier code kept every tick with t <= end, so it
   trained the decision taken at the horizon and, when a capture completed exactly on a tick, the
   decision taken after the capture was already complete.
2. The reward of the objective belongs to the transition in whose interval the event occurs, that
   is, to the last decision taken BEFORE it.
3. The time cost of a transition is proportional to its duration, so an interval cut short by the
   event costs less than a full one and the total time cost of an episode is exact.
4. The collision penalty is applied once, to the transition in whose interval the first collision
   inside the trained interval occurs. Collisions after the end (or before the first decision) are
   recorded and not penalised. The earlier code used an episode-level flag, so a collision after
   the cut penalised a prefix that had already ended.
5. Non-finite or disordered times are rejected.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

EPS = 1e-9


class TransitionError(ValueError):
    """The recorded times cannot be turned into transitions."""


@dataclass(frozen=True)
class Transition:
    tick: int  # index of the decision among the recorded ticks
    t_decision_s: float
    t_end_s: float
    duration_s: float
    reward: float
    terminal: bool  # the trained interval ends with this transition
    collision: bool  # the collision penalty was applied here
    next_tick: int | None  # recorded observation at t_end_s, if the interval ends on a tick


@dataclass(frozen=True)
class TransitionSet:
    transitions: tuple[Transition, ...]
    end_s: float
    end_reason: str  # "event" or the reason given for the end of the trace
    event_s: float | None
    recorded_ticks: int
    terminal_observation_ticks: tuple[int, ...]  # recorded, never trained
    collisions_in_interval: tuple[float, ...]
    collisions_outside: tuple[float, ...]
    exclusion: str | None  # why nothing is trainable, when transitions is empty

    @property
    def rewards(self) -> list[float]:
        return [tr.reward for tr in self.transitions]

    @property
    def ticks(self) -> list[int]:
        return [tr.tick for tr in self.transitions]


def _finite(name, value):
    try:
        ok = math.isfinite(value)
    except TypeError:
        ok = False
    if not ok:
        raise TransitionError(f"{name} is not a finite number: {value!r}")


def build_transitions(
    tick_times,
    *,
    trace_end_s: float,
    event_s: float | None = None,
    collision_times=(),
    trace_end_reason: str = "trace_end",
    decide_s: float = 3.0,
    step_cost: float = 0.005,
    event_reward: float = 1.0,
    collision_penalty: float = 1.0,
) -> TransitionSet:
    """Transitions of one episode from its recorded decision times; see the module docstring."""
    times = [float(t) for t in tick_times]
    for k, t in enumerate(times):
        _finite(f"tick {k}", t)
    for a, b in zip(times, times[1:], strict=False):
        if b <= a + EPS:
            raise TransitionError(f"decision times are not increasing: {a!r}, {b!r}")
    _finite("trace_end_s", trace_end_s)
    _finite("decide_s", decide_s)
    if decide_s <= 0.0:
        raise TransitionError("decide_s must be positive")
    if event_s is not None:
        _finite("event_s", event_s)
        if event_s > trace_end_s + EPS:
            raise TransitionError(f"event at {event_s!r} after the trace end {trace_end_s!r}")
    collisions = sorted(float(c) for c in collision_times)
    for c in collisions:
        _finite("collision time", c)

    end = float(trace_end_s) if event_s is None else float(event_s)
    reason = trace_end_reason if event_s is None else "event"
    trainable = [k for k, t in enumerate(times) if t < end - EPS]
    terminal_observations = tuple(k for k, t in enumerate(times) if t >= end - EPS)
    first = times[trainable[0]] if trainable else None
    inside = tuple(c for c in collisions if first is not None and first + EPS < c <= end + EPS)
    outside = tuple(c for c in collisions if c not in inside)

    exclusion = None
    if not times:
        exclusion = "no_decision_recorded"
    elif not trainable:
        exclusion = "ended_before_first_decision"

    penalised = inside[0] if inside else None
    out = []
    for position, k in enumerate(trainable):
        t = times[k]
        has_next = k + 1 < len(times)
        t_end = min(times[k + 1], end) if has_next else end
        duration = t_end - t
        last = position == len(trainable) - 1
        reward = -step_cost * duration / decide_s
        if last and event_s is not None:
            reward += event_reward
        hit = penalised is not None and t + EPS < penalised <= t_end + EPS
        if hit:
            reward -= collision_penalty
        on_tick = has_next and abs(times[k + 1] - t_end) <= EPS
        out.append(
            Transition(
                tick=k,
                t_decision_s=t,
                t_end_s=t_end,
                duration_s=duration,
                reward=reward,
                terminal=last,
                collision=hit,
                next_tick=k + 1 if on_tick else None,
            )
        )
    return TransitionSet(
        transitions=tuple(out),
        end_s=end,
        end_reason=reason,
        event_s=None if event_s is None else float(event_s),
        recorded_ticks=len(times),
        terminal_observation_ticks=terminal_observations,
        collisions_in_interval=inside,
        collisions_outside=outside,
        exclusion=exclusion,
    )


def discounted_returns(rewards, gamma: float) -> list[float]:
    """Return from every transition; the value after the last transition is 0 (terminal)."""
    out, g = [0.0] * len(rewards), 0.0
    for t in reversed(range(len(rewards))):
        g = rewards[t] + gamma * g
        out[t] = g
    return out


def gae(rewards, values, gamma: float, lam: float) -> list[float]:
    """Generalised advantage estimates over the transitions of one episode.

    `values[k]` is the critic's value of the observation of transition k. The value after the last
    transition is 0: the trained interval ends there (objective reached, or a finite horizon with
    time in the state).
    """
    if len(rewards) != len(values):
        raise TransitionError("one value per transition is required")
    adv, last = [0.0] * len(rewards), 0.0
    for t in reversed(range(len(rewards))):
        nxt = values[t + 1] if t + 1 < len(rewards) else 0.0
        delta = rewards[t] + gamma * nxt - values[t]
        last = delta + gamma * lam * last
        adv[t] = last
    return adv


__all__ = [
    "Transition",
    "TransitionError",
    "TransitionSet",
    "build_transitions",
    "discounted_returns",
    "gae",
]
