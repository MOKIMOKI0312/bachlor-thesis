"""Public schemas and config helpers for the rebuilt MPC v1 system."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


class SchemaValidationError(ValueError):
    """Raised when an input or output contract is violated."""


class SolverUnavailableError(RuntimeError):
    """Raised when the optimization backend cannot return a valid solution."""


class UnsupportedFeatureError(NotImplementedError):
    """Raised for old advanced options intentionally deferred after rebuild."""


@dataclass(frozen=True)
class MPCState:
    """Current state passed to a controller."""

    soc: float
    room_temp_c: float
    prev_q_ch_tes_kw_th: float = 0.0
    prev_q_dis_tes_kw_th: float = 0.0

    def validate(self) -> None:
        _require_finite("soc", self.soc)
        _require_finite("room_temp_c", self.room_temp_c)
        if not 0.0 <= self.soc <= 1.0:
            raise SchemaValidationError(f"soc must be in [0, 1], got {self.soc}")
        if self.prev_q_ch_tes_kw_th < -1e-9 or self.prev_q_dis_tes_kw_th < -1e-9:
            raise SchemaValidationError("previous TES actions must be non-negative")


@dataclass(frozen=True)
class MPCAction:
    """First-step physical controls emitted by a controller."""

    q_ch_tes_kw_th: float
    q_dis_tes_kw_th: float
    q_chiller_kw_th: float
    q_load_kw_th: float
    plant_power_kw: float
    u_ch: float
    u_dis: float
    mode_index: int = 0
    q_ch_max_kw_th: float = 4500.0
    q_dis_max_kw_th: float = 4500.0

    @property
    def u_signed(self) -> float:
        return self.u_ch - self.u_dis

    def validate(self) -> None:
        for name in [
            "q_ch_tes_kw_th",
            "q_dis_tes_kw_th",
            "q_chiller_kw_th",
            "q_load_kw_th",
            "plant_power_kw",
            "u_ch",
            "u_dis",
        ]:
            _require_finite(name, getattr(self, name))
        if min(self.q_ch_tes_kw_th, self.q_dis_tes_kw_th, self.q_chiller_kw_th, self.q_load_kw_th) < -1e-9:
            raise SchemaValidationError("cooling and plant actions must be non-negative")
        if self.q_ch_tes_kw_th > 1e-6 and self.q_dis_tes_kw_th > 1e-6:
            raise SchemaValidationError("TES cannot charge and discharge simultaneously")
        if self.q_ch_tes_kw_th > self.q_ch_max_kw_th + 1e-6:
            raise SchemaValidationError("TES charge exceeds q_ch_max_kw_th")
        if self.q_dis_tes_kw_th > self.q_dis_max_kw_th + 1e-6:
            raise SchemaValidationError("TES discharge exceeds q_dis_max_kw_th")
        if abs(self.u_ch - self.q_ch_tes_kw_th / self.q_ch_max_kw_th) > 1e-6:
            raise SchemaValidationError("u_ch must equal normalized charge flow")
        if abs(self.u_dis - self.q_dis_tes_kw_th / self.q_dis_max_kw_th) > 1e-6:
            raise SchemaValidationError("u_dis must equal normalized discharge flow")
        if self.u_ch + self.u_dis > 1.0 + 1e-6:
            raise SchemaValidationError("TES valves cannot both be open")
        if self.q_load_kw_th + self.q_ch_tes_kw_th > self.q_chiller_kw_th + 1e-6:
            raise SchemaValidationError("chiller output must cover direct load cooling plus TES charging")


@dataclass(frozen=True)
class ForecastBundle:
    """Aligned replay or synthetic disturbance arrays."""

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
        bad = {name: size for name, size in lengths.items() if size != horizon_steps}
        if bad:
            raise SchemaValidationError(f"forecast length mismatch: {bad}; expected {horizon_steps}")
        for name, size in lengths.items():
            if name == "timestamps":
                continue
            values = getattr(self, name)
            for i in range(size):
                value = float(values[i])
                _require_finite(f"{name}[{i}]", value)
                if name not in {"outdoor_temp_forecast_c", "wet_bulb_forecast_c"} and value < -1e-9:
                    raise SchemaValidationError(f"{name}[{i}] must be non-negative")


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML mapping."""

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
