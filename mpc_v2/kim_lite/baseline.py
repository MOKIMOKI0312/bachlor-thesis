"""Kim-lite baseline controllers."""

from __future__ import annotations

import time

import numpy as np

from mpc_v2.kim_lite.config import KimLiteConfig
from mpc_v2.kim_lite.model import KimLiteInputs, KimLiteSolution, plant_dispatch


def direct_no_tes(cfg: KimLiteConfig, inputs: KimLiteInputs) -> KimLiteSolution:
    """Direct-load no-storage baseline."""

    return _fixed_dispatch_solution(cfg, inputs, inputs.q_load_kw_th, "direct_no_tes")


def storage_priority(cfg: KimLiteConfig, inputs: KimLiteInputs) -> KimLiteSolution:
    """Charge TES in low-price periods and discharge in high-price periods."""

    start = time.perf_counter()
    low = float(np.quantile(inputs.price_cny_per_kwh, 0.30))
    high = float(np.quantile(inputs.price_cny_per_kwh, 0.70))
    q_chiller = np.zeros_like(inputs.q_load_kw_th)
    soc = [cfg.tes.initial_soc]
    for k, price in enumerate(inputs.price_cny_per_kwh):
        desired = float(inputs.q_load_kw_th[k])
        if price <= low and soc[-1] < cfg.tes.soc_max - 1e-8:
            room = (cfg.tes.soc_max - soc[-1]) * cfg.tes.capacity_kwh_th / cfg.dt_hours
            desired += min(cfg.tes.q_ch_max_kw_th, room)
        elif price >= high and soc[-1] > cfg.tes.soc_min + 1e-8:
            available = (soc[-1] - cfg.tes.soc_min) * cfg.tes.capacity_kwh_th / cfg.dt_hours
            desired -= min(cfg.tes.q_dis_max_kw_th, available, desired)
        q_actual, _, _ = plant_dispatch(desired, cfg, inputs.t_wb_c[k])
        q_net = float(q_actual - inputs.q_load_kw_th[k])
        q_net = max(-cfg.tes.q_dis_max_kw_th, min(cfg.tes.q_ch_max_kw_th, q_net))
        next_soc = (1.0 - cfg.tes.loss_per_h * cfg.dt_hours) * soc[-1] + q_net * cfg.dt_hours / cfg.tes.capacity_kwh_th
        if next_soc > cfg.tes.soc_max:
            q_net -= (next_soc - cfg.tes.soc_max) * cfg.tes.capacity_kwh_th / cfg.dt_hours
        if next_soc < cfg.tes.soc_min:
            q_net += (cfg.tes.soc_min - next_soc) * cfg.tes.capacity_kwh_th / cfg.dt_hours
        q_chiller[k] = inputs.q_load_kw_th[k] + q_net
        soc.append((1.0 - cfg.tes.loss_per_h * cfg.dt_hours) * soc[-1] + q_net * cfg.dt_hours / cfg.tes.capacity_kwh_th)
    return _fixed_dispatch_solution(cfg, inputs, q_chiller, "storage_priority", np.asarray(soc), time.perf_counter() - start)


def _fixed_dispatch_solution(
    cfg: KimLiteConfig,
    inputs: KimLiteInputs,
    requested_q_chiller: np.ndarray,
    status: str,
    soc_override: np.ndarray | None = None,
    solver_time_s: float = 0.0,
) -> KimLiteSolution:
    start = time.perf_counter()
    n = len(inputs.timestamps)
    q_chiller = np.zeros(n)
    p_plant = np.zeros(n)
    mode_index = np.full(n, -1, dtype=int)
    for k in range(n):
        q, p, mode = plant_dispatch(float(requested_q_chiller[k]), cfg, float(inputs.t_wb_c[k]))
        q_chiller[k] = q
        p_plant[k] = p
        mode_index[k] = mode
    q_net = q_chiller - inputs.q_load_kw_th
    if soc_override is None:
        soc_override = np.full(n + 1, cfg.tes.initial_soc, dtype=float)
    grid = np.maximum(0.0, inputs.p_nonplant_kw + p_plant - inputs.p_pv_kw)
    spill = np.maximum(0.0, inputs.p_pv_kw - inputs.p_nonplant_kw - p_plant)
    objective = float(np.sum(grid * inputs.price_cny_per_kwh * cfg.dt_hours))
    return KimLiteSolution(
        status=status,
        objective_value=objective,
        solver_time_s=solver_time_s or (time.perf_counter() - start),
        q_chiller_kw_th=q_chiller,
        q_tes_net_kw_th=q_net,
        soc=soc_override,
        p_plant_kw=p_plant,
        p_grid_pos_kw=grid,
        p_spill_kw=spill,
        d_peak_kw=float(grid.max()) if len(grid) else 0.0,
        mode_index=mode_index,
        peak_slack_kw=np.zeros(n),
    )
