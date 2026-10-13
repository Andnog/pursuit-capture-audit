"""Public observation construction and the information boundary.

Everything the selector sees passes through `build_public_observation`. Nothing else may
construct an observation, so there is exactly one place where a prohibited field could be
introduced and exactly one place that has to be audited.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import CONTRACT_VERSION, load_domain, validate_observation


@dataclass(frozen=True)
class VehicleObservation:
    vehicle_id: str
    vehicle_class: str
    position_xy_m: tuple[float, float]
    speed_mps: float
    heading_rad: float
    lane_id: str
    lane_position_m: float
    body_length_m: float
    body_width_m: float

    def as_record(self) -> dict:
        return {
            "vehicle_id": self.vehicle_id,
            "vehicle_class": self.vehicle_class,
            "position_xy_m": list(self.position_xy_m),
            "speed_mps": self.speed_mps,
            "heading_rad": self.heading_rad,
            "lane_id": self.lane_id,
            "lane_position_m": self.lane_position_m,
            "body_length_m": self.body_length_m,
            "body_width_m": self.body_width_m,
        }


def build_public_observation(
    decision_index: int,
    vehicles: list[VehicleObservation],
    signals: list[dict] | None = None,
    topology_version: str = "unresolved",
    domain: dict | None = None,
) -> dict:
    """Build and validate one public observation.

    `simulation_time_s` is DERIVED from the decision index and the contract interval; it is
    never passed in. A caller that could supply its own clock could desynchronise the
    observation from the decision it belongs to.
    """
    domain = domain or load_domain()
    interval = domain["timing"]["decision_interval_s"]
    record = {
        "contract_version": CONTRACT_VERSION,
        "simulation_time_s": decision_index * interval,
        "decision_index": decision_index,
        "topology_version": topology_version,
        "vehicles": [v.as_record() for v in vehicles],
        "signals": list(signals or []),
    }
    validate_observation(record)
    return record


def selector_inputs(observation: dict) -> dict:
    """The exact subset handed to the selector.

    The observation is already the public projection, so this is the identity on its
    fields. It exists as a single named chokepoint: if a later stage adds a field to the
    observation for logging, this function is where the decision to expose it to the
    selector must be made explicitly.
    """
    return {
        "decision_index": observation["decision_index"],
        "simulation_time_s": observation["simulation_time_s"],
        "vehicles": observation["vehicles"],
        "signals": observation["signals"],
        "topology_version": observation["topology_version"],
    }
