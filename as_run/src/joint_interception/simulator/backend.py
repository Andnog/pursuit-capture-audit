"""The simulator backend protocol and a deterministic in-memory implementation.

Why a protocol. The adapter must be validated before any SUMO process may be started:
native execution is gated behind W4/W5, and obligation O22 exists because native steps
were once taken before their proofs. Writing the adapter against a narrow protocol lets
everything above that protocol be checked exactly, and confines what remains unchecked to
the TraCI call surface itself.

`DeterministicBackend` is not a simulator and is not claimed to be one. It is a kinematic
fixture with exact, inspectable state, whose purpose is to make state restoration and the
information boundary testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class VehicleState:
    """One vehicle's physical state, in the frame the adapter publishes."""

    vehicle_id: str
    vehicle_class: str
    x: float
    y: float
    heading_rad: float
    speed_mps: float
    lane_id: str
    lane_position_m: float
    body_length_m: float
    body_width_m: float


@dataclass(frozen=True)
class Command:
    """An executed command, distinct from the action that proposed it.

    `clamped_from` records the originally requested value when a guard reduced it. The
    contract requires proposed and executed to be logged separately, and finite assistance
    case A4 exists because different intentions can produce the same executed command.
    """

    vehicle_id: str
    target_speed_mps: float
    clamped_from: float | None = None

    @property
    def was_clamped(self) -> bool:
        return self.clamped_from is not None


@runtime_checkable
class SimulatorBackend(Protocol):
    """The minimum a simulator must provide. Deliberately small."""

    @property
    def time_s(self) -> float: ...

    def vehicle_ids(self) -> list[str]: ...

    def vehicle_state(self, vehicle_id: str) -> VehicleState: ...

    def lane_length_m(self, lane_id: str) -> float: ...

    def queue_command(self, command: Command) -> None: ...

    def pending_commands(self) -> dict[str, Command]: ...

    def step(self, count: int = 1) -> None: ...

    def capture_state(self) -> dict: ...

    def restore_state(self, state: dict) -> None: ...

    def close(self) -> None: ...


class DeterministicRandom:
    """A small explicit linear congruential stream.

    The standard library generator would serve, but an explicit stream makes two things
    visible that matter for the assistance audit: the state is a single integer that can be
    snapshotted exactly, and the DRAW COUNT is observable. A shared seed is not a shared
    noise realisation once two runs consume different numbers of draws, and that is
    demonstrated rather than asserted.
    """

    MODULUS = 2**48
    MULTIPLIER = 25214903917
    INCREMENT = 11

    def __init__(self, seed: int):
        self._seed = seed % self.MODULUS
        self._draws = 0

    @property
    def draws(self) -> int:
        return self._draws

    def next_float(self) -> float:
        self._seed = (self.MULTIPLIER * self._seed + self.INCREMENT) % self.MODULUS
        self._draws += 1
        return self._seed / self.MODULUS

    def capture(self) -> dict:
        return {"seed": self._seed, "draws": self._draws}

    def restore(self, state: dict) -> None:
        self._seed = int(state["seed"])
        self._draws = int(state["draws"])


