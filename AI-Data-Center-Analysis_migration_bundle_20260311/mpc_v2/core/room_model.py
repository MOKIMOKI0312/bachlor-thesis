"""Simple room-temperature model for synthetic replay and MPC constraints."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoomParams:
    """1R1C-like temperature proxy expressed in Celsius per MWh terms."""

    initial_temperature_C: float
    thermal_time_constant_h: float
    outdoor_gain_fraction: float
    ite_heat_gain_C_per_mwh: float
    cooling_gain_C_per_mwh: float
    base_cooling_kw: float

    @classmethod
    def from_config(cls, config: dict) -> "RoomParams":
        return cls(**{field: float(config[field]) for field in cls.__dataclass_fields__})

    def validate(self) -> None:
        if self.thermal_time_constant_h <= 0:
            raise ValueError("thermal_time_constant_h must be positive")
        if self.base_cooling_kw < 0:
            raise ValueError("base_cooling_kw must be non-negative")
        if self.cooling_gain_C_per_mwh < 0 or self.ite_heat_gain_C_per_mwh < 0:
            raise ValueError("room gains must be non-negative")


class RoomModel:
    """Linear room-temperature proxy."""

    def __init__(self, params: RoomParams, dt_h: float = 0.25):
        if abs(dt_h - 0.25) > 1e-9:
            raise ValueError(f"RoomModel requires dt_h=0.25, got {dt_h}")
        params.validate()
        self.params = params
        self.dt_h = dt_h

    def next_temperature(
        self,
        temperature_C: float,
        outdoor_C: float,
        ite_kw: float,
        base_cooling_kw: float,
        tes_discharge_kw: float,
    ) -> float:
        """Advance the room proxy by one 15-minute step."""

        p = self.params
        ambient_pull = self.dt_h / p.thermal_time_constant_h
        outdoor_target = (1.0 - p.outdoor_gain_fraction) * temperature_C + p.outdoor_gain_fraction * outdoor_C
        return (
            temperature_C
            + ambient_pull * (outdoor_target - temperature_C)
            + p.ite_heat_gain_C_per_mwh * ite_kw * self.dt_h / 1000.0
            - p.cooling_gain_C_per_mwh * (base_cooling_kw + tes_discharge_kw) * self.dt_h / 1000.0
        )

