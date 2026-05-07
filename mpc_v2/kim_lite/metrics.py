"""Metrics and result serialization for Kim-lite runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from mpc_v2.kim_lite.config import KimLiteConfig
from mpc_v2.kim_lite.model import KimLiteInputs, KimLiteSolution


def build_monitor(controller: str, inputs: KimLiteInputs, solution: KimLiteSolution, cfg: KimLiteConfig) -> pd.DataFrame:
    """Build one monitor row per timestep."""

    q_abs = cfg.tes.q_abs_max_kw_th
    u_signed = solution.q_tes_net_kw_th / q_abs
    signed_du = np.zeros_like(u_signed)
    if len(signed_du) > 1:
        signed_du[1:] = np.diff(u_signed)
    return pd.DataFrame(
        {
            "timestamp": [ts.isoformat(sep=" ") for ts in inputs.timestamps],
            "step": np.arange(len(inputs.timestamps)),
            "controller": controller,
            "Q_load_kw_th": inputs.q_load_kw_th,
            "P_nonplant_kw": inputs.p_nonplant_kw,
            "P_pv_kw": inputs.p_pv_kw,
            "T_wb_C": inputs.t_wb_c,
            "price_cny_per_kwh": inputs.price_cny_per_kwh,
            "cp_flag": inputs.cp_flag,
            "Q_chiller_kw_th": solution.q_chiller_kw_th,
            "Q_tes_net_kw_th": solution.q_tes_net_kw_th,
            "P_plant_kw": solution.p_plant_kw,
            "P_grid_pos_kw": solution.p_grid_pos_kw,
            "P_spill_kw": solution.p_spill_kw,
            "d_peak_kw": solution.d_peak_kw,
            "peak_slack_kw": solution.peak_slack_kw,
            "soc": solution.soc[:-1],
            "soc_next": solution.soc[1:],
            "u_signed": u_signed,
            "signed_du": signed_du,
            "mode_index": solution.mode_index,
            "solver_status": solution.status,
            "solver_time_s": solution.solver_time_s,
        }
    )


def summarize_monitor(monitor: pd.DataFrame, cfg: KimLiteConfig, case_id: str, controller: str) -> dict[str, Any]:
    """Return stable paper-like metrics."""

    dt = cfg.dt_hours
    q_pos = monitor["Q_tes_net_kw_th"].clip(lower=0.0)
    q_neg = (-monitor["Q_tes_net_kw_th"]).clip(lower=0.0)
    charge_kwh = float((q_pos * dt).sum())
    discharge_kwh = float((q_neg * dt).sum())
    summary = {
        "case_id": case_id,
        "controller": controller,
        "steps": int(len(monitor)),
        "cost_total": float((monitor["P_grid_pos_kw"] * monitor["price_cny_per_kwh"] * dt).sum()),
        "whole_facility_energy_cost": float((monitor["P_grid_pos_kw"] * monitor["price_cny_per_kwh"] * dt).sum()),
        "plant_energy_cost": float((monitor["P_plant_kw"] * monitor["price_cny_per_kwh"] * dt).sum()),
        "grid_import_kwh": float((monitor["P_grid_pos_kw"] * dt).sum()),
        "plant_energy_kwh": float((monitor["P_plant_kw"] * dt).sum()),
        "pv_used_kwh": float(((monitor["P_pv_kw"] - monitor["P_spill_kw"]).clip(lower=0.0) * dt).sum()),
        "pv_spill_kwh": float((monitor["P_spill_kw"] * dt).sum()),
        "peak_grid_kw": float(monitor["P_grid_pos_kw"].max()),
        "peak_slack_max_kw": float(monitor["peak_slack_kw"].max()),
        "peak_slack_kwh": float((monitor["peak_slack_kw"] * dt).sum()),
        "soc_initial": float(monitor["soc"].iloc[0]),
        "soc_final": float(monitor["soc_next"].iloc[-1]),
        "soc_delta": float(monitor["soc_next"].iloc[-1] - monitor["soc"].iloc[0]),
        "soc_min": float(min(monitor["soc"].min(), monitor["soc_next"].min())),
        "soc_max": float(max(monitor["soc"].max(), monitor["soc_next"].max())),
        "TES_charge_kwh_th": charge_kwh,
        "TES_discharge_kwh_th": discharge_kwh,
        "TES_charge_weighted_avg_price": _weighted_price(monitor, q_pos, dt),
        "TES_discharge_weighted_avg_price": _weighted_price(monitor, q_neg, dt),
        "TES_arbitrage_spread": _weighted_price(monitor, q_neg, dt) - _weighted_price(monitor, q_pos, dt),
        "solver_time_avg_s": float(monitor["solver_time_s"].mean()),
        "solver_time_p95_s": float(monitor["solver_time_s"].quantile(0.95)),
        "solver_status": str(monitor["solver_status"].iloc[0]),
        "max_signed_du": float(monitor["signed_du"].abs().max()),
        "signed_valve_violation_count": int((monitor["signed_du"].abs() > cfg.signed_du_max + 1e-8).sum()),
        "grid_balance_violation_count": int(
            (
                (
                    monitor["P_grid_pos_kw"]
                    - (monitor["P_nonplant_kw"] + monitor["P_plant_kw"] - monitor["P_pv_kw"]).clip(lower=0.0)
                ).abs()
                > 1e-5
            ).sum()
        ),
    }
    return summary


def write_case_outputs(
    run_dir: Path,
    monitor: pd.DataFrame,
    summary: dict[str, Any],
    cfg: KimLiteConfig,
    extra_config: dict[str, Any] | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    monitor.to_csv(run_dir / "monitor.csv", index=False)
    pd.DataFrame([summary]).to_csv(run_dir / "summary.csv", index=False)
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    effective = {
        "kim_lite_config": {
            "dt_hours": cfg.dt_hours,
            "horizon_steps": cfg.horizon_steps,
            "default_steps": cfg.default_steps,
            "start_timestamp": cfg.start_timestamp,
            "pv_csv": cfg.pv_csv,
            "price_csv": cfg.price_csv,
            "output_root": cfg.output_root,
            "q_load_kw_th": cfg.q_load_kw_th,
            "q_load_daily_amp_frac": cfg.q_load_daily_amp_frac,
            "p_nonplant_kw": cfg.p_nonplant_kw,
            "pv_scale": cfg.pv_scale,
            "wet_bulb_base_c": cfg.wet_bulb_base_c,
            "wet_bulb_amp_c": cfg.wet_bulb_amp_c,
            "alpha_float": cfg.alpha_float,
            "signed_du_max": cfg.signed_du_max,
            "solver_time_limit_s": cfg.solver_time_limit_s,
            "tes": cfg.tes.__dict__,
            "objective": cfg.objective.__dict__,
            "modes": [m.__dict__ for m in cfg.modes],
        },
        "extra": extra_config or {},
    }
    with (run_dir / "config_effective.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(effective, fh, sort_keys=False, allow_unicode=True)


def attribution_table(summary: pd.DataFrame) -> pd.DataFrame:
    costs = dict(zip(summary["controller"], summary["cost_total"]))
    rows = [
        {
            "metric": "MPC_value",
            "formula": "cost(direct_no_tes) - cost(mpc_no_tes)",
            "value": costs.get("direct_no_tes", np.nan) - costs.get("mpc_no_tes", np.nan),
        },
        {
            "metric": "TES_value",
            "formula": "cost(mpc_no_tes) - cost(paper_like_mpc_tes)",
            "value": costs.get("mpc_no_tes", np.nan) - costs.get("paper_like_mpc_tes", np.nan),
        },
        {
            "metric": "RBC_gap",
            "formula": "cost(storage_priority_tes) - cost(paper_like_mpc_tes)",
            "value": costs.get("storage_priority_tes", np.nan) - costs.get("paper_like_mpc_tes", np.nan),
        },
    ]
    return pd.DataFrame(rows)


def _weighted_price(monitor: pd.DataFrame, weights: pd.Series, dt: float) -> float:
    w = weights.astype(float) * dt
    total = float(w.sum())
    if total <= 1e-9:
        return 0.0
    return float((monitor["price_cny_per_kwh"] * w).sum() / total)
