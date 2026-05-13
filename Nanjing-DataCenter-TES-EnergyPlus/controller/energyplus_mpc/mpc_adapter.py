"""Adapter between EnergyPlus observations and the hardened Kim-lite MILP."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

import numpy as np

from mpc_v2.kim_lite.config import KimLiteConfig, ModeConfig, ObjectiveConfig, TESConfig
from mpc_v2.kim_lite.model import KimLiteInputs, solve_paper_like_mpc

from .common import tes_set_from_q_tes_net


def build_kim_config(params: dict[str, Any], initial_soc: float, horizon_steps: int = 8) -> KimLiteConfig:
    tes = params["tes"]
    plant = params.get("plant_proxy", {})
    mode_specs = plant.get("modes") or [
        {"q_min_kw_th": 0.0, "q_max_kw_th": 8000.0, "a_kw_per_kwth": 0.126, "b_kw": 90.0, "c_kw_per_c": 0.0}
    ]
    q_abs = float(tes.get("q_abs_max_kw_th_proxy", 4500.0))
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
            q_ch_max_kw_th=q_abs,
            q_dis_max_kw_th=q_abs,
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


def solve_energyplus_mpc_action(
    params: dict[str, Any],
    forecast: dict[str, Any],
    current_soc: float,
    mode_integrality: str = "relaxed",
) -> dict[str, float | str]:
    cfg = build_kim_config(params, current_soc, len(forecast["timestamps"]))
    tes_enabled = cfg.tes.capacity_kwh_th > 0.0 and cfg.tes.q_abs_max_kw_th > 0.0
    if not tes_enabled:
        return {
            "tes_set": 0.0,
            "q_tes_net_kw_th_pred": 0.0,
            "q_chiller_kw_th_pred": float(np.asarray(forecast["q_load_kw_th"], dtype=float)[0]),
            "solver_status": "no_tes_disabled",
            "solver_time_s": 0.0,
        }
    inputs = KimLiteInputs(
        timestamps=list(forecast["timestamps"]),
        q_load_kw_th=np.asarray(forecast["q_load_kw_th"], dtype=float),
        p_nonplant_kw=np.asarray(forecast["p_nonplant_kw"], dtype=float),
        p_pv_kw=np.asarray(forecast["p_pv_kw"], dtype=float),
        t_wb_c=np.asarray(forecast["t_wb_c"], dtype=float),
        price_cny_per_kwh=np.asarray(forecast["price_per_kwh"], dtype=float),
        cp_flag=np.zeros(len(forecast["timestamps"]), dtype=int),
    )
    solution = solve_paper_like_mpc(cfg, inputs, tes_enabled=tes_enabled, mode_integrality=mode_integrality)
    q_net = float(solution.q_tes_net_kw_th[0])
    return {
        "tes_set": tes_set_from_q_tes_net(q_net, cfg.tes.q_abs_max_kw_th),
        "q_tes_net_kw_th_pred": q_net,
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
