"""Typed inputs, outputs, and config helpers for deterministic MPC v2."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


class SchemaValidationError(ValueError):
    """Raised when an input bundle violates the MPC schema."""


class SolverUnavailableError(RuntimeError):
    """Raised when the configured optimization backend is unavailable."""


@dataclass(frozen=True)
class MPCState:
    """Current physical state passed into a receding-horizon solve."""

    soc: float
    room_temp_c: float
    prev_q_ch_tes_kw_th: float = 0.0
    prev_q_dis_tes_kw_th: float = 0.0
    prev_u_ch: float = 0.0
    prev_u_dis: float = 0.0
    prev_mode_index: int = -1

    def validate(self) -> None:
        _require_finite("soc", self.soc)
        _require_finite("room_temp_c", self.room_temp_c)
        _require_finite("prev_q_ch_tes_kw_th", self.prev_q_ch_tes_kw_th)
        _require_finite("prev_q_dis_tes_kw_th", self.prev_q_dis_tes_kw_th)
        _require_finite("prev_u_ch", self.prev_u_ch)
        _require_finite("prev_u_dis", self.prev_u_dis)
        if not 0.0 <= self.soc <= 1.0:
            raise SchemaValidationError(f"soc must be in [0, 1], got {self.soc}")
        if self.prev_q_ch_tes_kw_th < -1e-9 or self.prev_q_dis_tes_kw_th < -1e-9:
            raise SchemaValidationError("previous TES actions must be non-negative")
        if not 0.0 <= self.prev_u_ch <= 1.0 or not 0.0 <= self.prev_u_dis <= 1.0:
            raise SchemaValidationError("previous valve positions must be in [0, 1]")
        if self.prev_mode_index < -1:
            raise SchemaValidationError("prev_mode_index must be -1 or a non-negative mode index")


@dataclass(frozen=True)
class MPCAction:
    """First-step physical controls returned by the receding-horizon solve."""

    q_ch_tes_kw_th: float
    q_dis_tes_kw_th: float
    q_chiller_kw_th: float = 0.0
    q_load_kw_th: float = 0.0
    plant_power_kw: float = 0.0
    u_ch: float = 0.0
    u_dis: float = 0.0
    mode_index: int = -1

    def validate(self) -> None:
        _require_finite("q_ch_tes_kw_th", self.q_ch_tes_kw_th)
        _require_finite("q_dis_tes_kw_th", self.q_dis_tes_kw_th)
        _require_finite("q_chiller_kw_th", self.q_chiller_kw_th)
        _require_finite("q_load_kw_th", self.q_load_kw_th)
        _require_finite("plant_power_kw", self.plant_power_kw)
        _require_finite("u_ch", self.u_ch)
        _require_finite("u_dis", self.u_dis)
        if min(self.q_ch_tes_kw_th, self.q_dis_tes_kw_th, self.q_chiller_kw_th, self.q_load_kw_th) < -1e-9:
            raise SchemaValidationError("cooling actions must be non-negative")
        if self.q_ch_tes_kw_th > 1e-6 and self.q_dis_tes_kw_th > 1e-6:
            raise SchemaValidationError("TES cannot charge and discharge simultaneously")
        if not 0.0 <= self.u_ch <= 1.0 or not 0.0 <= self.u_dis <= 1.0:
            raise SchemaValidationError("valve positions must be in [0, 1]")
        if self.u_ch + self.u_dis > 1.0 + 1e-7:
            raise SchemaValidationError("TES charge and discharge valves cannot both be open")
        if self.mode_index < -1:
            raise SchemaValidationError("mode_index must be -1 or a non-negative mode index")


@dataclass(frozen=True)
class ForecastBundle:
    """Forecast arrays aligned to the MPC horizon."""

    timestamps: list[datetime]
    outdoor_temp_forecast_c: list[float]
    it_load_forecast_kw: list[float]
    pv_forecast_kw: list[float]
    price_forecast: list[float]
    base_facility_kw: list[float]
    base_cooling_kw_th: list[float]
    wet_bulb_forecast_c: list[float] | None = None

    def validate(self, horizon_steps: int, dt_hours: float) -> None:
        if horizon_steps <= 0:
            raise SchemaValidationError("horizon_steps must be positive")
        if dt_hours <= 0:
            raise SchemaValidationError("dt_hours must be positive")
        lengths = {
            "timestamps": len(self.timestamps),
            "outdoor_temp_forecast_c": len(self.outdoor_temp_forecast_c),
            "it_load_forecast_kw": len(self.it_load_forecast_kw),
            "pv_forecast_kw": len(self.pv_forecast_kw),
            "price_forecast": len(self.price_forecast),
            "base_facility_kw": len(self.base_facility_kw),
            "base_cooling_kw_th": len(self.base_cooling_kw_th),
        }
        if self.wet_bulb_forecast_c is not None:
            lengths["wet_bulb_forecast_c"] = len(self.wet_bulb_forecast_c)
        bad = {name: n for name, n in lengths.items() if n != horizon_steps}
        if bad:
            raise SchemaValidationError(f"forecast length mismatch: {bad}; expected {horizon_steps}")
        for field_name in lengths:
            if field_name == "timestamps":
                continue
            values = getattr(self, field_name)
            for i, value in enumerate(values):
                _require_finite(f"{field_name}[{i}]", float(value))
                if field_name not in {"outdoor_temp_forecast_c", "wet_bulb_forecast_c"} and float(value) < -1e-9:
                    raise SchemaValidationError(f"{field_name}[{i}] must be non-negative")

    def wet_bulb_or_default(self, default_depression_c: float = 4.0) -> list[float]:
        """Return wet-bulb values, using a dry-bulb-minus-depression proxy if absent."""

        if self.wet_bulb_forecast_c is not None:
            return self.wet_bulb_forecast_c
        return [float(v) - float(default_depression_c) for v in self.outdoor_temp_forecast_c]


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML mapping with a stable validation error."""

    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise SchemaValidationError(f"YAML file must contain a mapping: {path}")
    return data


def parse_timestamp(value: Any) -> datetime:
    """Parse timestamps from YAML, CSV, pandas, or tests."""

    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime().replace(tzinfo=None)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "").replace("T", " "))
    raise SchemaValidationError(f"unsupported timestamp value: {value!r}")


def dataclass_dict(value: Any) -> dict[str, Any]:
    """Return an ordinary dict for dataclass instances."""

    return asdict(value)


def _require_finite(name: str, value: float) -> None:
    if value != value or value in (float("inf"), float("-inf")):
        raise SchemaValidationError(f"{name} must be finite, got {value}")
