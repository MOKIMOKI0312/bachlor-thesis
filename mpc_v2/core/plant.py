"""Small plant model for the rebuilt closed-loop MPC path."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PlantParams:
    """Minimal chiller plant parameters used by all v1 controllers."""

    cop: float
    cooling_load_ratio: float
    room_initial_temp_c: float
    room_drift_per_h: float

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "PlantParams":
        facility = cfg.get("facility", {})
        room = cfg.get("room", {})
        return cls(
            cop=float(facility.get("cop_charge", facility.get("cop", 5.2))),
            cooling_load_ratio=float(room.get("alpha_it_to_cooling", 0.12)),
            room_initial_temp_c=float(room.get("initial_room_temp_c", 24.0)),
            room_drift_per_h=float(room.get("room_drift_per_h", 0.02)),
        )

    def validate(self) -> None:
        if self.cop <= 0:
            raise ValueError("cop must be positive")
        if self.cooling_load_ratio < 0:
            raise ValueError("cooling_load_ratio must be non-negative")


def chiller_power_kw(q_chiller_kw_th: float, plant: PlantParams) -> float:
    """Convert thermal cooling to electric plant power."""

    plant.validate()
    return max(0.0, float(q_chiller_kw_th)) / plant.cop


def grid_and_spill_kw(it_load_kw: float, plant_power_kw: float, pv_kw: float) -> tuple[float, float]:
    """Split net load into grid import and PV spill."""

    net = float(it_load_kw) + float(plant_power_kw) - float(pv_kw)
    return max(0.0, net), max(0.0, -net)


def next_room_temp_c(room_temp_c: float, outdoor_temp_c: float, plant: PlantParams, dt_hours: float) -> float:
    """Deterministic proxy room temperature update.

    The rebuilt v1 controller assumes the cooling load proxy is fully served; room
    temperature is therefore a slow exogenous drift toward outdoor conditions.
    """

    drift = plant.room_drift_per_h * float(dt_hours) * (float(outdoor_temp_c) - float(room_temp_c)) / 10.0
    return float(room_temp_c) + drift
