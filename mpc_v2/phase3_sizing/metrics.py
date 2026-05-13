"""Phase 3 technical sizing metrics."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


def critical_peak_flags(timestamps: Iterable[Any], windows: list[list[float]]) -> pd.Series:
    """Return explicit critical-peak flags from hour windows."""

    flags = []
    index = []
    for value in timestamps:
        ts = pd.Timestamp(value).to_pydatetime()
        hour = ts.hour + ts.minute / 60.0 + ts.second / 3600.0
        flags.append(any(float(start) <= hour < float(end) for start, end in windows))
        index.append(ts)
    return pd.Series(flags, index=pd.DatetimeIndex(index), dtype=bool)


def apply_critical_peak_uplift(
    base_price: pd.Series,
    uplift: float,
    windows: list[list[float]],
) -> tuple[pd.Series, pd.Series]:
    """Apply price_cp[t] = price_base[t] * (1 + uplift * I_cp[t])."""

    if float(uplift) < 0:
        raise ValueError("critical peak uplift must be non-negative")
    flags = critical_peak_flags(base_price.index, windows)
    flags = flags.reindex(base_price.index)
    adjusted = base_price.astype(float) * (1.0 + float(uplift) * flags.astype(float))
    return adjusted.rename(base_price.name), flags.astype(int).rename("critical_peak_flag")


def compute_case_metrics(
    timeseries: pd.DataFrame,
    dt_hours: float,
    tes_capacity_mwh_th: float,
    soc_min: float,
    soc_max: float,
    max_signed_du: float,
) -> dict[str, float]:
    """Compute per-scenario metrics before cross-case baselines."""

    required = [
        "facility_power_kw",
        "grid_import_kw",
        "pv_kw",
        "pv_spill_kw",
        "price_currency_per_mwh",
        "critical_peak_flag",
        "q_tes_ch_kw_th",
        "q_tes_dis_kw_th",
        "Q_tes_net_kw_th",
        "soc",
        "signed_tes_u",
        "grid_balance_error_kw",
    ]
    missing = [name for name in required if name not in timeseries.columns]
    if missing:
        raise ValueError(f"timeseries is missing columns: {missing}")

    dt = float(dt_hours)
    cp = timeseries["critical_peak_flag"].astype(bool)
    facility_energy_kwh = _energy(timeseries["facility_power_kw"], dt)
    grid_import_kwh = _energy(timeseries["grid_import_kw"], dt)
    pv_generation_kwh = _energy(timeseries["pv_kw"], dt)
    pv_spill_kwh = _energy(timeseries["pv_spill_kw"], dt)
    pv_used_kwh = max(0.0, pv_generation_kwh - pv_spill_kwh)
    total_cost = float((timeseries["price_currency_per_mwh"] * timeseries["grid_import_kw"] * dt / 1000.0).sum())
    cp_duration_h = float(cp.sum() * dt)
    cp_grid_kwh = _energy(timeseries.loc[cp, "grid_import_kw"], dt)
    cp_pv_used_kwh = _energy(_pv_used_kw(timeseries).loc[cp], dt)
    cp_tes_discharge = _energy(timeseries.loc[cp, "q_tes_dis_kw_th"], dt)
    cp_tes_charge = _energy(timeseries.loc[cp, "q_tes_ch_kw_th"], dt)
    tes_charge = _energy(timeseries["Q_tes_net_kw_th"].clip(lower=0.0), dt)
    tes_discharge = _energy((-timeseries["Q_tes_net_kw_th"]).clip(lower=0.0), dt)
    effective_capacity = float(tes_capacity_mwh_th) * 1000.0 * (float(soc_max) - float(soc_min))
    signed_du = timeseries["signed_tes_u"].astype(float).diff().abs().fillna(timeseries["signed_tes_u"].abs())

    return {
        "facility_energy_kwh": facility_energy_kwh,
        "grid_import_kwh": grid_import_kwh,
        "pv_generation_kwh": pv_generation_kwh,
        "pv_spill_kwh": pv_spill_kwh,
        "pv_used_kwh": pv_used_kwh,
        "pv_self_consumption_ratio": _safe_div(pv_used_kwh, pv_generation_kwh),
        "pv_facility_load_coverage_ratio": _safe_div(pv_used_kwh, facility_energy_kwh),
        "peak_grid_kw": float(timeseries["grid_import_kw"].max()) if len(timeseries) else np.nan,
        "total_cost": total_cost,
        "energy_cost": total_cost,
        "critical_peak_duration_h": cp_duration_h,
        "critical_peak_grid_kwh": cp_grid_kwh,
        "critical_peak_avg_grid_kw": _safe_div(cp_grid_kwh, cp_duration_h),
        "critical_peak_pv_used_kwh": cp_pv_used_kwh,
        "critical_peak_tes_discharge_kwh_th": cp_tes_discharge,
        "critical_peak_tes_charge_kwh_th": cp_tes_charge,
        "tes_charge_kwh_th": tes_charge if tes_capacity_mwh_th > 0 else 0.0,
        "tes_discharge_kwh_th": tes_discharge if tes_capacity_mwh_th > 0 else 0.0,
        "tes_discharge_cp_ratio": _safe_div(cp_tes_discharge, tes_discharge),
        "tes_effective_capacity_kwh_th": effective_capacity,
        "tes_cp_capacity_utilization": _safe_div(cp_tes_discharge, effective_capacity),
        "soc_initial": float(timeseries["soc"].iloc[0]) if len(timeseries) else np.nan,
        "soc_final": float(timeseries["soc"].iloc[-1]) if len(timeseries) else np.nan,
        "soc_delta": float(timeseries["soc"].iloc[-1] - timeseries["soc"].iloc[0]) if len(timeseries) else np.nan,
        "soc_min_observed": float(timeseries["soc"].min()) if len(timeseries) else np.nan,
        "soc_max_observed": float(timeseries["soc"].max()) if len(timeseries) else np.nan,
        "grid_balance_max_abs_error_kw": float(timeseries["grid_balance_error_kw"].abs().max()) if len(timeseries) else 0.0,
        "signed_valve_max_abs_delta": float(signed_du.max()) if len(timeseries) else 0.0,
        "signed_valve_violation_max": max(0.0, float(signed_du.max()) - float(max_signed_du)) if len(timeseries) else 0.0,
    }


def add_relative_metrics(summary: pd.DataFrame) -> pd.DataFrame:
    """Add baseline-relative peak and critical-peak impact metrics."""

    frame = summary.copy()
    for col in [
        "peak_reduction_kw",
        "peak_reduction_ratio",
        "critical_peak_cost_impact",
        "critical_peak_suppression_ratio",
        "critical_peak_grid_reduction_kwh",
    ]:
        frame[col] = np.nan

    baseline = frame[(frame["pv_capacity_mwp"] == 0) & (frame["tes_capacity_mwh_th"] == 0)]
    for idx, row in frame.iterrows():
        base = baseline[
            (baseline["location_id"] == row["location_id"])
            & (baseline["critical_peak_uplift"] == row["critical_peak_uplift"])
        ]
        if not base.empty:
            base_row = base.iloc[0]
            frame.at[idx, "peak_reduction_kw"] = float(base_row["peak_grid_kw"]) - float(row["peak_grid_kw"])
            frame.at[idx, "peak_reduction_ratio"] = _safe_div(
                float(frame.at[idx, "peak_reduction_kw"]), float(base_row["peak_grid_kw"])
            )

    base_cp0 = frame[frame["critical_peak_uplift"] == 0.0][
        ["location_id", "pv_capacity_mwp", "tes_capacity_mwh_th", "total_cost"]
    ].rename(columns={"total_cost": "total_cost_cp0"})
    frame = frame.merge(base_cp0, on=["location_id", "pv_capacity_mwp", "tes_capacity_mwh_th"], how="left")
    frame["critical_peak_cost_impact"] = frame["total_cost"] - frame["total_cost_cp0"]

    for idx, row in frame.iterrows():
        uplift = float(row["critical_peak_uplift"])
        if uplift <= 0:
            continue
        no_tes_now = frame[
            (frame["location_id"] == row["location_id"])
            & (frame["pv_capacity_mwp"] == row["pv_capacity_mwp"])
            & (frame["tes_capacity_mwh_th"] == 0)
            & (frame["critical_peak_uplift"] == uplift)
        ]
        no_tes_cp0 = frame[
            (frame["location_id"] == row["location_id"])
            & (frame["pv_capacity_mwp"] == row["pv_capacity_mwp"])
            & (frame["tes_capacity_mwh_th"] == 0)
            & (frame["critical_peak_uplift"] == 0.0)
        ]
        if no_tes_now.empty or no_tes_cp0.empty:
            continue
        impact_ref = float(no_tes_now.iloc[0]["total_cost"] - no_tes_cp0.iloc[0]["total_cost"])
        impact_case = float(row["total_cost"] - row["total_cost_cp0"])
        if impact_ref > 0:
            frame.at[idx, "critical_peak_suppression_ratio"] = 1.0 - impact_case / impact_ref
        frame.at[idx, "critical_peak_grid_reduction_kwh"] = float(no_tes_now.iloc[0]["critical_peak_grid_kwh"]) - float(
            row["critical_peak_grid_kwh"]
        )

    return frame.drop(columns=["total_cost_cp0"])


def add_marginal_metrics(summary: pd.DataFrame) -> pd.DataFrame:
    """Add PV and TES marginal-gain columns."""

    frame = summary.copy()
    frame["marginal_cp_suppression_per_mwh"] = np.nan
    frame["marginal_peak_reduction_per_mwp"] = np.nan
    frame["diminishing_return_after_this_capacity"] = False

    active = frame[frame["critical_peak_uplift"] > 0].copy()
    for (location_id, pv), group in active.groupby(["location_id", "pv_capacity_mwp"]):
        ordered = group.sort_values("tes_capacity_mwh_th")
        previous_gain = np.nan
        previous_index = None
        previous_ratio = None
        previous_capacity = None
        for idx, row in ordered.iterrows():
            ratio = float(row["critical_peak_suppression_ratio"]) if pd.notna(row["critical_peak_suppression_ratio"]) else np.nan
            capacity = float(row["tes_capacity_mwh_th"])
            if previous_ratio is not None and capacity > previous_capacity:
                gain = ratio - previous_ratio
                frame.at[idx, "marginal_cp_suppression_per_mwh"] = gain / (capacity - previous_capacity)
                if pd.notna(previous_gain) and previous_gain > 0 and gain < 0.05 * previous_gain and previous_index is not None:
                    frame.at[previous_index, "diminishing_return_after_this_capacity"] = True
                previous_gain = gain
            previous_index = idx
            previous_ratio = ratio
            previous_capacity = capacity

    for (location_id, tes), group in active.groupby(["location_id", "tes_capacity_mwh_th"]):
        ordered = group.sort_values("pv_capacity_mwp")
        prev_ratio = None
        prev_capacity = None
        for idx, row in ordered.iterrows():
            ratio = float(row["peak_reduction_ratio"]) if pd.notna(row["peak_reduction_ratio"]) else np.nan
            capacity = float(row["pv_capacity_mwp"])
            if prev_ratio is not None and capacity > prev_capacity:
                frame.at[idx, "marginal_peak_reduction_per_mwp"] = (ratio - prev_ratio) / (capacity - prev_capacity)
            prev_ratio = ratio
            prev_capacity = capacity
    return frame


def _energy(series: pd.Series, dt_hours: float) -> float:
    if len(series) == 0:
        return 0.0
    return float((pd.to_numeric(series, errors="raise").astype(float) * float(dt_hours)).sum())


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator is None or float(denominator) <= 0 or not np.isfinite(float(denominator)):
        return float("nan")
    return float(numerator) / float(denominator)


def _pv_used_kw(timeseries: pd.DataFrame) -> pd.Series:
    if "pv_used_kw" in timeseries.columns:
        return pd.to_numeric(timeseries["pv_used_kw"], errors="raise").astype(float)
    return pd.to_numeric(timeseries["pv_kw"], errors="raise").astype(float) - pd.to_numeric(
        timeseries["pv_spill_kw"], errors="raise"
    ).astype(float)
