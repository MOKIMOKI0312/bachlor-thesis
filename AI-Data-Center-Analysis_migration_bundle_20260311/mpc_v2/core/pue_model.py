"""Facility-power and PUE proxy model used for economic cost estimation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PUEParams:
    """Linear PUE/facility proxy parameters."""

    base_pue: float
    outdoor_temp_coeff_per_C: float
    reference_outdoor_C: float
    charge_cop: float
    discharge_power_credit_cop: float

    @classmethod
    def from_config(cls, config: dict) -> "PUEParams":
        return cls(**{field: float(config[field]) for field in cls.__dataclass_fields__})

    def validate(self) -> None:
        if self.base_pue <= 1.0:
            raise ValueError("base_pue should be greater than 1")
        if self.charge_cop <= 0 or self.discharge_power_credit_cop <= 0:
            raise ValueError("COP values must be positive")


class PUEModel:
    """Estimate facility power and PUE from IT load, weather, and TES action."""

    def __init__(self, params: PUEParams):
        params.validate()
        self.params = params

    def pue_hat(self, outdoor_C: float) -> float:
        return max(1.01, self.params.base_pue + self.params.outdoor_temp_coeff_per_C * (outdoor_C - self.params.reference_outdoor_C))

    def base_facility_kw(self, ite_kw: float, outdoor_C: float) -> float:
        if ite_kw < 0:
            raise ValueError("ite_kw must be non-negative")
        return ite_kw * self.pue_hat(outdoor_C)

    def facility_kw(self, ite_kw: float, outdoor_C: float, q_ch_kw: float, q_dis_kw: float) -> float:
        base = self.base_facility_kw(ite_kw, outdoor_C)
        return max(0.0, base + q_ch_kw / self.params.charge_cop - q_dis_kw / self.params.discharge_power_credit_cop)

