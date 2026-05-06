"""Facility, chiller plant, grid, and PV power-balance proxy models."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


@dataclass(frozen=True)
class FacilityParams:
    """Linear facility-power proxy parameters."""

    base_pue: float
    outdoor_temp_coeff_per_c: float
    reference_outdoor_c: float
    cop_charge: float = 5.2
    cop_discharge_equiv: float = 5.0

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "FacilityParams":
        return cls(
            base_pue=float(config["base_pue"]),
            outdoor_temp_coeff_per_c=float(config["outdoor_temp_coeff_per_c"]),
            reference_outdoor_c=float(config["reference_outdoor_c"]),
            cop_charge=float(config.get("cop_charge", 5.2)),
            cop_discharge_equiv=float(config.get("cop_discharge_equiv", 5.0)),
        )

    def validate(self) -> None:
        if self.base_pue <= 1.0:
            raise ValueError("base_pue should be greater than 1")
        if self.cop_charge <= 0 or self.cop_discharge_equiv <= 0:
            raise ValueError("COP values must be positive")


@dataclass(frozen=True)
class ChillerMode:
    """One affine chiller plant operating mode."""

    q_min_kw_th: float
    q_max_kw_th: float
    a_kw_per_kwth: float
    c0_kw: float
    c1_kw_per_c: float
    min_on_steps: int
    min_off_steps: int

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ChillerMode":
        return cls(
            q_min_kw_th=float(config["q_min_kw_th"]),
            q_max_kw_th=float(config["q_max_kw_th"]),
            a_kw_per_kwth=float(config["a_kw_per_kwth"]),
            c0_kw=float(config["c0_kw"]),
            c1_kw_per_c=float(config.get("c1_kw_per_c", 0.0)),
            min_on_steps=int(config.get("min_on_steps", 1)),
            min_off_steps=int(config.get("min_off_steps", 1)),
        )

    def validate(self) -> None:
        values = [
            self.q_min_kw_th,
            self.q_max_kw_th,
            self.a_kw_per_kwth,
            self.c0_kw,
            self.c1_kw_per_c,
        ]
        if any(not math.isfinite(v) for v in values):
            raise ValueError("chiller mode values must be finite")
        if self.q_min_kw_th < 0 or self.q_max_kw_th <= 0 or self.q_min_kw_th > self.q_max_kw_th:
            raise ValueError("chiller mode q_min/q_max are inconsistent")
        if self.a_kw_per_kwth < 0:
            raise ValueError("chiller mode slope must be non-negative")
        if self.min_on_steps < 1 or self.min_off_steps < 1:
            raise ValueError("minimum on/off steps must be positive")


@dataclass(frozen=True)
class ChillerPlantParams:
    """Mode-based affine chiller plant configuration."""

    modes: tuple[ChillerMode, ...]
    plr_pref: float = 0.75

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ChillerPlantParams":
        raw_modes = config.get("modes", [])
        if not isinstance(raw_modes, list) or not raw_modes:
            raise ValueError("chiller.modes must contain at least one mode")
        params = cls(
            modes=tuple(ChillerMode.from_config(item) for item in raw_modes),
            plr_pref=float(config.get("plr_pref", 0.75)),
        )
        params.validate()
        return params

    def validate(self) -> None:
        if not self.modes:
            raise ValueError("at least one chiller mode is required")
        if not 0 <= self.plr_pref <= 1:
            raise ValueError("plr_pref must be in [0, 1]")
        for mode in self.modes:
            mode.validate()

    @property
    def q_max_kw_th(self) -> float:
        return max(mode.q_max_kw_th for mode in self.modes)


@dataclass(frozen=True)
class ValveParams:
    """Linear valve proxy parameters."""

    u_min: float = 0.0
    u_max: float = 1.0
    du_max_per_step: float = 0.10
    du_signed_max_per_step: float = 0.10

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "ValveParams":
        du_max = float(config.get("du_max_per_step", 0.10))
        params = cls(
            u_min=float(config.get("u_min", 0.0)),
            u_max=float(config.get("u_max", 1.0)),
            du_max_per_step=du_max,
            du_signed_max_per_step=float(config.get("du_signed_max_per_step", du_max)),
        )
        params.validate()
        return params

    def validate(self) -> None:
        if not 0 <= self.u_min <= self.u_max <= 1:
            raise ValueError("valve u_min/u_max must be within [0, 1]")
        if not 0 < self.du_max_per_step <= 1:
            raise ValueError("valve du_max_per_step must be in (0, 1]")
        if not 0 < self.du_signed_max_per_step <= 2:
            raise ValueError("valve du_signed_max_per_step must be in (0, 2]")


@dataclass(frozen=True)
class EconomicsParams:
    """Economic terms outside the time-varying energy price."""

    demand_charge_rate: float = 0.0
    demand_charge_basis: str = "per_day_proxy"
    pv_scale: float = 1.0
    peak_cap_kw: float | None = None

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> "EconomicsParams":
        config = config or {}
        legacy_rate = config.get("demand_charge_currency_per_kw_day", 0.0)
        peak_cap = config.get("peak_cap_kw", None)
        params = cls(
            demand_charge_rate=float(config.get("demand_charge_rate", legacy_rate)),
            demand_charge_basis=str(config.get("demand_charge_basis", "per_day_proxy")),
            pv_scale=float(config.get("pv_scale", 1.0)),
            peak_cap_kw=None if peak_cap in (None, "") else float(peak_cap),
        )
        params.validate()
        return params

    def validate(self) -> None:
        if self.demand_charge_rate < 0:
            raise ValueError("demand charge must be non-negative")
        if self.demand_charge_basis not in {"per_day_proxy", "per_episode"}:
            raise ValueError("demand_charge_basis must be per_day_proxy or per_episode")
        if self.pv_scale < 0:
            raise ValueError("pv_scale must be non-negative")
        if self.peak_cap_kw is not None and self.peak_cap_kw < 0:
            raise ValueError("peak_cap_kw must be non-negative when provided")

    def demand_charge_multiplier(self, duration_hours: float) -> float:
        """Return the multiplier applied to peak kW for this demand charge basis."""

        if self.demand_charge_basis == "per_episode":
            return 1.0
        return max(0.0, float(duration_hours)) / 24.0


class FacilityModel:
    """PUE helper retained for total-facility reporting."""

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


class ChillerPlantModel:
    """Mode-based affine plant power helper."""

    def __init__(self, params: ChillerPlantParams):
        params.validate()
        self.params = params

    def power_for_mode_kw(self, mode_index: int, q_chiller_kw_th: float, wet_bulb_c: float) -> float:
        if mode_index < 0:
            return 0.0
        mode = self.params.modes[mode_index]
        q = min(mode.q_max_kw_th, max(mode.q_min_kw_th, float(q_chiller_kw_th)))
        return max(0.0, mode.a_kw_per_kwth * q + mode.c0_kw + mode.c1_kw_per_c * float(wet_bulb_c))

    def dispatch(self, q_chiller_kw_th: float, wet_bulb_c: float) -> tuple[float, int, float]:
        """Return effective load, selected mode, and plant power for rule/fallback controllers."""

        q = max(0.0, float(q_chiller_kw_th))
        if q <= 1e-9:
            return 0.0, -1, 0.0
        candidates = []
        for i, mode in enumerate(self.params.modes):
            if q <= mode.q_max_kw_th + 1e-9:
                effective_q = max(q, mode.q_min_kw_th)
                power = self.power_for_mode_kw(i, effective_q, wet_bulb_c)
                candidates.append((power, i, effective_q))
        if not candidates:
            i = max(range(len(self.params.modes)), key=lambda m: self.params.modes[m].q_max_kw_th)
            mode = self.params.modes[i]
            effective_q = mode.q_max_kw_th
            return effective_q, i, self.power_for_mode_kw(i, effective_q, wet_bulb_c)
        power, mode_index, effective_q = min(candidates, key=lambda item: item[0])
        return effective_q, mode_index, power


def grid_and_spill_from_load_kw(load_kw: float, pv_kw: float) -> tuple[float, float]:
    """Split any non-negative electric load into grid import and PV spill."""

    net_load_kw = max(0.0, float(load_kw)) - max(0.0, float(pv_kw))
    return max(0.0, net_load_kw), max(0.0, -net_load_kw)


def grid_and_spill_from_plant_kw(plant_power_kw: float, pv_kw: float) -> tuple[float, float]:
    """Split cold-station proxy net load into grid import and PV spill."""

    return grid_and_spill_from_load_kw(plant_power_kw, pv_kw)
