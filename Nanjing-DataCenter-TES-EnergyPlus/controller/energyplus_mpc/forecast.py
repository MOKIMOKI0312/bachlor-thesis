"""Forecast adapters for the EnergyPlus-MPC runner."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np

from .common import cyclic_lookup, load_baseline_timeseries, load_external_series


class ForecastProvider:
    def __init__(self, baseline_timeseries: str, price_csv: str, pv_csv: str, horizon_steps: int = 8):
        self.baseline = load_baseline_timeseries(baseline_timeseries)
        self.external = load_external_series(price_csv, pv_csv)
        self.horizon_steps = int(horizon_steps)

    def horizon(self, step: int, now: datetime, load_forecast: str = "baseline") -> dict[str, np.ndarray | list[datetime]]:
        timestamps = [now + timedelta(minutes=15 * i) for i in range(self.horizon_steps)]
        if load_forecast == "persistence":
            row = self.baseline.iloc[min(step, len(self.baseline) - 1)]
            q_load = np.full(self.horizon_steps, max(float(row["chiller_cooling_kw"]), 0.0), dtype=float)
        else:
            idx = [(step + i) % len(self.baseline) for i in range(self.horizon_steps)]
            q_load = self.baseline.iloc[idx]["chiller_cooling_kw"].clip(lower=0.0).to_numpy(dtype=float)
        idx = [(step + i) % len(self.baseline) for i in range(self.horizon_steps)]
        p_nonplant = (
            self.baseline.iloc[idx]["facility_electricity_kw"].to_numpy(dtype=float)
            - self.baseline.iloc[idx]["chiller_electricity_kw"].to_numpy(dtype=float)
        )
        t_wb = self.baseline.iloc[idx]["outdoor_wetbulb_c"].to_numpy(dtype=float)
        return {
            "timestamps": timestamps,
            "q_load_kw_th": q_load,
            "p_nonplant_kw": np.maximum(0.0, p_nonplant),
            "p_pv_kw": cyclic_lookup(self.external.pv_kw, timestamps),
            "price_per_kwh": cyclic_lookup(self.external.price_per_kwh, timestamps),
            "t_wb_c": t_wb,
        }
