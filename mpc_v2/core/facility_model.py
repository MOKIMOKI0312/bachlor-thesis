"""Facility, cooling, grid, and PV power-balance proxy models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FacilityParams:
    """Linear facility-power proxy parameters."""

    base_pue: float
    outdoor_temp_coeff_per_c: float
    reference_outdoor_c: float
    cop_charge: float
    cop_discharge_equiv: float

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "FacilityParams":
        return cls(**{field: float(config[field]) for field in cls.__dataclass_fields__})

    def validate(self) -> None:
        if self.base_pue <= 1.0:
            raise ValueError("base_pue should be greater than 1")
        if self.cop_charge <= 0 or self.cop_discharge_equiv <= 0:
            raise ValueError("COP values must be positive")


class FacilityModel:
    """Power-balance helper shared by forecasts, MILP, and metrics."""

    def __init__(self, params: FacilityParams):
        params.validate()
        self.params = params

    def pue_hat(self, outdoor_temp_c: float) -> float:
        return max(
            1.01,
            self.params.base_pue
            + self.params.outdoor_temp_coeff_per_c * (outdoor_temp_c - self.params.reference_outdoor_c),
        )

    def base_facility_kw(self, it_load_kw: float, outdoor_temp_c: float) -> float:
        if it_load_kw < 0:
            raise ValueError("it_load_kw must be non-negative")
        return it_load_kw * self.pue_hat(outdoor_temp_c)

    def facility_kw(
        self,
        base_facility_kw: float,
        q_ch_tes_kw_th: float,
        q_dis_tes_kw_th: float,
    ) -> float:
        return max(
            0.0,
            base_facility_kw
            + q_ch_tes_kw_th / self.params.cop_charge
            - q_dis_tes_kw_th / self.params.cop_discharge_equiv,
        )

    def grid_and_spill_kw(
        self,
        base_facility_kw: float,
        q_ch_tes_kw_th: float,
        q_dis_tes_kw_th: float,
        pv_kw: float,
    ) -> tuple[float, float, float]:
        """Return grid import, PV spill, and facility power."""

        facility_kw = self.facility_kw(base_facility_kw, q_ch_tes_kw_th, q_dis_tes_kw_th)
        net_load_kw = facility_kw - pv_kw
        return max(0.0, net_load_kw), max(0.0, -net_load_kw), facility_kw
