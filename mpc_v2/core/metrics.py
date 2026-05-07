"""Episode metrics for the rebuilt MPC v1 output contract."""

from __future__ import annotations

from typing import Any

import pandas as pd


def compute_episode_metrics(monitor: pd.DataFrame, cfg: dict[str, Any]) -> dict[str, Any]:
    """Compute stable summary fields consumed by downstream scripts."""

    dt = float(cfg["time"]["dt_hours"])
    tes = cfg["tes"]
    total_cost = float(monitor["step_cost"].sum())
    grid_kwh = float((monitor["grid_import_kw"] * dt).sum())
    plant_kwh = float((monitor["plant_power_kw"] * dt).sum())
    it_kwh = float((monitor["it_load_kw"] * dt).sum())
    pv_kwh = float((monitor["pv_actual_kw"] * dt).sum())
    spill_kwh = float((monitor["pv_spill_kw"] * dt).sum())
    charge_kwh = float((monitor["q_ch_tes_kw_th"] * dt).sum())
    discharge_kwh = float((monitor["q_dis_tes_kw_th"] * dt).sum())
    soc_values = monitor["soc"].astype(float)
    final_soc = float(monitor["soc_after_update"].iloc[-1]) if len(monitor) else float(tes["initial_soc"])
    soc_min = float(min(soc_values.min(), monitor["soc_after_update"].min()))
    soc_max = float(max(soc_values.max(), monitor["soc_after_update"].max()))
    soc_lo = float(tes["soc_physical_min"])
    soc_hi = float(tes["soc_physical_max"])
    charge_steps = int((monitor["q_ch_tes_kw_th"] > 1e-6).sum())
    discharge_steps = int((monitor["q_dis_tes_kw_th"] > 1e-6).sum())
    idle_steps = int(len(monitor) - charge_steps - discharge_steps)
    simultaneous_count = int(((monitor["q_ch_tes_kw_th"] > 1e-6) & (monitor["q_dis_tes_kw_th"] > 1e-6)).sum())
    chiller_deficit = (
        monitor["q_load_kw_th"] + monitor["q_ch_tes_kw_th"] - monitor["q_chiller_kw_th"]
    ).clip(lower=0.0)
    charge_price = _weighted_price(monitor, "q_ch_tes_kw_th", dt)
    discharge_price = _weighted_price(monitor, "q_dis_tes_kw_th", dt)
    return {
        "closed_loop_steps": int(len(monitor)),
        "controller_mode": str(monitor["controller_mode"].iloc[0]) if len(monitor) else "",
        "total_cost": total_cost,
        "energy_cost": total_cost,
        "grid_import_kwh": grid_kwh,
        "peak_grid_kw": float(monitor["grid_import_kw"].max()) if len(monitor) else 0.0,
        "pv_actual_kwh": pv_kwh,
        "pv_spill_kwh": spill_kwh,
        "pv_used_kwh": max(0.0, pv_kwh - spill_kwh),
        "facility_energy_kwh": grid_kwh + max(0.0, pv_kwh - spill_kwh),
        "cold_station_energy_kwh": plant_kwh,
        "it_energy_kwh": it_kwh,
        "pue_avg": (grid_kwh + max(0.0, pv_kwh - spill_kwh)) / max(it_kwh, 1e-9),
        "initial_soc": float(tes["initial_soc"]),
        "final_soc_after_last_update": final_soc,
        "soc_delta": final_soc - float(tes["initial_soc"]),
        "soc_inventory_delta_kwh_th": (final_soc - float(tes["initial_soc"])) * float(tes["capacity_kwh_th"]),
        "soc_min": soc_min,
        "soc_max": soc_max,
        "soc_violation_count": int(((monitor["soc_after_update"] < soc_lo - 1e-7) | (monitor["soc_after_update"] > soc_hi + 1e-7)).sum()),
        "tes_charge_kwh_th": charge_kwh,
        "tes_discharge_kwh_th": discharge_kwh,
        "tes_charge_weighted_avg_price": charge_price,
        "tes_discharge_weighted_avg_price": discharge_price,
        "tes_arbitrage_price_spread": discharge_price - charge_price,
        "charge_steps": charge_steps,
        "discharge_steps": discharge_steps,
        "idle_steps": idle_steps,
        "charge_discharge_switch_count": _switch_count(monitor),
        "simultaneous_charge_discharge_count": simultaneous_count,
        "physical_consistency_violation_count": int((chiller_deficit > 1e-6).sum() + simultaneous_count),
        "max_chiller_supply_deficit_kw_th": float(chiller_deficit.max()) if len(chiller_deficit) else 0.0,
        "optimal_rate": float((monitor["solver_status"] == "optimal").mean()) if len(monitor) else 0.0,
        "feasible_rate": float((monitor["fallback"] == 0).mean()) if len(monitor) else 0.0,
        "fallback_count": int(monitor["fallback"].sum()) if len(monitor) else 0,
        "unsupported_advanced_features": "true",
    }


def _weighted_price(monitor: pd.DataFrame, weight_col: str, dt: float) -> float:
    weights = monitor[weight_col].astype(float) * dt
    total = float(weights.sum())
    if total <= 1e-9:
        return 0.0
    return float((monitor["price_cny_per_kwh"].astype(float) * weights).sum() / total)


def _switch_count(monitor: pd.DataFrame) -> int:
    modes = []
    for _, row in monitor.iterrows():
        if row["q_ch_tes_kw_th"] > 1e-6:
            modes.append("charge")
        elif row["q_dis_tes_kw_th"] > 1e-6:
            modes.append("discharge")
        else:
            modes.append("idle")
    return sum(1 for left, right in zip(modes, modes[1:]) if left != right)
