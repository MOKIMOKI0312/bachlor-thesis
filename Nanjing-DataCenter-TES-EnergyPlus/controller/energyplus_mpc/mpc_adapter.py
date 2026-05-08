"""Adapter between EnergyPlus observations and the hardened Kim-lite MILP."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from mpc_v2.kim_lite.config import KimLiteConfig, ModeConfig, ObjectiveConfig, TESConfig
from mpc_v2.kim_lite.model import KimLiteInputs, solve_paper_like_mpc

from .common import read_yaml, tes_set_from_q_tes_net


def build_kim_config(params: dict[str, Any], initial_soc: float, horizon_steps: int = 8) -> KimLiteConfig:
    tes = params["tes"]
    plant = params.get("plant_proxy", {})
    mode_specs = plant.get("modes") or [
        {"q_min_kw_th": 0.0, "q_max_kw_th": 8000.0, "a_kw_per_kwth": 0.126, "b_kw": 90.0, "c_kw_per_c": 0.0}
    ]
    q_abs = float(tes.get("q_abs_max_kw_th_proxy", 4500.0))
    q_ch_max = float(tes.get("q_ch_max_kw_th_proxy", q_abs))
    q_dis_max = float(tes.get("q_dis_max_kw_th_proxy", q_abs))
    return KimLiteConfig(
        dt_hours=float(params["energyplus"].get("dt_hours", 0.25)),
        horizon_steps=int(horizon_steps),
        default_steps=int(horizon_steps),
        start_timestamp="2024-01-01 00:00:00",
        pv_csv="",
        price_csv="",
        output_root="",
        q_load_kw_th=float(plant.get("q_load_kw_th", 2160.0)),
        q_load_daily_amp_frac=0.0,
        p_nonplant_kw=float(plant.get("p_nonplant_kw", 18000.0)),
        pv_scale=1.0,
        wet_bulb_base_c=float(plant.get("wet_bulb_base_c", 25.0)),
        wet_bulb_amp_c=float(plant.get("wet_bulb_amp_c", 4.0)),
        tes=TESConfig(
            capacity_kwh_th=float(tes.get("capacity_kwh_th_proxy", 18000.0)),
            q_ch_max_kw_th=q_ch_max,
            q_dis_max_kw_th=q_dis_max,
            initial_soc=float(np.clip(initial_soc, tes.get("soc_min", 0.15), tes.get("soc_max", 0.85))),
            soc_min=float(tes.get("soc_min", 0.15)),
            soc_max=float(tes.get("soc_max", 0.85)),
            soc_target=float(tes.get("soc_target", 0.50)),
            loss_per_h=0.002,
        ),
        modes=tuple(ModeConfig(**mode) for mode in mode_specs),
        objective=ObjectiveConfig(w_peak=0.0, w_soc=100000.0, w_terminal=80000.0, w_spill=0.001, w_peak_slack=100000.0),
        alpha_float=0.8,
        signed_du_max=0.25,
        solver_time_limit_s=5.0,
    )


def derive_measured_params(
    default_params: dict[str, Any],
    prediction_model_path: str | Path,
    samples_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build EnergyPlus-MPC params from the accepted sampling-fit model."""

    model_doc = read_yaml(prediction_model_path)
    if not bool(model_doc.get("adoption_ready")):
        reasons = model_doc.get("failure_reasons", [])
        raise ValueError(f"measured prediction model is not adoption_ready: {reasons}")
    params = deepcopy(default_params)
    chiller = model_doc["models"]["chiller_power"]
    coeffs = chiller.get("coefficients", {})
    default_chiller_t_set = float(params.get("schedules", {}).get("Chiller_T_Set", 0.0))
    measured_mode = {
        "q_min_kw_th": 0.0,
        "q_max_kw_th": float(params["plant_proxy"]["modes"][0]["q_max_kw_th"]),
        "a_kw_per_kwth": max(0.0, float(coeffs.get("chiller_cooling_kw", 0.0))),
        "b_kw": max(
            0.0,
            float(chiller.get("intercept", 0.0)) + float(coeffs.get("chiller_t_set_written", 0.0)) * default_chiller_t_set,
        ),
        "c_kw_per_c": float(coeffs.get("outdoor_wetbulb_c", 0.0)),
    }
    params["plant_proxy"]["modes"] = [measured_mode]
    soc = model_doc["models"].get("soc", {})
    params["tes"]["capacity_kwh_th_proxy"] = float(soc.get("capacity_kwh_th", params["tes"]["capacity_kwh_th_proxy"]))
    params["tes"]["loss_per_h_proxy"] = max(0.0, float(soc.get("loss_per_h", 0.0)))
    if samples_path is not None:
        q_ch, q_dis = _measured_tes_power_limits(samples_path)
        if q_ch > 0.0:
            params["tes"]["q_ch_max_kw_th_proxy"] = q_ch
        if q_dis > 0.0:
            params["tes"]["q_dis_max_kw_th_proxy"] = q_dis
        if q_ch > 0.0 or q_dis > 0.0:
            params["tes"]["q_abs_max_kw_th_proxy"] = max(q_ch, q_dis)
    params.setdefault("source", {})
    params["source"]["prediction_model_path"] = str(prediction_model_path)
    params["source"]["model_source"] = "measured_sampling"
    params["source"]["samples_path"] = str(samples_path) if samples_path is not None else ""
    return params


