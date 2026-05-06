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
        """Nominal reference only; closed-loop cooling must come from chiller/TES actions."""

        if it_load_kw < 0:
            raise ValueError("it_load_kw must be non-negative")
        return self.params.alpha_it_to_cooling * it_load_kw

    def coefficients(self) -> tuple[float, float, float, float]:
        """Return linear coefficients for T_next = a*T + b_out*T_out + b_it*IT - b_c*q_cool."""

        p = self.params
        dt = self.dt_hours
        temp_a = 1.0 - dt * p.outdoor_gain_fraction / p.thermal_time_constant_h
        temp_out_gain = dt * p.outdoor_gain_fraction / p.thermal_time_constant_h
        heat_gain = p.it_heat_gain_c_per_mwh * dt / 1000.0
        cooling_gain = p.cooling_gain_c_per_mwh * dt / 1000.0
        return temp_a, temp_out_gain, heat_gain, cooling_gain

    def next_temperature(
        self,
        room_temp_c: float,
        outdoor_temp_c: float,
        it_load_kw: float,
        q_cooling_total_kw_th: float | None = None,
        base_cooling_kw_th: float | None = None,
        q_dis_tes_kw_th: float | None = None,
    ) -> float:
        """Advance the room proxy by one time step."""

        has_total = q_cooling_total_kw_th is not None
        has_components = base_cooling_kw_th is not None or q_dis_tes_kw_th is not None
        if has_total and has_components:
            raise ValueError("pass either q_cooling_total_kw_th or base/q_dis components, not both")
        if q_cooling_total_kw_th is None:
            q_cooling_total_kw_th = float(base_cooling_kw_th or 0.0) + float(q_dis_tes_kw_th or 0.0)
        if it_load_kw < 0 or q_cooling_total_kw_th < -1e-9:
            raise ValueError("it_load_kw and q_cooling_total_kw_th must be non-negative")
        temp_a, temp_out_gain, heat_gain, cooling_gain = self.coefficients()
        return (
            temp_a * float(room_temp_c)
            + temp_out_gain * float(outdoor_temp_c)
            + heat_gain * float(it_load_kw)
            - cooling_gain * max(0.0, float(q_cooling_total_kw_th))
        )

    def required_cooling_kw_th(
        self,
        room_temp_c: float,
        outdoor_temp_c: float,
        it_load_kw: float,
        target_next_temp_c: float,
    ) -> float:
        """Cooling needed to hit a one-step target under the linear proxy."""

        temp_a, temp_out_gain, heat_gain, cooling_gain = self.coefficients()
        if cooling_gain <= 0:
            return 0.0
        no_cooling_next = temp_a * room_temp_c + temp_out_gain * outdoor_temp_c + heat_gain * it_load_kw
        return max(0.0, (no_cooling_next - target_next_temp_c) / cooling_gain)
