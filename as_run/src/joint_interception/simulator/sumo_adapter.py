"""The episode adapter, and the TraCI backend it will use at W4.

The adapter is backend-independent: it builds public observations, computes validity
masks, enforces the inference deadline, applies the contract fallback and records proposed
and executed commands separately. All of that is validated offline at W3 against
`DeterministicBackend`.

`TraciBackend` is written against the pinned TraCI API of SUMO 1.21.0 and is **NOT executed
at W3**. No SUMO process is started in this stage: native execution is gated behind W4 and
W5, which require the D06 freeze, a validated arrival model and the O22 safety evidence
that remains open. Its first execution is a W4 action under that stage's gate.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from ..domain.actions import FALLBACK_ACTION_ID, build_action, choose_with_fallback
from ..domain.contracts import load_domain
from ..domain.geometry import Rectangle, body_separation_m
from ..domain.observations import VehicleObservation, build_public_observation
from .backend import Command, SimulatorBackend, VehicleState


@dataclass
class DecisionRecord:
    """One decision, with proposed and executed kept apart."""

    decision_index: int
    vehicle_id: str
    proposed_action_id: str
    executed_action_id: str
    selection_label: str
    executed_command: Command | None
    deadline_miss: bool
    guard_clamped: bool
    mask: dict[str, bool]
    reasons: list[str] = field(default_factory=list)


class EpisodeAdapter:
    """Drives one episode over any `SimulatorBackend`."""

    def __init__(
        self,
        backend: SimulatorBackend,
        domain: dict | None = None,
        topology_version: str = "deterministic_v1",
    ):
        self.backend = backend
        self.domain = domain or load_domain()
        self.topology_version = topology_version
        self.decision_index = 0
        self.records: list[DecisionRecord] = []
        self._steps_per_decision = self.domain["timing"]["physical_steps_per_decision"]
        self._deadline_s = self.domain["action_menu"]["inference_deadline_s"]
        self._geometry_tolerance = self.domain["capture_predicate"]["parameters"][
            "geometry_tolerance_m"
        ]["value"]

    # -- observation ----------------------------------------------------------------

    def observe(self) -> dict:
        """Build the public observation. The ONLY route from backend state to selector."""
        observations = [
            VehicleObservation(
                vehicle_id=state.vehicle_id,
                vehicle_class=state.vehicle_class,
                position_xy_m=(state.x, state.y),
                speed_mps=state.speed_mps,
                heading_rad=state.heading_rad,
                lane_id=state.lane_id,
                lane_position_m=state.lane_position_m,
                body_length_m=state.body_length_m,
                body_width_m=state.body_width_m,
            )
            for state in (self.backend.vehicle_state(vid) for vid in self.backend.vehicle_ids())
        ]
        return build_public_observation(
            decision_index=self.decision_index,
            vehicles=observations,
            topology_version=self.topology_version,
            domain=self.domain,
        )

    # -- masks ----------------------------------------------------------------------

    def action_mask(self, vehicle_id: str) -> list[dict]:
        """The per-vehicle action menu with validity bits from the public state.

        `HOLD_LANE` is declared always valid, so a fallback always exists. Speed-increasing
        actions are refused when a body ahead is close enough that the next decision
        interval could close the gap.
        """
        actor = self._rectangle(vehicle_id)
        others = {
            vid: self._rectangle(vid) for vid in self.backend.vehicle_ids() if vid != vehicle_id
        }
        gap = min(
            (body_separation_m(actor, body) for body in others.values()), default=float("inf")
        )
        speed = self.backend.vehicle_state(vehicle_id).speed_mps
        reachable = speed * self.domain["timing"]["decision_interval_s"]
        crowded = gap - reachable <= self._geometry_tolerance

        actions = [build_action(vehicle_id, FALLBACK_ACTION_ID, True, domain=self.domain)]
        for action_id, parameters in (
            ("CRUISE", {"target_speed_fraction": 1.0}),
            ("SLOW", {"target_speed_fraction": 0.5}),
        ):
            valid = not crowded if action_id == "CRUISE" else True
            actions.append(
                build_action(
                    vehicle_id,
                    action_id,
                    valid,
                    parameters,
                    invalid_reason=None if valid else "neighbour_within_one_decision_interval",
                    domain=self.domain,
                )
            )
        return actions

    def _rectangle(self, vehicle_id: str) -> Rectangle:
        state: VehicleState = self.backend.vehicle_state(vehicle_id)
        return Rectangle(
            state.x, state.y, state.heading_rad, state.body_length_m, state.body_width_m
        )

    # -- decision -------------------------------------------------------------------

    def decide_and_step(
        self,
        selector: Callable[[dict, str, list[dict]], int | None],
        speed_limit_mps: float = 13.89,
    ) -> list[DecisionRecord]:
        """One decision interval: observe, select under a deadline, execute, advance.

        A selector that exceeds the inference deadline does NOT get its action applied. The
        deadline miss is recorded and the always-valid fallback executes, because a late
        action is an action taken on a stale world.
        """
        observation = self.observe()
        made: list[DecisionRecord] = []

        for vehicle_id in self.backend.vehicle_ids():
            state = self.backend.vehicle_state(vehicle_id)
            if state.vehicle_class != "pursuer":
                continue
            actions = self.action_mask(vehicle_id)

            started = time.perf_counter()
            chosen = selector(observation, vehicle_id, actions)
            elapsed = time.perf_counter() - started
            deadline_miss = elapsed > self._deadline_s
            if deadline_miss:
                chosen = None

            proposed = self._action_at(actions, chosen)
            executed, label = choose_with_fallback(actions, chosen)
            command, clamped = self._command_for(vehicle_id, executed, speed_limit_mps)
            self.backend.queue_command(command)

            made.append(
                DecisionRecord(
                    decision_index=self.decision_index,
                    vehicle_id=vehicle_id,
                    proposed_action_id=proposed,
                    executed_action_id=executed["action_id"],
                    selection_label="DEADLINE_FALLBACK" if deadline_miss else label,
                    executed_command=command,
                    deadline_miss=deadline_miss,
                    guard_clamped=clamped,
                    mask={a["action_id"]: a["valid"] for a in actions},
                )
            )

        self.records.extend(made)
        self.backend.step(self._steps_per_decision)
        self.decision_index += 1
        return made

    @staticmethod
    def _action_at(actions: list[dict], index: int | None) -> str:
        selectable = [a for a in actions if a["valid"]]
        if index is None or not (0 <= index < len(selectable)):
            return FALLBACK_ACTION_ID
        return selectable[index]["action_id"]

    def _command_for(
        self, vehicle_id: str, action: dict, speed_limit_mps: float
    ) -> tuple[Command, bool]:
        """Translate an action into an executed command, clamping to the legal limit.

        Clamping is recorded on the command, so a proposal and its execution remain
        distinguishable even when two different intentions produce the same command.
        """
        current = self.backend.vehicle_state(vehicle_id).speed_mps
        action_id = action["action_id"]
        if action_id == "CRUISE":
            requested = speed_limit_mps * action["parameters"]["target_speed_fraction"]
        elif action_id == "SLOW":
            requested = current * action["parameters"]["target_speed_fraction"]
        else:
            requested = current
        target = min(requested, speed_limit_mps)
        clamped = target < requested - 1e-12
        return (
            Command(vehicle_id, target, clamped_from=requested if clamped else None),
            clamped,
        )


class TraciBackend:
    """SUMO 1.21.0 backend over the TraCI socket interface.

    First executed at W4 under `experiments/20260922_w04_traci_first_execution_r01`. Before
    that package no SUMO process had been started in this root.

    Two facts recorded at W2 shape this design and are repeated where they bite:

    - `libsumo` is unavailable on this platform, so the socket interface is the only option.
      It is slower and its determinism guarantees are weaker, which bears directly on the
      replay coupling the assistance audit requires.
    - The SUMO binary and the Python bindings come from different distribution channels and
      can drift apart silently. `scripts/preflight.py` must pass before this class is used.

    **Safety checks are left ON.** `setSpeed` is a request, not a guarantee: SUMO's
    car-following and junction logic may execute something slower. The executed speed is
    therefore read back from the simulator rather than assumed, which is the same
    proposed-versus-executed separation the task contract requires of the action layer.
    """

    IMPLEMENTATION_STATUS = "IMPLEMENTED_W4_FIRST_EXECUTED_2026_09_22"

    #: SUMO reports angles in degrees clockwise from north; the project uses radians
    #: counter-clockwise from +x.
    @staticmethod
    def heading_rad_from_sumo_angle(angle_deg: float) -> float:
        return math.radians((90.0 - angle_deg) % 360.0)

    @staticmethod
    def centre_from_front(
        x: float, y: float, heading_rad: float, length_m: float
    ) -> tuple[float, float]:
        """SUMO reports a vehicle's FRONT BUMPER; the project's `Rectangle` is CENTRED.

        Passing the bumper straight through shifted every body half a length forward along
        its own heading. On one lane with one heading both bodies shift alike and the
        separation survives, which is why no single-lane test noticed. Across a junction,
        where headings differ, the separations the capture judge and the safety admission
        compute were wrong by up to a body length - exactly where interception happens.
        """
        half = length_m / 2.0
        return x - half * math.cos(heading_rad), y - half * math.sin(heading_rad)

    def __init__(
        self,
        net_file: str,
        *,
        seed: int,
        step_s: float,
        sumo_binary: str,
        label: str = "default",
        collision_action: str = "warn",
        extra_args: list[str] | None = None,
    ):
        import traci  # imported here so the module remains importable without SUMO

        self._traci = traci
        self._label = label
        self._step_s = step_s
        self._seed = seed
        self._closed = False
        self._pending: dict[str, Command] = {}
        self._lane_length_cache: dict[str, float] = {}
        self._collision_action = collision_action
        # Per-instance, deliberately. A class-level dict here would be shared by every
        # backend in the process, which is exactly the kind of silent cross-run coupling
        # the assistance audit must not have.
        self._classes: dict[str, str] = {}
        self._state_path: str | None = None

        command = [
            sumo_binary,
            "-n",
            net_file,
            "--step-length",
            repr(step_s),
            "--seed",
            str(seed),
            "--collision.action",
            collision_action,
            # Determinism: without this SUMO draws a per-vehicle speed factor.
            "--default.speeddev",
            "0",
            "--no-step-log",
            "true",
            "--time-to-teleport",
            "-1",
            "--quit-on-end",
            "true",
        ]
        if extra_args:
            command += extra_args
        self._start_command = command
        traci.start(command, label=label)
        self._connection = traci.getConnection(label)

    @property
    def connection(self):
        """The TraCI connection, for replay harnesses that need calls this surface omits."""
        return self._connection

    # -- construction helpers -------------------------------------------------------

    def add_route(self, route_id: str, edges: list[str]) -> None:
        self._connection.route.add(route_id, edges)

    def find_route_edges(self, from_edge: str, to_edge: str) -> list[str]:
        return list(self._connection.simulation.findRoute(from_edge, to_edge).edges)

    def add_vehicle(
        self,
        vehicle_id: str,
        route_id: str,
        *,
        type_id: str,
        depart_position_m: float,
        depart_speed_mps: float,
        body_length_m: float,
        body_width_m: float,
        min_gap_m: float,
        imperfection: float | None = None,
        depart_lane: str | None = None,
    ) -> None:
        """Add one vehicle with the body dimensions the domain contract declares.

        A distinct vehicle type is created per vehicle so that the body dimensions come from
        `configs/domain_v1.json` rather than from a SUMO default, which is the arithmetic
        that failed in the historical O22 collision at 21.8 s.
        """
        own_type = f"{type_id}_{vehicle_id}"
        self._connection.vehicletype.copy(type_id, own_type)
        self._connection.vehicletype.setLength(own_type, body_length_m)
        self._connection.vehicletype.setWidth(own_type, body_width_m)
        self._connection.vehicletype.setMinGap(own_type, min_gap_m)
        if imperfection is not None:
            # Krauss driver imperfection (sigma). SUMO's default is 0.5, which is
            # STOCHASTIC: it draws from SUMO's own random stream every step. Setting it to
            # 0 makes the car-following deterministic, which is how the W4 first-execution
            # package isolates unrestored randomness from an inability to restore state.
            self._connection.vehicletype.setImperfection(own_type, imperfection)
        self._connection.vehicle.add(
            vehicle_id,
            route_id,
            typeID=own_type,
            departPos=str(depart_position_m),
            departSpeed=str(depart_speed_mps),
            **({"departLane": depart_lane} if depart_lane is not None else {}),
        )

    def assign_class(self, vehicle_id: str, vehicle_class: str) -> None:
        self._classes[vehicle_id] = vehicle_class

    # -- SimulatorBackend -----------------------------------------------------------

    @property
    def time_s(self) -> float:
        return float(self._connection.simulation.getTime())

    def vehicle_ids(self) -> list[str]:
        return sorted(self._connection.vehicle.getIDList())

    def vehicle_state(self, vehicle_id: str) -> VehicleState:
        conn = self._connection
        front_x, front_y = conn.vehicle.getPosition(vehicle_id)
        heading = self.heading_rad_from_sumo_angle(conn.vehicle.getAngle(vehicle_id))
        length = conn.vehicle.getLength(vehicle_id)
        x, y = self.centre_from_front(front_x, front_y, heading, length)
        return VehicleState(
            vehicle_id=vehicle_id,
            vehicle_class=self._classes.get(vehicle_id, "pursuer"),
            x=x,
            y=y,
            heading_rad=heading,
            speed_mps=conn.vehicle.getSpeed(vehicle_id),
            lane_id=conn.vehicle.getLaneID(vehicle_id),
            lane_position_m=conn.vehicle.getLanePosition(vehicle_id),
            body_length_m=conn.vehicle.getLength(vehicle_id),
            body_width_m=conn.vehicle.getWidth(vehicle_id),
        )

    def lane_length_m(self, lane_id: str) -> float:
        if lane_id not in self._lane_length_cache:
            self._lane_length_cache[lane_id] = float(self._connection.lane.getLength(lane_id))
        return self._lane_length_cache[lane_id]

    def queue_command(self, command: Command) -> None:
        self._pending[command.vehicle_id] = command

    def pending_commands(self) -> dict[str, Command]:
        return dict(self._pending)

    def step(self, count: int = 1) -> None:
        if self._closed:
            raise RuntimeError("backend is closed")
        live = set(self._connection.vehicle.getIDList())
        for vehicle_id, command in sorted(self._pending.items()):
            if vehicle_id in live:
                self._connection.vehicle.setSpeed(vehicle_id, command.target_speed_mps)
        for _ in range(count):
            self._connection.simulationStep()

    def capture_state(self) -> dict:
        """Ask SUMO to write its own state, and record ours alongside it.

        SUMO's state file is the only complete description of its internals; nothing in the
        TraCI surface exposes them. Whether reloading it reproduces a continuation exactly
        is an empirical question about SUMO, answered in the W4 first-execution package and
        NOT assumed here.
        """
        if self._state_path is None:
            raise RuntimeError("capture_state requires a state_path; set one with use_state_path()")
        self._connection.simulation.saveState(self._state_path)
        return {
            "sumo_state_file": self._state_path,
            "time_s": self.time_s,
            "vehicle_ids": self.vehicle_ids(),
            "pending_commands": {
                vid: {
                    "vehicle_id": c.vehicle_id,
                    "target_speed_mps": c.target_speed_mps,
                    "clamped_from": c.clamped_from,
                }
                for vid, c in sorted(self._pending.items())
            },
        }

    def use_state_path(self, path: str) -> None:
        self._state_path = path

    def restore_state(self, state: dict) -> None:
        self._connection.simulation.loadState(state["sumo_state_file"])
        self._pending = {
            vid: Command(**payload) for vid, payload in state["pending_commands"].items()
        }

    def close(self) -> None:
        if not self._closed:
            self._connection.close()
            self._closed = True

    # -- provenance -----------------------------------------------------------------

    def start_command(self) -> list[str]:
        return list(self._start_command)
