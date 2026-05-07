"""Replay/synthetic forecast builder for the rebuilt MPC v1 path."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from mpc_v2.core.io_schemas import ForecastBundle, SchemaValidationError, parse_timestamp
from mpc_v2.core.plant import PlantParams


def load_hourly_csv(path: str | Path) -> pd.Series:
    """Load an hourly timestamp/value CSV and normalize known price units."""

    frame = pd.read_csv(path)
    if "timestamp" not in frame.columns:
        raise SchemaValidationError(f"{path} must contain timestamp")
    value_columns = [c for c in frame.columns if c != "timestamp"]
    if not value_columns:
        raise SchemaValidationError(f"{path} must contain a value column")
    value_column = value_columns[0]
    ts = pd.to_datetime(frame["timestamp"])
    values = pd.to_numeric(frame[value_column], errors="raise").astype(float)
    if "mwh" in value_column.lower():
        values = values / 1000.0
    series = pd.Series(values.to_numpy(), index=ts).sort_index()
    if series.empty:
        raise SchemaValidationError(f"{path} is empty")
    if series.index.has_duplicates:
        series = series.groupby(level=0).mean()
    return series


def resample_to_step(series: pd.Series, dt_hours: float) -> pd.Series:
    """Forward-fill hourly data to the controller timestep."""

    if abs(float(dt_hours) - 0.25) > 1e-9:
        raise SchemaValidationError("rebuilt MPC v1 currently supports 15-minute steps only")
    idx = pd.date_range(series.index.min(), series.index.max() + pd.Timedelta(minutes=45), freq="15min")
    return series.reindex(idx, method="ffill").astype(float)


def apply_pv_forecast_error(pv_actual_kw: np.ndarray, sigma: float, seed: int | None) -> np.ndarray:
    """Apply a deterministic multiplicative Gaussian PV forecast error."""

    pv_actual_kw = np.asarray(pv_actual_kw, dtype=float)
    if sigma < 0:
        raise ValueError("sigma must be non-negative")
    if sigma == 0:
        return np.maximum(0.0, pv_actual_kw)
    rng = np.random.default_rng(seed)
    return np.maximum(0.0, pv_actual_kw * (1.0 + rng.normal(0.0, sigma, pv_actual_kw.shape)))


class ForecastBuilder:
    """Build aligned forecast bundles from current Nanjing PV and TOU CSV inputs."""

    def __init__(self, pv_csv: str | Path, price_csv: str | Path, plant: PlantParams, dt_hours: float):
        self.dt_hours = float(dt_hours)
        self.plant = plant
        self.pv = resample_to_step(load_hourly_csv(pv_csv), self.dt_hours)
        self.price = resample_to_step(load_hourly_csv(price_csv), self.dt_hours)

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "ForecastBuilder":
        return cls(
            cfg["paths"]["pv_csv"],
            cfg["paths"]["price_csv"],
            PlantParams.from_config(cfg),
            float(cfg["time"]["dt_hours"]),
        )

    def build(
        self,
        now_ts: datetime | str,
        horizon_steps: int,
        pv_error_sigma: float,
        seed: int | None,
        it_load_kw: float,
        outdoor_base_c: float,
        outdoor_amplitude_c: float,
        outdoor_offset_c: float = 0.0,
        tariff_multiplier: float = 1.0,
        pv_scale: float = 1.0,
        wet_bulb_depression_c: float = 4.0,
    ) -> ForecastBundle:
        if horizon_steps <= 0:
            raise ValueError("horizon_steps must be positive")
        now = parse_timestamp(now_ts)
        timestamps = [now + timedelta(minutes=15 * i) for i in range(horizon_steps)]
        pv_actual = _take_cyclic(self.pv, timestamps) * float(pv_scale)
        pv_forecast = apply_pv_forecast_error(pv_actual, pv_error_sigma, seed)
        price = _take_cyclic(self.price, timestamps) * float(tariff_multiplier)
        hours = np.asarray([ts.hour + ts.minute / 60.0 for ts in timestamps], dtype=float)
        outdoor = (
            float(outdoor_base_c)
            + float(outdoor_offset_c)
            + float(outdoor_amplitude_c) * np.sin(2.0 * np.pi * (hours - 15.0) / 24.0)
        )
        it_load = np.full(horizon_steps, float(it_load_kw))
        cooling = it_load * self.plant.cooling_load_ratio
        bundle = ForecastBundle(
            timestamps=timestamps,
            outdoor_temp_forecast_c=outdoor.tolist(),
            it_load_forecast_kw=it_load.tolist(),
            pv_forecast_kw=pv_forecast.tolist(),
            price_forecast=price.tolist(),
            base_facility_kw=it_load.tolist(),
            base_cooling_kw_th=cooling.tolist(),
            wet_bulb_forecast_c=(outdoor - float(wet_bulb_depression_c)).tolist(),
        )
        bundle.validate(horizon_steps, self.dt_hours)
        return bundle


def _take_cyclic(series: pd.Series, timestamps: list[datetime]) -> np.ndarray:
    by_key = {(ts.month, ts.day, ts.hour, ts.minute): float(value) for ts, value in series.items()}
    fallback = float(series.iloc[0])
    return np.asarray([by_key.get((ts.month, ts.day, ts.hour, ts.minute), fallback) for ts in timestamps], dtype=float)
