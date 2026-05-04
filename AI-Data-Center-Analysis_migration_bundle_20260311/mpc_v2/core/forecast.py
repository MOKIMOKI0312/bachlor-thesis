"""Forecast loading, resampling, and synthetic horizon generation."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from mpc_v2.core.io_schemas import ForecastBundle, SchemaValidationError, parse_timestamp
from mpc_v2.core.pue_model import PUEModel

Perturbation = Literal["nominal", "g05", "g10", "g20"]


def load_hourly_csv(path: str | Path, value_column: str) -> pd.Series:
    """Load a timestamp/value CSV into an hourly pandas Series."""

    frame = pd.read_csv(path)
    if "timestamp" not in frame.columns or value_column not in frame.columns:
        raise SchemaValidationError(f"{path} must contain timestamp and {value_column}")
    ts = pd.to_datetime(frame["timestamp"])
    values = pd.to_numeric(frame[value_column], errors="raise").astype(float)
    series = pd.Series(values.to_numpy(), index=ts).sort_index()
    if series.empty:
        raise SchemaValidationError(f"{path} is empty")
    if series.index.has_duplicates:
        series = series.groupby(level=0).mean()
    return series


def resample_hourly_to_15min(series: pd.Series, mode: Literal["step", "average_power"] = "step") -> pd.Series:
    """Expand hourly series to fixed 15-minute steps.

    Prices use ``step`` semantics. PV is average hourly power, so each hourly
    value is repeated to the four quarter-hour intervals in that hour.
    """

    if series.empty:
        raise SchemaValidationError("cannot resample an empty series")
    series = series.sort_index()
    full_idx = pd.date_range(series.index.min(), series.index.max() + pd.Timedelta(minutes=45), freq="15min")
    if mode not in {"step", "average_power"}:
        raise ValueError(f"unsupported resampling mode: {mode}")
    return series.reindex(full_idx, method="ffill").astype(float)


def apply_pv_perturbation(pv_kw: np.ndarray, mode: Perturbation = "nominal", seed: int | None = None) -> np.ndarray:
    """Apply multiplicative PV forecast perturbation with deterministic seeds."""

    sigmas = {"nominal": 0.0, "g05": 0.05, "g10": 0.10, "g20": 0.20}
    if mode not in sigmas:
        raise ValueError(f"unsupported PV perturbation mode: {mode}")
    pv_kw = np.asarray(pv_kw, dtype=float)
    if np.any(~np.isfinite(pv_kw)) or np.any(pv_kw < -1e-9):
        raise SchemaValidationError("pv_kw must be finite and non-negative")
    sigma = sigmas[mode]
    if sigma == 0:
        return np.maximum(0.0, pv_kw.copy())
    rng = np.random.default_rng(seed)
    factors = np.clip(rng.normal(loc=1.0, scale=sigma, size=pv_kw.shape), 0.0, None)
    return np.maximum(0.0, pv_kw * factors)


class ForecastBuilder:
    """Build 192-step forecasts from hourly price/PV files and synthetic exogenous inputs."""

    def __init__(
        self,
        pv_csv: str | Path,
        price_csv: str | Path,
        pue_model: PUEModel,
        dt_h: float = 0.25,
    ):
        if abs(dt_h - 0.25) > 1e-9:
            raise ValueError(f"ForecastBuilder requires dt_h=0.25, got {dt_h}")
        self.dt_h = dt_h
        self.pue_model = pue_model
        self.pv_15min = resample_hourly_to_15min(load_hourly_csv(pv_csv, "power_kw"), mode="average_power")
        self.price_15min = resample_hourly_to_15min(load_hourly_csv(price_csv, "price_usd_per_mwh"), mode="step")

    def build(
        self,
        now_ts: datetime | str,
        horizon_steps: int = 192,
        pv_perturbation: Perturbation = "nominal",
        seed: int | None = None,
        ite_power_kw: float = 18000.0,
        outdoor_base_C: float = 29.0,
        outdoor_amplitude_C: float = 6.0,
        outdoor_offset_C: float = 0.0,
        base_cooling_kw: float = 2100.0,
        tariff_multiplier: float = 1.0,
    ) -> ForecastBundle:
        """Return a fixed-length forecast beginning at ``now_ts``."""

        if horizon_steps <= 0:
            raise ValueError("horizon_steps must be positive")
        now = parse_timestamp(now_ts)
        timestamps = [now + timedelta(minutes=15 * i) for i in range(horizon_steps)]
        pv = _take_cyclic(self.pv_15min, timestamps)
        price = _take_cyclic(self.price_15min, timestamps) * float(tariff_multiplier)
        pv = apply_pv_perturbation(pv, pv_perturbation, seed)
        hours = np.array([ts.hour + ts.minute / 60.0 for ts in timestamps], dtype=float)
        outdoor = outdoor_base_C + outdoor_offset_C + outdoor_amplitude_C * np.sin(2.0 * np.pi * (hours - 15.0) / 24.0)
        ite = np.full(horizon_steps, float(ite_power_kw))
        base_facility = np.array([self.pue_model.base_facility_kw(float(v), float(t)) for v, t in zip(ite, outdoor)])
        base_cooling = np.full(horizon_steps, float(base_cooling_kw))
        bundle = ForecastBundle(
            timestamps=timestamps,
            price_usd_per_mwh=price.tolist(),
            pv_kw=pv.tolist(),
            outdoor_drybulb_C=outdoor.tolist(),
            ite_power_kw=ite.tolist(),
            base_facility_kw=base_facility.tolist(),
            base_cooling_kw=base_cooling.tolist(),
        )
        bundle.validate(horizon_steps=horizon_steps, dt_h=self.dt_h)
        return bundle


def _take_cyclic(series: pd.Series, timestamps: list[datetime]) -> np.ndarray:
    """Map requested timestamps into a repeated annual index."""

    index = series.index
    by_key = {(ts.month, ts.day, ts.hour, ts.minute): float(value) for ts, value in series.items()}
    values: list[float] = []
    fallback = float(series.iloc[0])
    for ts in timestamps:
        values.append(by_key.get((ts.month, ts.day, ts.hour, ts.minute), fallback))
    return np.asarray(values, dtype=float)

