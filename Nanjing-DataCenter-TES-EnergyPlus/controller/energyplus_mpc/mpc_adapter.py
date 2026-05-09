"""Adapter between EnergyPlus observations and the hardened Kim-lite MILP."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from mpc_v2.kim_lite.config import CriticalPeakConfig, KimLiteConfig, ModeConfig, ObjectiveConfig, TESConfig
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
        objective=ObjectiveConfig(w_peak=0.0, w_terminal=80000.0, w_spill=0.001, w_peak_slack=100000.0),
        alpha_float=0.8,
        critical_peak=CriticalPeakConfig(months=(7, 8), windows=((11.0, 13.0), (16.0, 17.0))),
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
    params["plant_proxy"]["chiller_t_set_kw_per_norm"] = float(coeffs.get("chiller_t_set_written", 0.0))
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
    previous_u_signed: float = 0.0,
    observation: dict[str, Any] | None = None,
    io_coupled: bool = False,
) -> dict[str, float | str | bool]:
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
    solution = solve_paper_like_mpc(
        cfg,
        inputs,
        tes_enabled=True,
        enforce_signed_ramp=True,
        mode_integrality=mode_integrality,
        previous_u_signed=previous_u_signed,
    )
    q_net = float(solution.q_tes_net_kw_th[0])
    tes_set = tes_set_from_q_tes_net(q_net, cfg.tes.q_abs_max_kw_th)
    mode_idx = int(solution.mode_index[0]) if len(solution.mode_index) else -1
    plant_power = _predicted_plant_power_kw(cfg, mode_idx, float(solution.q_chiller_kw_th[0]), float(inputs.t_wb_c[0]))
    out: dict[str, float | str | bool] = {
        "tes_set": tes_set,
        "mpc_predicted_tes_set": tes_set,
        "q_tes_net_kw_th": q_net,
        "mpc_predicted_q_tes_net_kw_th": q_net,
        "q_chiller_kw_th_pred": float(solution.q_chiller_kw_th[0]),
        "mpc_predicted_q_chiller_kw_th": float(solution.q_chiller_kw_th[0]),
        "mpc_predicted_chiller_power_kw": plant_power,
        "solver_status": solution.status,
        "solver_time_s": float(solution.solver_time_s),
        "safety_override": False,
        "safety_override_reason": "",
        "temp_guard_charge_block": False,
    }
    if io_coupled:
        out.update(_choose_io_coupled_outputs(params, forecast, observation or {}, tes_set, q_net, plant_power))
    return out


def _predicted_plant_power_kw(cfg: KimLiteConfig, mode_idx: int, q_chiller_kw_th: float, wetbulb_c: float) -> float:
    if mode_idx < 0 or q_chiller_kw_th <= 1e-9:
        return 0.0
    mode = cfg.modes[mode_idx]
    return float(mode.a_kw_per_kwth * q_chiller_kw_th + mode.b_kw + mode.c_kw_per_c * wetbulb_c)


def _choose_io_coupled_outputs(
    params: dict[str, Any],
    forecast: dict[str, Any],
    observation: dict[str, Any],
    tes_set: float,
    q_net: float,
    plant_power_kw: float,
) -> dict[str, float | str | bool]:
    zone_temp = float(observation.get("zone_temp_c", np.nan))
    levels = tuple(float(v) for v in params.get("io_coupling", {}).get("chiller_t_set_levels", [0.0, 0.5, 1.0]))
    if not levels:
        levels = (0.0,)
    warm_threshold = float(params.get("io_coupling", {}).get("temp_guard_charge_block_c", 26.5))
    hot_threshold = float(params.get("io_coupling", {}).get("temp_guard_hard_c", 27.0))
    chiller_t = _choose_chiller_t_level(params, forecast, zone_temp, q_net, levels)
    override = False
    reasons: list[str] = []
    charge_block = False
    if np.isfinite(zone_temp) and zone_temp >= warm_threshold and tes_set < 0.0:
        tes_set = 0.0
        override = True
        charge_block = True
        reasons.append("temp_guard_charge_block")
    if np.isfinite(zone_temp) and zone_temp >= hot_threshold:
        chiller_t = min(levels)
        if tes_set < 0.0:
            tes_set = 0.0
        override = True
        reasons.append("temp_guard_hard_chiller_low")
    chiller_kw_per_norm = float(params.get("plant_proxy", {}).get("chiller_t_set_kw_per_norm", 0.0))
    return {
        "tes_set": float(np.clip(tes_set, -1.0, 1.0)),
        "chiller_t_set": float(np.clip(chiller_t, 0.0, 1.0)),
        "mpc_predicted_chiller_t_set": float(np.clip(chiller_t, 0.0, 1.0)),
        "mpc_predicted_chiller_power_kw": float(plant_power_kw + chiller_kw_per_norm * chiller_t),
        "safety_override": bool(override),
        "safety_override_reason": ";".join(dict.fromkeys(reasons)),
        "temp_guard_charge_block": bool(charge_block),
    }


def _choose_chiller_t_level(
    params: dict[str, Any],
    forecast: dict[str, Any],
    zone_temp_c: float,
    q_net: float,
    levels: tuple[float, ...],
) -> float:
    if np.isfinite(zone_temp_c) and zone_temp_c >= float(params.get("io_coupling", {}).get("temp_guard_charge_block_c", 26.5)):
        return min(levels)
    prices = np.asarray(forecast.get("price_per_kwh", [0.0]), dtype=float)
    price = float(prices[0]) if len(prices) else 0.0
    high_price = float(np.quantile(prices, 0.70)) if len(prices) else price
    if np.isfinite(zone_temp_c) and zone_temp_c <= 25.0 and q_net <= 0.0 and price >= high_price:
        return max(levels)
    if np.isfinite(zone_temp_c) and zone_temp_c <= 25.5 and q_net <= 0.0:
        return sorted(levels)[len(levels) // 2]
    return min(levels)


def rbc_action(price: float, low_price: float, high_price: float, soc: float) -> float:
    if price <= low_price and soc < 0.80:
        return -0.5
    if price >= high_price and soc > 0.20:
        return 0.5
    return 0.0
