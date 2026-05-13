"""TES capacity scaling helpers for Phase 3 scenarios."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def build_tes_config(base_cfg: dict[str, Any], capacity_mwh_th: float, q_abs_max_kw_th: float | None = None) -> dict:
    """Return a TES config for the requested thermal capacity.

    The Phase 3 main experiment keeps the TES charge/discharge power fixed while
    varying energy capacity. A zero-capacity request becomes an explicit no-TES
    case with zero power and constant SOC.
    """

    capacity = float(capacity_mwh_th)
    if capacity < 0:
        raise ValueError("capacity_mwh_th must be non-negative")

    cfg = deepcopy(base_cfg)
    cfg["capacity_mwh_th"] = capacity
    cfg["capacity_kwh_th"] = capacity * 1000.0

    if q_abs_max_kw_th is None:
        q_abs_max_kw_th = _default_q_abs_max(cfg)
    q_abs = float(q_abs_max_kw_th)
    if q_abs < 0:
        raise ValueError("q_abs_max_kw_th must be non-negative")

    if capacity == 0:
        soc = float(cfg.get("initial_soc", cfg.get("soc_initial", cfg.get("soc_target", 0.5))))
        cfg.update(
            {
                "enabled": False,
                "q_tes_abs_max_kw_th": 0.0,
                "q_ch_max_kw_th": 0.0,
                "q_dis_max_kw_th": 0.0,
                "initial_soc": soc,
                "soc_initial": soc,
                "soc_target": soc,
                "soc_physical_min": soc,
                "soc_physical_max": soc,
                "soc_planning_min": soc,
                "soc_planning_max": soc,
                "soc_constant": True,
                "q_tes_net_forced_zero": True,
            }
        )
        return cfg

    cfg.update(
        {
            "enabled": True,
            "q_tes_abs_max_kw_th": q_abs,
            "q_ch_max_kw_th": q_abs,
            "q_dis_max_kw_th": q_abs,
            "soc_constant": False,
            "q_tes_net_forced_zero": False,
        }
    )
    return cfg


def _default_q_abs_max(cfg: dict[str, Any]) -> float:
    for key in ("q_tes_abs_max_kw_th", "q_ch_max_kw_th", "q_dis_max_kw_th"):
        if key in cfg:
            return float(cfg[key])
    return 0.0
