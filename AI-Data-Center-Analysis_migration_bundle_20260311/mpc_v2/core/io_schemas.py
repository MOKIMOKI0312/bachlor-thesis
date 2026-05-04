"""Typed I/O schemas and validation helpers for MPC v2."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


class SchemaValidationError(ValueError):
    """Raised when an observation, action, or config violates the v2 schema."""


class SolverUnavailableError(RuntimeError):
    """Raised when the requested MILP solver backend is not available."""


@dataclass(frozen=True)
class Observation:
    """Single 15-minute observation passed from replay or EnergyPlus to MPC."""

    timestamp: datetime
    dt_h: float
    air_temperature_C: float
    outdoor_drybulb_C: float
    ite_power_kw: float
    facility_power_kw: float
    tes_soc: float
    tes_tank_temp_C: float
    current_pv_kw: float
    current_price_usd_per_mwh: float
    chiller_cop: float
    pue_actual: float

    def validate(self) -> None:
        if abs(self.dt_h - 0.25) > 1e-9:
            raise SchemaValidationError(f"dt_h must be fixed at 0.25, got {self.dt_h}")
        if not 0.0 <= self.tes_soc <= 1.0:
            raise SchemaValidationError(f"tes_soc must be in [0, 1], got {self.tes_soc}")
        for name, value in asdict(self).items():
            if name == "timestamp":
                continue
            _require_finite(name, float(value))
        if self.ite_power_kw < 0 or self.facility_power_kw < 0 or self.current_pv_kw < 0:
            raise SchemaValidationError("power fields must be non-negative")
        if self.chiller_cop <= 0 or self.pue_actual <= 0:
            raise SchemaValidationError("chiller_cop and pue_actual must be positive")


@dataclass(frozen=True)
class Action:
    """First control action returned by the MPC."""

    tes_signed_target: float
    tes_charge_kwth: float
    tes_discharge_kwth: float
    crah_supply_temp_sp_C: float | None = None
    chiller_lwt_sp_C: float | None = None
    ct_pump_speed_frac: float | None = None

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if value is not None:
                _require_finite(name, float(value))
        if self.tes_charge_kwth < -1e-9 or self.tes_discharge_kwth < -1e-9:
            raise SchemaValidationError("TES charge/discharge power must be non-negative")
        if self.tes_charge_kwth > 1e-6 and self.tes_discharge_kwth > 1e-6:
            raise SchemaValidationError("TES cannot charge and discharge in the same action")


@dataclass(frozen=True)
class ForecastBundle:
    """Forecast arrays aligned to fixed 15-minute MPC steps."""

    timestamps: list[datetime]
    price_usd_per_mwh: list[float]
    pv_kw: list[float]
    outdoor_drybulb_C: list[float]
    ite_power_kw: list[float]
    base_facility_kw: list[float]
    base_cooling_kw: list[float]

    def validate(self, horizon_steps: int, dt_h: float = 0.25) -> None:
        if horizon_steps <= 0:
            raise SchemaValidationError("horizon_steps must be positive")
        lengths = {
            "timestamps": len(self.timestamps),
            "price_usd_per_mwh": len(self.price_usd_per_mwh),
            "pv_kw": len(self.pv_kw),
            "outdoor_drybulb_C": len(self.outdoor_drybulb_C),
            "ite_power_kw": len(self.ite_power_kw),
            "base_facility_kw": len(self.base_facility_kw),
            "base_cooling_kw": len(self.base_cooling_kw),
        }
        bad = {name: n for name, n in lengths.items() if n != horizon_steps}
        if bad:
            raise SchemaValidationError(f"forecast length mismatch: {bad}, expected {horizon_steps}")
        if abs(dt_h - 0.25) > 1e-9:
            raise SchemaValidationError(f"dt_h must be 0.25, got {dt_h}")
        for field_name in lengths:
            if field_name == "timestamps":
                continue
            for i, value in enumerate(getattr(self, field_name)):
                _require_finite(f"{field_name}[{i}]", float(value))
                if field_name in {"price_usd_per_mwh", "pv_kw", "ite_power_kw", "base_facility_kw", "base_cooling_kw"}:
                    if float(value) < -1e-9:
                        raise SchemaValidationError(f"{field_name}[{i}] must be non-negative")


def parse_timestamp(value: Any) -> datetime:
    """Parse a timestamp supplied by CSV, YAML, EnergyPlus info, or tests."""

    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime().replace(tzinfo=None)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "").replace("T", " "))
    raise SchemaValidationError(f"unsupported timestamp value: {value!r}")


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML mapping with a clear error when the file is malformed."""

    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise SchemaValidationError(f"YAML file must contain a mapping: {path}")
    return data


def _require_finite(name: str, value: float) -> None:
    if value != value or value in (float("inf"), float("-inf")):
        raise SchemaValidationError(f"{name} must be finite, got {value}")

