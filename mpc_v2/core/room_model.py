"""Control-oriented room temperature proxy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RoomParams:
    """Linear room-temperature proxy parameters."""

    initial_room_temp_c: float
    thermal_time_constant_h: float
    outdoor_gain_fraction: float
    it_heat_gain_c_per_mwh: float
    cooling_gain_c_per_mwh: float
    alpha_it_to_cooling: float

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "RoomParams":
        return cls(**{field: float(config[field]) for field in cls.__dataclass_fields__})

    def validate(self) -> None:
        if self.thermal_time_constant_h <= 0:
            raise ValueError("thermal_time_constant_h must be positive")
        if not 0 <= self.outdoor_gain_fraction <= 1:
            raise ValueError("outdoor_gain_fraction must be in [0, 1]")
        if self.it_heat_gain_c_per_mwh < 0 or self.cooling_gain_c_per_mwh < 0:
            raise ValueError("room heat/cooling gains must be non-negative")
        if self.alpha_it_to_cooling < 0:
            raise ValueError("alpha_it_to_cooling must be non-negative")


class RoomModel:
    """Linear plant model for synthetic closed-loop validation."""

    def __init__(self, params: RoomParams, dt_hours: float):
        if dt_hours <= 0:
            raise ValueError("dt_hours must be positive")
        params.validate()
        self.params = params
        self.dt_hours = float(dt_hours)

    def base_cooling_kw_th(self, it_load_kw: float) -> float:
        if it_load_kw < 0:
            raise ValueError("it_load_kw must be non-negative")
        return self.params.alpha_it_to_cooling * it_load_kw

    def next_temperature(
        self,
        room_temp_c: float,
        outdoor_temp_c: float,
        it_load_kw: float,
        base_cooling_kw_th: float,
        q_dis_tes_kw_th: float,
    ) -> float:
        """Advance the room proxy by one time step."""

        p = self.params
        dt = self.dt_hours
        ambient_pull = dt / p.thermal_time_constant_h
        outdoor_target = (1.0 - p.outdoor_gain_fraction) * room_temp_c + p.outdoor_gain_fraction * outdoor_temp_c
        return (
            room_temp_c
            + ambient_pull * (outdoor_target - room_temp_c)
            + p.it_heat_gain_c_per_mwh * it_load_kw * dt / 1000.0
            - p.cooling_gain_c_per_mwh * (base_cooling_kw_th + q_dis_tes_kw_th) * dt / 1000.0
        )
