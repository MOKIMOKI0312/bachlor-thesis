"""Control-oriented TES state model."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class TESParams:
    """Parameters for a linear chilled-water TES SOC model."""

    effective_capacity_kwh: float
    charge_efficiency: float
    discharge_efficiency: float
    standing_loss_per_h: float
    max_charge_kw: float
    max_discharge_kw: float
    initial_soc: float
    soc_min_phys: float
    soc_max_phys: float
    soc_min_plan: float
    soc_max_plan: float
    terminal_soc_target: float

    @classmethod
    def from_config(cls, config: dict) -> "TESParams":
        return cls(**{field: float(config[field]) for field in cls.__dataclass_fields__})

    def validate(self) -> None:
        for field_name in self.__dataclass_fields__:
            value = float(getattr(self, field_name))
            if not math.isfinite(value):
                raise ValueError(f"{field_name} must be finite, got {value}")
        if self.effective_capacity_kwh <= 0:
            raise ValueError("effective_capacity_kwh must be positive")
        if not 0 < self.charge_efficiency <= 1.0:
            raise ValueError("charge_efficiency must be in (0, 1]")
        if not 0 < self.discharge_efficiency <= 1.0:
            raise ValueError("discharge_efficiency must be in (0, 1]")
        if not 0 <= self.standing_loss_per_h < 1.0:
            raise ValueError("standing_loss_per_h must be in [0, 1)")
        if self.max_charge_kw < 0 or self.max_discharge_kw < 0:
            raise ValueError("TES max charge/discharge rates must be non-negative")
        bounds = [
            self.soc_min_phys,
            self.soc_min_plan,
            self.initial_soc,
            self.terminal_soc_target,
            self.soc_max_plan,
            self.soc_max_phys,
        ]
        if any(v < 0 or v > 1 for v in bounds):
            raise ValueError("SOC bounds, initial SOC, and terminal target must be in [0, 1]")
        if not self.soc_min_phys <= self.soc_min_plan <= self.soc_max_plan <= self.soc_max_phys:
            raise ValueError("SOC physical and planning bounds are inconsistent")


class TESModel:
    """Linear SOC dynamics used by the MILP and synthetic closed loop."""

    def __init__(self, params: TESParams, dt_h: float = 0.25):
        if not math.isfinite(float(dt_h)):
            raise ValueError(f"TESModel dt_h must be finite, got {dt_h}")
        if abs(dt_h - 0.25) > 1e-9:
            raise ValueError(f"TESModel requires dt_h=0.25, got {dt_h}")
        params.validate()
        self.params = params
        self.dt_h = dt_h

    def next_soc(self, soc: float, q_ch_kw: float, q_dis_kw: float) -> float:
        """Return next SOC after one 15-minute step."""

        for name, value in {"soc": soc, "q_ch_kw": q_ch_kw, "q_dis_kw": q_dis_kw, "dt_h": self.dt_h}.items():
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite, got {value}")
        if not 0.0 <= soc <= 1.0:
            raise ValueError(f"soc must be in [0, 1], got {soc}")
        self.params.validate()
        if q_ch_kw < -1e-9 or q_dis_kw < -1e-9:
            raise ValueError("TES charge/discharge must be non-negative")
        if q_ch_kw > self.params.max_charge_kw + 1e-9:
            raise ValueError("TES charge exceeds max_charge_kw")
        if q_dis_kw > self.params.max_discharge_kw + 1e-9:
            raise ValueError("TES discharge exceeds max_discharge_kw")
        if q_ch_kw > 1e-6 and q_dis_kw > 1e-6:
            raise ValueError("TES cannot charge and discharge simultaneously")
        p = self.params
        next_soc = (
            (1.0 - p.standing_loss_per_h * self.dt_h) * soc
            + p.charge_efficiency * q_ch_kw * self.dt_h / p.effective_capacity_kwh
            - q_dis_kw * self.dt_h / (p.discharge_efficiency * p.effective_capacity_kwh)
        )
        return min(1.0, max(0.0, next_soc))