@dataclass
class DeterministicBackend:
    """An in-memory kinematic backend on a straight single-lane corridor.

    Vehicles move along `+x` at their current speed, approaching a commanded target speed
    under a bounded acceleration. A small stochastic perturbation is drawn each step for
    each vehicle, so that random-stream handling is exercised rather than trivially absent.
    """

    step_s: float = 0.1
    max_acceleration_mps2: float = 2.6
    max_deceleration_mps2: float = 4.5
    lane_length_m: float = 1000.0
    perturbation_mps: float = 0.01
    _time_s: float = 0.0
    _vehicles: dict[str, VehicleState] = field(default_factory=dict)
    _pending: dict[str, Command] = field(default_factory=dict)
    _random: DeterministicRandom = field(default_factory=lambda: DeterministicRandom(0))
    _closed: bool = False

    @staticmethod
    def build(vehicles: list[VehicleState], seed: int, **kwargs) -> DeterministicBackend:
        backend = DeterministicBackend(**kwargs)
        backend._vehicles = {v.vehicle_id: v for v in vehicles}
        backend._random = DeterministicRandom(seed)
        return backend

    @property
    def time_s(self) -> float:
        return self._time_s

    @property
    def draws(self) -> int:
        return self._random.draws

    def vehicle_ids(self) -> list[str]:
        return sorted(self._vehicles)

    def vehicle_state(self, vehicle_id: str) -> VehicleState:
        return self._vehicles[vehicle_id]

    def queue_command(self, command: Command) -> None:
        if command.vehicle_id not in self._vehicles:
            raise KeyError(f"unknown vehicle {command.vehicle_id!r}")
        self._pending[command.vehicle_id] = command

    def pending_commands(self) -> dict[str, Command]:
        return dict(self._pending)

    def step(self, count: int = 1) -> None:
        if self._closed:
            raise RuntimeError("backend is closed")
        for _ in range(count):
            self._advance_one_step()

    def _advance_one_step(self) -> None:
        updated: dict[str, VehicleState] = {}
        for vehicle_id in sorted(self._vehicles):
            state = self._vehicles[vehicle_id]
            command = self._pending.get(vehicle_id)
            target = command.target_speed_mps if command else state.speed_mps
            delta = target - state.speed_mps
            limit = (
                self.max_acceleration_mps2 if delta >= 0 else self.max_deceleration_mps2
            ) * self.step_s
            speed = state.speed_mps + math.copysign(min(abs(delta), limit), delta)
            # One draw per vehicle per step, in a fixed vehicle order, so the number of
            # draws is a deterministic function of the number of steps and vehicles.
            speed = max(0.0, speed + (self._random.next_float() - 0.5) * self.perturbation_mps)
            travelled = speed * self.step_s
            updated[vehicle_id] = replace(
                state,
                x=state.x + travelled * math.cos(state.heading_rad),
                y=state.y + travelled * math.sin(state.heading_rad),
                speed_mps=speed,
                lane_position_m=min(state.lane_position_m + travelled, self.lane_length_m),
            )
        self._vehicles = updated
        self._time_s = round(self._time_s + self.step_s, 9)

    def capture_state(self) -> dict:
        """Complete state: clock, bodies, PENDING COMMANDS and the random stream.

        Omitting pending commands would make a restored run diverge on its first step while
        looking correct at the moment of capture, which is the failure mode the assistance
        replay must not have.
        """
        return {
            "time_s": self._time_s,
            "vehicles": {
                vid: {
                    "vehicle_id": v.vehicle_id,
                    "vehicle_class": v.vehicle_class,
                    "x": v.x,
                    "y": v.y,
                    "heading_rad": v.heading_rad,
                    "speed_mps": v.speed_mps,
                    "lane_id": v.lane_id,
                    "lane_position_m": v.lane_position_m,
                    "body_length_m": v.body_length_m,
                    "body_width_m": v.body_width_m,
                }
                for vid, v in sorted(self._vehicles.items())
            },
            "pending_commands": {
                vid: {
                    "vehicle_id": c.vehicle_id,
                    "target_speed_mps": c.target_speed_mps,
                    "clamped_from": c.clamped_from,
                }
                for vid, c in sorted(self._pending.items())
            },
            "random": self._random.capture(),
        }

    def restore_state(self, state: dict) -> None:
        self._time_s = float(state["time_s"])
        self._vehicles = {
            vid: VehicleState(**payload) for vid, payload in state["vehicles"].items()
        }
        self._pending = {
            vid: Command(**payload) for vid, payload in state["pending_commands"].items()
        }
        self._random.restore(state["random"])

    def close(self) -> None:
        self._closed = True
