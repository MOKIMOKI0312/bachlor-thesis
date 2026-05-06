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
    cold_station_proxy_total_cost: float
    cold_station_proxy_energy_cost: float
    cold_station_proxy_grid_import_kwh: float
    cold_station_proxy_pv_spill_kwh: float
    grid_import_kwh: float
    peak_grid_kw: float
    peak_slack_max_kw: float
    peak_slack_step_count: int
    pv_actual_kwh: float
    pv_used_kwh: float
    pv_spill_kwh: float
    pv_spill_reduction_vs_no_tes: float | None
    tes_charge_during_pv_surplus_kwh_th: float
    soc_headroom_before_pv_hours: float
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
    initial_soc: float
    final_soc_after_last_update: float
    soc_delta: float
    soc_inventory_delta_kwh_th: float
    tes_charge_kwh_th: float
    tes_discharge_kwh_th: float
    tes_equivalent_cycles: float
    tes_charge_weighted_avg_price: float | None
    tes_discharge_weighted_avg_price: float | None
    tes_arbitrage_price_spread: float | None
    charge_steps: int
    discharge_steps: int
    idle_steps: int
    charge_discharge_switch_count: int
    first_discharge_step: int | None
    first_discharge_timestamp: str | None
    avg_chiller_plr: float
    avg_mode_specific_plr: float
    weighted_avg_chiller_cop: float
    time_in_high_plr_region: float
    low_plr_hours: float
    high_plr_hours: float
    time_in_each_mode: dict[str, float]
    mode_switch_count: int
    max_signed_du: float
    signed_valve_violation_count: int
    physical_consistency_violation_count: int
    max_chiller_supply_deficit_kw_th: float
    max_signed_valve_du: float
    tes_discharge_during_peak_cap_violation_kwh_th: float
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
    soc_planning_max: float,
    tes_capacity_kwh_th: float,
    initial_soc: float,
    final_soc_after_last_update: float,
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
        "q_load_kw_th",
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
    if "cold_station_proxy_grid_import_kw" in monitor.columns:
        cold_proxy_grid_kw = monitor["cold_station_proxy_grid_import_kw"]
    else:
        cold_proxy_grid_kw = (monitor["cold_station_power_kw"] - monitor["pv_actual_kw"]).clip(lower=0.0)
    if "cold_station_proxy_pv_spill_kw" in monitor.columns:
        cold_proxy_spill_kw = monitor["cold_station_proxy_pv_spill_kw"]
    else:
        cold_proxy_spill_kw = (monitor["pv_actual_kw"] - monitor["cold_station_power_kw"]).clip(lower=0.0)
    cold_station_proxy_grid_import_kwh = float((cold_proxy_grid_kw * dt_hours).sum())
    cold_station_proxy_pv_spill_kwh = float((cold_proxy_spill_kw * dt_hours).sum())
    facility_energy_kwh = float((monitor["facility_power_kw"] * dt_hours).sum())
    cold_station_energy_kwh = float((monitor["cold_station_power_kw"] * dt_hours).sum())
    it_energy_kwh = float((monitor["it_load_kw"] * dt_hours).sum())
    energy_cost = float((monitor["price_currency_per_mwh"] * monitor["grid_import_kw"] * dt_hours / 1000.0).sum())
    cold_station_proxy_energy_cost = float((monitor["price_currency_per_mwh"] * cold_proxy_grid_kw * dt_hours / 1000.0).sum())
    demand_rate = float(monitor["demand_charge_rate"].max()) if "demand_charge_rate" in monitor.columns else 0.0
    demand_basis = str(monitor["demand_charge_basis"].iloc[0]) if "demand_charge_basis" in monitor.columns and len(monitor) else "per_day_proxy"
    episode_days = len(monitor) * dt_hours / 24.0
    demand_multiplier = 1.0 if demand_basis == "per_episode" else episode_days
    demand_charge_cost = peak_grid_kw * demand_rate * demand_multiplier
    cost = energy_cost + demand_charge_cost
    cold_station_proxy_peak_kw = float(cold_proxy_grid_kw.max()) if len(monitor) else 0.0
    cold_station_proxy_total_cost = cold_station_proxy_energy_cost + cold_station_proxy_peak_kw * demand_rate * demand_multiplier
    temp_hi = (monitor["room_temp_c"] - temp_max_c).clip(lower=0.0)
    temp_lo = (temp_min_c - monitor["room_temp_c"]).clip(lower=0.0)
    temp_violation = temp_hi + temp_lo
    soc_bad = (monitor["soc"] < soc_physical_min - 1e-7) | (monitor["soc"] > soc_physical_max + 1e-7)
    status_values = [str(v).lower() for v in solver_log["solve_status"]]
    q_on = monitor["q_chiller_kw_th"] > 1e-9
    if "mode_specific_plr" in monitor.columns:
        plr = monitor["mode_specific_plr"].fillna(0.0)
    else:
        q_max_observed = float(monitor["q_chiller_kw_th"].max()) if len(monitor) else 0.0
        plr = monitor["q_chiller_kw_th"] / q_max_observed if q_max_observed > 1e-9 else monitor["q_chiller_kw_th"] * 0.0
    avg_chiller_plr = float(plr[q_on].mean()) if bool(q_on.any()) else 0.0
    avg_mode_specific_plr = avg_chiller_plr
    high_plr_hours = float(((plr >= 0.75) & q_on).sum() * dt_hours)
    low_plr_hours = float(((plr < 0.50) & q_on).sum() * dt_hours)
    time_in_high_plr_region = high_plr_hours
    chiller_thermal_kwh = float((monitor["q_chiller_kw_th"] * dt_hours).sum())
    chiller_electric_kwh = float((monitor["plant_power_kw"] * dt_hours).sum())
    weighted_avg_chiller_cop = chiller_thermal_kwh / chiller_electric_kwh if chiller_electric_kwh > 0 else 0.0

    supply_deficit = (monitor["q_load_kw_th"] + monitor["q_ch_tes_kw_th"] - monitor["q_chiller_kw_th"]).clip(lower=0.0)
    physical_count = int((supply_deficit > 1e-6).sum())
    max_supply_deficit = float(supply_deficit.max()) if len(supply_deficit) else 0.0
    signed_du = monitor["signed_du"] if "signed_du" in monitor.columns else (monitor.get("u_ch", 0.0) - monitor.get("u_dis", 0.0)).diff().abs().fillna(0.0)
    max_signed_du = float(signed_du.max()) if len(monitor) else 0.0
    du_limit = float(monitor["du_signed_max"].max()) if "du_signed_max" in monitor.columns else float("inf")
    signed_violation_count = int((signed_du > du_limit + 1e-8).sum()) if len(monitor) else 0

    initial_soc = float(initial_soc)
    final_soc_after_last_update = float(final_soc_after_last_update)
    soc_delta = final_soc_after_last_update - initial_soc
    soc_inventory_delta_kwh_th = soc_delta * float(tes_capacity_kwh_th)

    charge_energy = monitor["q_ch_tes_kw_th"] * dt_hours
    discharge_energy = monitor["q_dis_tes_kw_th"] * dt_hours
    tes_charge_kwh_th = float(charge_energy.sum())
    tes_discharge_kwh_th = float(discharge_energy.sum())
    charge_price = _weighted_average(monitor["price_currency_per_mwh"], charge_energy)
    discharge_price = _weighted_average(monitor["price_currency_per_mwh"], discharge_energy)
    arbitrage_spread = None if charge_price is None or discharge_price is None else discharge_price - charge_price

    charge_mask = (monitor["q_ch_tes_kw_th"] > 1e-7) & (monitor["q_dis_tes_kw_th"] <= 1e-7)
    discharge_mask = (monitor["q_dis_tes_kw_th"] > 1e-7) & (monitor["q_ch_tes_kw_th"] <= 1e-7)
    idle_mask = ~(charge_mask | discharge_mask)
    states = ["charge" if c else "discharge" if d else "idle" for c, d in zip(charge_mask, discharge_mask)]
    charge_discharge_switch_count = _charge_discharge_switch_count(states)
    first_discharge_step = int(monitor.loc[discharge_mask, "step"].iloc[0]) if bool(discharge_mask.any()) and "step" in monitor.columns else None
    first_discharge_timestamp = str(monitor.loc[discharge_mask, "timestamp"].iloc[0]) if bool(discharge_mask.any()) and "timestamp" in monitor.columns else None

    peak_slack = monitor["peak_slack_kw"] if "peak_slack_kw" in monitor.columns else monitor["grid_import_kw"] * 0.0
    peak_slack_max_kw = float(peak_slack.max()) if len(monitor) else 0.0
    peak_slack_step_count = int((peak_slack > 1e-7).sum()) if len(monitor) else 0
    tes_discharge_during_peak = float((monitor.loc[peak_slack > 1e-7, "q_dis_tes_kw_th"] * dt_hours).sum()) if len(monitor) else 0.0

    pv_surplus_mask = monitor["pv_spill_kw"] > 1e-7
    tes_charge_during_pv_surplus = float((monitor.loc[pv_surplus_mask, "q_ch_tes_kw_th"] * dt_hours).sum()) if len(monitor) else 0.0
    soc_headroom_before_pv_hours = float(((monitor["soc"] < soc_planning_max - 1e-7) & pv_surplus_mask).sum() * dt_hours) if len(monitor) else 0.0
    time_in_each_mode = {
        str(int(mode)): float((monitor["mode_index"] == mode).sum() * dt_hours)
        for mode in sorted(monitor["mode_index"].dropna().unique())
    } if "mode_index" in monitor.columns else {}
    modes = [int(v) for v in monitor["mode_index"].tolist()] if "mode_index" in monitor.columns else []
    mode_switch_count = sum(1 for prev, cur in zip(modes, modes[1:]) if prev != cur)
    return EpisodeSummary(
        scenario_id=scenario_id,
        controller_type=controller_type,
        closed_loop_steps=int(len(monitor)),
        dt_hours=float(dt_hours),
        total_cost=cost,
        energy_cost=energy_cost,
        demand_charge_cost=demand_charge_cost,
        cold_station_proxy_total_cost=cold_station_proxy_total_cost,
        cold_station_proxy_energy_cost=cold_station_proxy_energy_cost,
        cold_station_proxy_grid_import_kwh=cold_station_proxy_grid_import_kwh,
        cold_station_proxy_pv_spill_kwh=cold_station_proxy_pv_spill_kwh,
        grid_import_kwh=grid_import_kwh,
        peak_grid_kw=peak_grid_kw,
        peak_slack_max_kw=peak_slack_max_kw,
        peak_slack_step_count=peak_slack_step_count,
        pv_actual_kwh=pv_actual_kwh,
        pv_used_kwh=pv_used_kwh,
        pv_spill_kwh=pv_spill_kwh,
        pv_spill_reduction_vs_no_tes=None,
        tes_charge_during_pv_surplus_kwh_th=tes_charge_during_pv_surplus,
        soc_headroom_before_pv_hours=soc_headroom_before_pv_hours,
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
        initial_soc=initial_soc,
        final_soc_after_last_update=final_soc_after_last_update,
        soc_delta=soc_delta,
        soc_inventory_delta_kwh_th=soc_inventory_delta_kwh_th,
        tes_charge_kwh_th=tes_charge_kwh_th,
        tes_discharge_kwh_th=tes_discharge_kwh_th,
        tes_equivalent_cycles=float(tes_discharge_kwh_th / max(1e-9, tes_capacity_kwh_th)),
        tes_charge_weighted_avg_price=charge_price,
        tes_discharge_weighted_avg_price=discharge_price,
        tes_arbitrage_price_spread=arbitrage_spread,
        charge_steps=int(charge_mask.sum()),
        discharge_steps=int(discharge_mask.sum()),
        idle_steps=int(idle_mask.sum()),
        charge_discharge_switch_count=charge_discharge_switch_count,
        first_discharge_step=first_discharge_step,
        first_discharge_timestamp=first_discharge_timestamp,
        avg_chiller_plr=avg_chiller_plr,
        avg_mode_specific_plr=avg_mode_specific_plr,
        weighted_avg_chiller_cop=weighted_avg_chiller_cop,
        time_in_high_plr_region=time_in_high_plr_region,
        low_plr_hours=low_plr_hours,
        high_plr_hours=high_plr_hours,
        time_in_each_mode=time_in_each_mode,
        mode_switch_count=mode_switch_count,
        max_signed_du=max_signed_du,
        signed_valve_violation_count=signed_violation_count,
        physical_consistency_violation_count=physical_count,
        max_chiller_supply_deficit_kw_th=max_supply_deficit,
        max_signed_valve_du=max_signed_du,
        tes_discharge_during_peak_cap_violation_kwh_th=tes_discharge_during_peak,
        solve_time_avg_s=float(solver_log["solve_time_s"].mean()),
        solve_time_p95_s=float(solver_log["solve_time_s"].quantile(0.95)),
        optimal_rate=_rate(status_values, {"optimal", "baseline"}),
        feasible_rate=_rate(status_values, {"optimal", "time_limit", "baseline", "fallback"}),
        fallback_count=int(monitor["fallback_used"].astype(bool).sum()),
        has_nan=has_nan,
    )


def _weighted_average(values: pd.Series, weights: pd.Series) -> float | None:
    total_weight = float(weights.sum())
    if total_weight <= 1e-9:
        return None
    return float((values * weights).sum() / total_weight)


def _charge_discharge_switch_count(states: list[str]) -> int:
    compact = [state for state in states if state in {"charge", "discharge"}]
    return sum(1 for prev, cur in zip(compact, compact[1:]) if prev != cur)


def _rate(values: Iterable[str], accepted: set[str]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(1 for value in values if value in accepted) / len(values)
