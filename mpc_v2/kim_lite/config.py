"""Configuration objects for the Kim-lite paper-like MPC path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ModeConfig:
    q_min_kw_th: float
    q_max_kw_th: float
    a_kw_per_kwth: float
    b_kw: float
    c_kw_per_c: float = 0.0


@dataclass(frozen=True)
class TESConfig:
    capacity_kwh_th: float
    q_ch_max_kw_th: float
    q_dis_max_kw_th: float
    initial_soc: float
    soc_min: float
    soc_max: float
    soc_target: float
    loss_per_h: float

    @property
    def q_abs_max_kw_th(self) -> float:
        return max(self.q_ch_max_kw_th, self.q_dis_max_kw_th)


@dataclass(frozen=True)
class ObjectiveConfig:
    w_peak: float
    w_soc: float
    w_terminal: float
    w_spill: float
    w_peak_slack: float


@dataclass(frozen=True)
class KimLiteConfig:
    dt_hours: float
    horizon_steps: int
    default_steps: int
    start_timestamp: str
    pv_csv: str
    price_csv: str
    output_root: str
    q_load_kw_th: float
    q_load_daily_amp_frac: float
    p_nonplant_kw: float
    pv_scale: float
    wet_bulb_base_c: float
    wet_bulb_amp_c: float
    tes: TESConfig
    modes: tuple[ModeConfig, ...]
    objective: ObjectiveConfig
    alpha_float: float
    signed_du_max: float
    solver_time_limit_s: float


def load_config(path: str | Path = "mpc_v2/config/kim_lite_base.yaml") -> KimLiteConfig:
    """Load and validate Kim-lite YAML config."""

    with Path(path).open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"Kim-lite config must be a mapping: {path}")
    time = raw["time"]
    paths = raw["paths"]
    inputs = raw["inputs"]
    tes = raw["tes"]
    objective = raw["objective"]
    modes = tuple(ModeConfig(**mode) for mode in raw["plant"]["modes"])
    cfg = KimLiteConfig(
        dt_hours=float(time["dt_hours"]),
        horizon_steps=int(time["horizon_steps"]),
        default_steps=int(time["default_steps"]),
        start_timestamp=str(inputs["start_timestamp"]),
        pv_csv=str(paths["pv_csv"]),
        price_csv=str(paths["price_csv"]),
        output_root=str(paths["output_root"]),
        q_load_kw_th=float(inputs["q_load_kw_th"]),
        q_load_daily_amp_frac=float(inputs.get("q_load_daily_amp_frac", 0.0)),
        p_nonplant_kw=float(inputs["p_nonplant_kw"]),
        pv_scale=float(inputs.get("pv_scale", 1.0)),
        wet_bulb_base_c=float(inputs.get("wet_bulb_base_c", 25.0)),
        wet_bulb_amp_c=float(inputs.get("wet_bulb_amp_c", 4.0)),
        tes=TESConfig(**{k: float(v) for k, v in tes.items()}),
        modes=modes,
        objective=ObjectiveConfig(**{k: float(v) for k, v in objective.items()}),
        alpha_float=float(raw.get("tariff", {}).get("alpha_float", 0.8)),
        signed_du_max=float(raw.get("signed_valve", {}).get("du_max_per_step", 1.0)),
        solver_time_limit_s=float(raw.get("solver", {}).get("time_limit_s", 20.0)),
    )
    validate_config(cfg)
    return cfg


def validate_config(cfg: KimLiteConfig) -> None:
    if abs(cfg.dt_hours - 0.25) > 1e-9:
        raise ValueError("Kim-lite v1 supports 15-minute steps only")
    if cfg.horizon_steps <= 0 or cfg.default_steps <= 0:
        raise ValueError("horizon and default steps must be positive")
    if not cfg.modes:
        raise ValueError("at least one plant mode is required")
    for mode in cfg.modes:
        if mode.q_min_kw_th < 0 or mode.q_max_kw_th <= 0 or mode.q_min_kw_th > mode.q_max_kw_th:
            raise ValueError(f"invalid mode bounds: {mode}")
    if not 0.0 <= cfg.tes.soc_min <= cfg.tes.initial_soc <= cfg.tes.soc_max <= 1.0:
        raise ValueError("TES SOC bounds are inconsistent")
    if not 0.0 <= cfg.tes.soc_target <= 1.0:
        raise ValueError("TES target SOC must be in [0, 1]")
    if cfg.tes.capacity_kwh_th <= 0 or cfg.tes.q_abs_max_kw_th <= 0:
        raise ValueError("TES capacity and power limits must be positive")
    if not 0.0 <= cfg.alpha_float <= 1.0:
        raise ValueError("alpha_float must be in [0, 1]")


def load_yaml_mapping(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"YAML must contain a mapping: {path}")
    return data