def _measured_tes_power_limits(samples_path: str | Path) -> tuple[float, float]:
    usecols = ["tes_set_written", "tes_use_side_kw", "tes_source_side_kw"]
    samples = pd.read_csv(samples_path, usecols=usecols)
    charge = samples.loc[samples["tes_set_written"] < -0.01, "tes_source_side_kw"].abs()
    discharge = samples.loc[samples["tes_set_written"] > 0.01, "tes_use_side_kw"].abs()
    q_ch = float(charge.quantile(0.95)) if not charge.empty else 0.0
    q_dis = float(discharge.quantile(0.95)) if not discharge.empty else 0.0
    return q_ch, q_dis


def solve_energyplus_mpc_action(
    params: dict[str, Any],
    forecast: dict[str, Any],
    current_soc: float,
    mode_integrality: str = "relaxed",
) -> dict[str, float | str]:
    cfg = build_kim_config(params, current_soc, len(forecast["timestamps"]))
    inputs = KimLiteInputs(
        timestamps=list(forecast["timestamps"]),
        q_load_kw_th=np.asarray(forecast["q_load_kw_th"], dtype=float),
        p_nonplant_kw=np.asarray(forecast["p_nonplant_kw"], dtype=float),
        p_pv_kw=np.asarray(forecast["p_pv_kw"], dtype=float),
        t_wb_c=np.asarray(forecast["t_wb_c"], dtype=float),
        price_cny_per_kwh=np.asarray(forecast["price_per_kwh"], dtype=float),
        cp_flag=np.zeros(len(forecast["timestamps"]), dtype=int),
    )
    solution = solve_paper_like_mpc(cfg, inputs, tes_enabled=True, mode_integrality=mode_integrality)
    q_net = float(solution.q_tes_net_kw_th[0])
    return {
        "tes_set": tes_set_from_q_tes_net(q_net, cfg.tes.q_abs_max_kw_th),
        "q_tes_net_kw_th": q_net,
        "q_chiller_kw_th_pred": float(solution.q_chiller_kw_th[0]),
        "solver_status": solution.status,
        "solver_time_s": float(solution.solver_time_s),
    }


def rbc_action(price: float, low_price: float, high_price: float, soc: float) -> float:
    if price <= low_price and soc < 0.80:
        return -0.5
    if price >= high_price and soc > 0.20:
        return 0.5
    return 0.0
