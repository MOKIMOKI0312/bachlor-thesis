"""Closed-loop summary metrics for MPC v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class EpisodeSummary:
    """JSON-serializable episode summary."""

    scenario_id: str
    controller_type: str
    closed_loop_steps: int
    dt_hours: float
    total_cost: float
    energy_cost: float
    demand_charge_cost: float
    grid_import_kwh: float
    peak_grid_kw: float
    pv_actual_kwh: float
    pv_used_kwh: float
    pv_spill_kwh: float
    pv_self_consumption_ratio: float
    pv_load_coverage_ratio: float
    it_energy_kwh: float
    facility_energy_kwh: float
    cold_station_energy_kwh: float
    pue_avg: float
    pue_p95: float
    temp_violation_count: int
    temp_violation_degree_hours: float
    max_temp_c: float
    soc_min: float
    soc_max: float
    soc_violation_count: int
    tes_charge_kwh_th: float
    tes_discharge_kwh_th: float
    tes_equivalent_cycles: float
    avg_chiller_plr: float
    time_in_high_plr_region: float
    solve_time_avg_s: float
    solve_time_p95_s: float
    optimal_rate: float
    feasible_rate: float
    fallback_count: int
    has_nan: bool


def compute_episode_metrics(
    monitor: pd.DataFrame,
    solver_log: pd.DataFrame,
    scenario_id: str,
    controller_type: str,
    dt_hours: float,
    temp_min_c: float,
    temp_max_c: float,
    soc_physical_min: float,
    soc_physical_max: float,
    tes_capacity_kwh_th: float,
) -> EpisodeSummary:
    """Compute economic, PV, thermal, TES, and solver metrics."""

    required = [
        "price_currency_per_mwh",
        "grid_import_kw",
        "pv_spill_kw",
        "pv_actual_kw",
        "it_load_kw",
        "facility_power_kw",
        "cold_station_power_kw",
        "q_chiller_kw_th",
        "room_temp_c",
        "soc",
        "q_ch_tes_kw_th",
        "q_dis_tes_kw_th",
        "pue",
        "fallback_used",
    ]
    missing = [name for name in required if name not in monitor.columns]
    if missing:
        raise ValueError(f"monitor is missing columns: {missing}")
    solver_required = ["solve_status", "solve_time_s"]
    solver_missing = [name for name in solver_required if name not in solver_log.columns]
    if solver_missing:
        raise ValueError(f"solver_log is missing columns: {solver_missing}")

    has_nan = bool(monitor[required].isna().any().any() or solver_log[solver_required].isna().any().any())
    grid_import_kwh = float((monitor["grid_import_kw"] * dt_hours).sum())
    peak_grid_kw = float(monitor["grid_import_kw"].max()) if len(monitor) else 0.0
    pv_actual_kwh = float((monitor["pv_actual_kw"] * dt_hours).sum())
    pv_spill_kwh = float((monitor["pv_spill_kw"] * dt_hours).sum())
    pv_used_kwh = max(0.0, pv_actual_kwh - pv_spill_kwh)
    facility_energy_kwh = float((monitor["facility_power_kw"] * dt_hours).sum())
    cold_station_energy_kwh = float((monitor["cold_station_power_kw"] * dt_hours).sum())
    it_energy_kwh = float((monitor["it_load_kw"] * dt_hours).sum())
    energy_cost = float((monitor["price_currency_per_mwh"] * monitor["grid_import_kw"] * dt_hours / 1000.0).sum())
    demand_rate = float(monitor["demand_charge_rate"].max()) if "demand_charge_rate" in monitor.columns else 0.0
    demand_charge_cost = peak_grid_kw * demand_rate
    cost = energy_cost + demand_charge_cost
    temp_hi = (monitor["room_temp_c"] - temp_max_c).clip(lower=0.0)
    temp_lo = (temp_min_c - monitor["room_temp_c"]).clip(lower=0.0)
    temp_violation = temp_hi + temp_lo
    soc_bad = (monitor["soc"] < soc_physical_min - 1e-7) | (monitor["soc"] > soc_physical_max + 1e-7)
    status_values = [str(v).lower() for v in solver_log["solve_status"]]
    q_max_observed = float(monitor["q_chiller_kw_th"].max()) if len(monitor) else 0.0
    if q_max_observed > 1e-9:
        plr = monitor["q_chiller_kw_th"] / q_max_observed
        avg_chiller_plr = float(plr[monitor["q_chiller_kw_th"] > 1e-9].mean())
        time_in_high_plr_region = float(((plr >= 0.75) & (monitor["q_chiller_kw_th"] > 1e-9)).sum() * dt_hours)
    else:
        avg_chiller_plr = 0.0
        time_in_high_plr_region = 0.0
    return EpisodeSummary(
        scenario_id=scenario_id,
        controller_type=controller_type,
        closed_loop_steps=int(len(monitor)),
        dt_hours=float(dt_hours),
        total_cost=cost,
        energy_cost=energy_cost,
        demand_charge_cost=demand_charge_cost,
        grid_import_kwh=grid_import_kwh,
        peak_grid_kw=peak_grid_kw,
        pv_actual_kwh=pv_actual_kwh,
        pv_used_kwh=pv_used_kwh,
        pv_spill_kwh=pv_spill_kwh,
        pv_self_consumption_ratio=pv_used_kwh / pv_actual_kwh if pv_actual_kwh > 0 else 0.0,
        pv_load_coverage_ratio=pv_used_kwh / cold_station_energy_kwh if cold_station_energy_kwh > 0 else 0.0,
        it_energy_kwh=it_energy_kwh,
        facility_energy_kwh=facility_energy_kwh,
        cold_station_energy_kwh=cold_station_energy_kwh,
        pue_avg=facility_energy_kwh / it_energy_kwh if it_energy_kwh > 0 else 0.0,
        pue_p95=float(monitor["pue"].quantile(0.95)),
        temp_violation_count=int((temp_violation > 1e-7).sum()),
        temp_violation_degree_hours=float((temp_violation * dt_hours).sum()),
        max_temp_c=float(monitor["room_temp_c"].max()),
        soc_min=float(monitor["soc"].min()),
        soc_max=float(monitor["soc"].max()),
        soc_violation_count=int(soc_bad.sum()),
        tes_charge_kwh_th=float((monitor["q_ch_tes_kw_th"] * dt_hours).sum()),
        tes_discharge_kwh_th=float((monitor["q_dis_tes_kw_th"] * dt_hours).sum()),
        tes_equivalent_cycles=float((monitor["q_dis_tes_kw_th"] * dt_hours).sum() / max(1e-9, tes_capacity_kwh_th)),
        avg_chiller_plr=avg_chiller_plr,
        time_in_high_plr_region=time_in_high_plr_region,
        solve_time_avg_s=float(solver_log["solve_time_s"].mean()),
        solve_time_p95_s=float(solver_log["solve_time_s"].quantile(0.95)),
        optimal_rate=_rate(status_values, {"optimal", "baseline"}),
        feasible_rate=_rate(status_values, {"optimal", "time_limit", "baseline", "fallback"}),
        fallback_count=int(monitor["fallback_used"].astype(bool).sum()),
        has_nan=has_nan,
    )


def _rate(values: Iterable[str], accepted: set[str]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(1 for value in values if value in accepted) / len(values)
