"""Forecast loading, resampling, and deterministic perturbations."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from mpc_v2.core.facility_model import FacilityModel
from mpc_v2.core.io_schemas import ForecastBundle, SchemaValidationError, parse_timestamp
from mpc_v2.core.room_model import RoomModel


def load_hourly_csv(path: str | Path, value_column: str) -> pd.Series:
    """Load an hourly timestamp/value CSV."""

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


def resample_hourly_to_15min(series: pd.Series) -> pd.Series:
    """Repeat hourly values over quarter-hour steps."""

    if series.empty:
        raise SchemaValidationError("cannot resample an empty series")
    series = series.sort_index()
    idx = pd.date_range(series.index.min(), series.index.max() + pd.Timedelta(minutes=45), freq="15min")
    return series.reindex(idx, method="ffill").astype(float)


def apply_pv_forecast_error(pv_actual_kw: np.ndarray, sigma: float, seed: int | None) -> np.ndarray:
    """Apply max(0, pv_actual*(1+epsilon)) with deterministic Gaussian epsilon."""

    pv_actual_kw = np.asarray(pv_actual_kw, dtype=float)
    if sigma < 0:
        raise ValueError("sigma must be non-negative")
    if np.any(~np.isfinite(pv_actual_kw)) or np.any(pv_actual_kw < -1e-9):
        raise SchemaValidationError("pv_actual_kw must be finite and non-negative")
    if sigma == 0:
        return np.maximum(0.0, pv_actual_kw.copy())
    rng = np.random.default_rng(seed)
    epsilon = rng.normal(loc=0.0, scale=sigma, size=pv_actual_kw.shape)
    return np.maximum(0.0, pv_actual_kw * (1.0 + epsilon))


class ForecastBuilder:
    """Build aligned forecast bundles from current南京 PV/TOU inputs."""

    def __init__(
        self,
        pv_csv: str | Path,
        price_csv: str | Path,
        facility_model: FacilityModel,
        room_model: RoomModel,
        dt_hours: float,
    ):
        if abs(dt_hours - 0.25) > 1e-9:
            raise ValueError(f"ForecastBuilder currently expects 15-minute steps, got {dt_hours}")
        self.dt_hours = float(dt_hours)
        self.facility_model = facility_model
        self.room_model = room_model
        self.pv_15min = resample_hourly_to_15min(load_hourly_csv(pv_csv, "power_kw"))
        self.price_15min = resample_hourly_to_15min(load_hourly_csv(price_csv, "price_usd_per_mwh"))

    def build(
        self,
        now_ts: datetime | str,
        horizon_steps: int,
        pv_error_sigma: float,
        seed: int | None,
        it_load_kw: float,
        outdoor_base_c: float,
        outdoor_amplitude_c: float,
        outdoor_offset_c: float,
        tariff_multiplier: float,
        pv_scale: float = 1.0,
        wet_bulb_depression_c: float = 4.0,
    ) -> ForecastBundle:
        if horizon_steps <= 0:
            raise ValueError("horizon_steps must be positive")
        now = parse_timestamp(now_ts)
        timestamps = [now + timedelta(minutes=15 * i) for i in range(horizon_steps)]
        pv_actual = _take_cyclic(self.pv_15min, timestamps) * float(pv_scale)
        pv_forecast = apply_pv_forecast_error(pv_actual, sigma=pv_error_sigma, seed=seed)
        price = _take_cyclic(self.price_15min, timestamps) * float(tariff_multiplier)
        hours = np.array([ts.hour + ts.minute / 60.0 for ts in timestamps], dtype=float)
        outdoor = (
            float(outdoor_base_c)
            + float(outdoor_offset_c)
            + float(outdoor_amplitude_c) * np.sin(2.0 * np.pi * (hours - 15.0) / 24.0)
        )
        it_load = np.full(horizon_steps, float(it_load_kw))
        base_facility = np.array(
            [self.facility_model.base_facility_kw(float(it), float(temp)) for it, temp in zip(it_load, outdoor)]
        )
        base_cooling = np.array([self.room_model.base_cooling_kw_th(float(it)) for it in it_load])
        wet_bulb = outdoor - float(wet_bulb_depression_c)
        bundle = ForecastBundle(
            timestamps=timestamps,
            outdoor_temp_forecast_c=outdoor.tolist(),
            it_load_forecast_kw=it_load.tolist(),
            pv_forecast_kw=pv_forecast.tolist(),
            price_forecast=price.tolist(),
            base_facility_kw=base_facility.tolist(),
            base_cooling_kw_th=base_cooling.tolist(),
            wet_bulb_forecast_c=wet_bulb.tolist(),
        )
        bundle.validate(horizon_steps=horizon_steps, dt_hours=self.dt_hours)
        return bundle

    def actual_at(
        self,
        now_ts: datetime | str,
        it_load_kw: float,
        outdoor_base_c: float,
        outdoor_amplitude_c: float,
        outdoor_offset_c: float,
        tariff_multiplier: float,
        pv_scale: float = 1.0,
        wet_bulb_depression_c: float = 4.0,
    ) -> ForecastBundle:
        """Return the one-step actual disturbance bundle without forecast error."""

        return self.build(
            now_ts=now_ts,
            horizon_steps=1,
            pv_error_sigma=0.0,
            seed=None,
            it_load_kw=it_load_kw,
            outdoor_base_c=outdoor_base_c,
            outdoor_amplitude_c=outdoor_amplitude_c,
            outdoor_offset_c=outdoor_offset_c,
            tariff_multiplier=tariff_multiplier,
            pv_scale=pv_scale,
            wet_bulb_depression_c=wet_bulb_depression_c,
        )


def _take_cyclic(series: pd.Series, timestamps: list[datetime]) -> np.ndarray:
    """Map requested timestamps to the annual profile by month/day/hour/minute."""

    by_key = {(ts.month, ts.day, ts.hour, ts.minute): float(value) for ts, value in series.items()}
    fallback = float(series.iloc[0])
    return np.asarray([by_key.get((ts.month, ts.day, ts.hour, ts.minute), fallback) for ts in timestamps], dtype=float)
