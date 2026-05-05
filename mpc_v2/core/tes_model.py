"""Linear chilled-water TES state model."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


@dataclass(frozen=True)
class TESParams:
    """Parameters for the TES SOC equation."""

    capacity_kwh_th: float
    eta_ch: float
    eta_dis: float
    lambda_loss_per_h: float
    q_ch_max_kw_th: float
    q_dis_max_kw_th: float
    initial_soc: float
    soc_physical_min: float
    soc_physical_max: float
    soc_planning_min: float
    soc_planning_max: float
    soc_target: float

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "TESParams":
        return cls(**{field: float(config[field]) for field in cls.__dataclass_fields__})

    def validate(self) -> None:
        for field_name in self.__dataclass_fields__:
            value = float(getattr(self, field_name))
            if not math.isfinite(value):
                raise ValueError(f"{field_name} must be finite, got {value}")
        if self.capacity_kwh_th <= 0:
            raise ValueError("capacity_kwh_th must be positive")
        if not 0 < self.eta_ch <= 1:
            raise ValueError("eta_ch must be in (0, 1]")
        if not 0 < self.eta_dis <= 1:
            raise ValueError("eta_dis must be in (0, 1]")
        if not 0 <= self.lambda_loss_per_h < 1:
            raise ValueError("lambda_loss_per_h must be in [0, 1)")
        if self.q_ch_max_kw_th < 0 or self.q_dis_max_kw_th < 0:
            raise ValueError("TES power limits must be non-negative")
        bounds = [
            self.soc_physical_min,
            self.soc_planning_min,
            self.initial_soc,
            self.soc_target,
            self.soc_planning_max,
            self.soc_physical_max,
        ]
        if any(v < 0 or v > 1 for v in bounds):
            raise ValueError("SOC values must be in [0, 1]")
        if not self.soc_physical_min <= self.soc_planning_min <= self.soc_planning_max <= self.soc_physical_max:
            raise ValueError("SOC physical and planning bounds are inconsistent")


class TESModel:
    """TES dynamics used by both the MILP and closed-loop plant update."""

    def __init__(self, params: TESParams, dt_hours: float):
        if not math.isfinite(float(dt_hours)) or dt_hours <= 0:
            raise ValueError(f"dt_hours must be positive and finite, got {dt_hours}")
        params.validate()
        self.params = params
        self.dt_hours = float(dt_hours)

    def next_soc(self, soc: float, q_ch_tes_kw_th: float, q_dis_tes_kw_th: float) -> float:
        """Advance SOC one control step without nonlinear clipping."""

        for name, value in {
            "soc": soc,
            "q_ch_tes_kw_th": q_ch_tes_kw_th,
            "q_dis_tes_kw_th": q_dis_tes_kw_th,
        }.items():
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite, got {value}")
        if not 0.0 <= soc <= 1.0:
            raise ValueError(f"soc must be in [0, 1], got {soc}")
        if q_ch_tes_kw_th < -1e-9 or q_dis_tes_kw_th < -1e-9:
            raise ValueError("TES charge/discharge power must be non-negative")
        if q_ch_tes_kw_th > self.params.q_ch_max_kw_th + 1e-9:
            raise ValueError("q_ch_tes_kw_th exceeds q_ch_max_kw_th")
        if q_dis_tes_kw_th > self.params.q_dis_max_kw_th + 1e-9:
            raise ValueError("q_dis_tes_kw_th exceeds q_dis_max_kw_th")
        if q_ch_tes_kw_th > 1e-6 and q_dis_tes_kw_th > 1e-6:
            raise ValueError("TES cannot charge and discharge simultaneously")
        p = self.params
        dt = self.dt_hours
        return (
            (1.0 - p.lambda_loss_per_h * dt) * soc
            + p.eta_ch * q_ch_tes_kw_th * dt / p.capacity_kwh_th
            - q_dis_tes_kw_th * dt / (p.eta_dis * p.capacity_kwh_th)
        )
