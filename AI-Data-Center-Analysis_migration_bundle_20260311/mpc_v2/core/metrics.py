"""Closed-loop metrics for MPC v2."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class EpisodeMetrics:
    """Summary metrics written to episode_summary.json."""

    case_id: str
    cost_total: float
    cost_peak: float
    cost_valley: float
    grid_import_mwh: float
    pv_total_mwh: float
    pv_self_consumed_mwh: float
    pv_self_consumption_rate_pct: float
    pv_load_coverage_pct: float
    pv_spill_mwh: float
    temp_violation_count: int
    temp_violation_degree_hours: float
    tes_cycles_equiv: float
    soc_violation_count: int
    pue_avg: float
    pue_p95: float
    solve_time_avg_s: float
    solve_time_p95_s: float
    optimal_rate: float
    has_nan: bool
    infeasible_count: int


def compute_episode_metrics(
    monitor: pd.DataFrame,
    solver_log: pd.DataFrame,
    case_id: str,
    dt_h: float = 0.25,
    temp_min_C: float = 18.0,
    temp_max_C: float = 27.0,
    soc_min_phys: float = 0.05,
    soc_max_phys: float = 0.95,
) -> EpisodeMetrics:
    """Compute required economic, PV, comfort, TES, PUE, and solver metrics."""

    required = [
        "price_usd_per_mwh",
        "P_grid_kw",
        "P_spill_kw",
        "pv_kw",
        "facility_power_kw",
        "air_temperature_C",
        "tes_soc",
        "tes_charge_kwth",
        "tes_discharge_kwth",
        "pue_actual",
    ]
    missing = [name for name in required if name not in monitor.columns]
    if missing:
        raise ValueError(f"monitor is missing columns: {missing}")
    solver_required = ["status", "solve_time_s"]
    solver_missing = [name for name in solver_required if name not in solver_log.columns]
    if solver_missing:
        raise ValueError(f"solver_log is missing columns: {solver_missing}")
    has_nan = bool(monitor[required].isna().any().any() or solver_log[solver_required].isna().any().any())
    cost_step = monitor["price_usd_per_mwh"] * monitor["P_grid_kw"] * dt_h / 1000.0
    peak_mask = monitor["price_usd_per_mwh"] >= monitor["price_usd_per_mwh"].quantile(0.75)
    valley_mask = monitor["price_usd_per_mwh"] <= monitor["price_usd_per_mwh"].quantile(0.25)
    pv_total_mwh = float((monitor["pv_kw"] * dt_h / 1000.0).sum())
    pv_spill_mwh = float((monitor["P_spill_kw"] * dt_h / 1000.0).sum())
    pv_self = max(0.0, pv_total_mwh - pv_spill_mwh)
    facility_mwh = float((monitor["facility_power_kw"] * dt_h / 1000.0).sum())
    temp_hi = (monitor["air_temperature_C"] - temp_max_C).clip(lower=0.0)
    temp_lo = (temp_min_C - monitor["air_temperature_C"]).clip(lower=0.0)
    temp_violation = temp_hi + temp_lo
    soc_bad = (monitor["tes_soc"] < soc_min_phys - 1e-7) | (monitor["tes_soc"] > soc_max_phys + 1e-7)
    optimal_rate = _optimal_rate(solver_log["status"])
    infeasible_count = int((solver_log["status"] == "infeasible").sum())
    return EpisodeMetrics(
        case_id=case_id,
        cost_total=float(cost_step.sum()),
        cost_peak=float(cost_step[peak_mask].sum()),
        cost_valley=float(cost_step[valley_mask].sum()),
        grid_import_mwh=float((monitor["P_grid_kw"] * dt_h / 1000.0).sum()),
        pv_total_mwh=pv_total_mwh,
        pv_self_consumed_mwh=pv_self,
        pv_self_consumption_rate_pct=100.0 * pv_self / pv_total_mwh if pv_total_mwh > 0 else 0.0,
        pv_load_coverage_pct=100.0 * pv_self / facility_mwh if facility_mwh > 0 else 0.0,
        pv_spill_mwh=pv_spill_mwh,
        temp_violation_count=int((temp_violation > 1e-7).sum()),
        temp_violation_degree_hours=float((temp_violation * dt_h).sum()),
        tes_cycles_equiv=float(((monitor["tes_charge_kwth"] + monitor["tes_discharge_kwth"]) * dt_h).sum() / max(1e-9, 2.0 * _capacity_hint(monitor))),
        soc_violation_count=int(soc_bad.sum()),
        pue_avg=float(monitor["pue_actual"].mean()),
        pue_p95=float(monitor["pue_actual"].quantile(0.95)),
        solve_time_avg_s=float(solver_log["solve_time_s"].mean()),
        solve_time_p95_s=float(solver_log["solve_time_s"].quantile(0.95)),
        optimal_rate=optimal_rate,
        has_nan=has_nan,
        infeasible_count=infeasible_count,
    )


def _optimal_rate(status_values: Iterable[object]) -> float:
    values = list(status_values)
    if not values:
        return 0.0
    return sum(1 for v in values if str(v).lower() == "optimal") / len(values)


def _capacity_hint(monitor: pd.DataFrame) -> float:
    if "tes_capacity_kwh" in monitor.columns:
        value = float(monitor["tes_capacity_kwh"].iloc[0])
        if math.isfinite(value) and value > 0:
            return value
    return 18000.0
