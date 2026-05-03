"""M2 TES failure-mode validation entrypoint.

This script is intentionally evaluation-only.  It builds the same M2-F1
fixed-fan wrapper stack as tools/evaluate_m2.py, rejects checkpoints whose
action dimension does not match the requested TES action semantics, and keeps
all counterfactual action surgery local to this file.

Subcommands:
    paired-eval          Run/checkpoint-manifest the four requested designs.
    guard-probe          Summarize raw TES target vs actual valve behavior.
    counterfactual-eval  Isolate learned HVAC/TES contributions.
    summarize            Aggregate JSON/CSV validation metrics.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import numpy as np
import pandas as pd

from tools.m2_action_guard import M2_FIXED_FAN_VALUE, checkpoint_action_dim


DEFAULT_EPW = "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
# C1 fix: keep CSV defaults as ROOT-relative absolute strings so the script also
# works when invoked from outside the repo root. _normalize_data_paths() further
# protects against user-supplied relative paths.
DEFAULT_PRICE_CSV = str(ROOT / "Data/prices/Jiangsu_TOU_2025_hourly.csv")
DEFAULT_PV_CSV = str(ROOT / "Data/pv/CHN_Nanjing_PV_6MWp_hourly.csv")
M2_TIMESTEPS_PER_HOUR = 4
TES_TANK_M3 = 1400.0
TES_MAX_FLOW_KG_S = 389.0
TOU_SWITCH_RADIUS_STEPS = 1
TES_MECHANISM_FIELDS = [
    "charge_window_sign_rate",
    "low_price_discharge_fraction",
    "discharge_window_sign_rate",
    "delta_soc_prepeak",
    "delta_soc_peak",
    "raw_actual_divergence_switch_mean",
    "raw_actual_divergence_switch_p95",
    "raw_actual_divergence_switch_count",
    "sign_flip_delay_steps",
    "sign_flip_delay_steps_mean",
    "sign_flip_no_flip_fraction",
    "charge_window_step_count",
    "discharge_window_step_count",
    "prepeak_window_count",
    "peak_window_count",
    "low_price_valve_mean",
    "high_price_valve_mean",
    "charge_window_valve_mean",
    "discharge_window_valve_mean",
]
COUNTERFACTUAL_FIELDS = [
    "tes_marginal_saving_usd",
    "tes_marginal_saving_basis",
    "tes_marginal_saving_pair_key",
]
CORE_FIELDS = [
    "status",
    "action_dim",
    "obs_dim",
    "tes_action_semantics",
    "tes_direction_deadband",
    "tes_option_hold_steps",
    "enable_tes_state_augmentation",
    "provenance_metadata_missing",
    "provenance_metadata_sources",
    "tag",
    "design",
    "mode",
    "checkpoint",
    "workspace",
    "monitor_csv",
    "steps",
    "total_reward",
    "total_facility_MWh",
    "total_ite_MWh",
    "pue",
    "comfort_violation_pct",
    "mean_temperature_C",
    "max_temperature_C",
    "p95_temperature_C",
    "cost_usd_annual",
    "cost_usd",
    "pv_self_consumption_pct",
    "tes_annual_cycles_rough",
    "tes_soc_daily_amplitude_mean",
    "tes_activated",
    "valve_mean_abs",
    "valve_active_fraction",
    "valve_saturation_fraction",
    "charge_fraction",
    "discharge_fraction",
    "price_low_valve_mean",
    "price_high_valve_mean",
    "price_response_high_minus_low",
    "pv_low_valve_mean",
    "pv_high_valve_mean",
    "pv_response_high_minus_low",
    "guard_clipped_fraction",
    "soc_pre_source",
    "raw_invalid_charge_frac_guard_high",
    "raw_invalid_discharge_frac_guard_low",
    "raw_warn_limit_charge_frac_085",
    "raw_warn_limit_discharge_frac_015",
    "raw_actual_divergence",
    "raw_actual_divergence_p95",
    "tes_intent_to_effect_ratio",
    *TES_MECHANISM_FIELDS,
    *COUNTERFACTUAL_FIELDS,
    "elapsed_seconds",
]
SUMMARY_REQUIRED_MONITOR_COLUMNS = [
    "Electricity:Facility",
    "ITE-CPU:InteriorEquipment:Electricity",
    "air_temperature",
    "TES_SOC",
    "TES_valve_wrapper_position",
    "price_current_norm",
    "pv_current_ratio",
]
GUARD_RAW_TARGET_COLUMNS = ["tes_valve_target", "tes_signed_target_from_semantics", "TES_DRL"]
GUARD_ACTUAL_VALVE_COLUMNS = ["TES_valve_wrapper_position", "tes_valve_position"]


def duplicate_names(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicated: list[str] = []
    for value in values:
        if value in seen and value not in duplicated:
            duplicated.append(value)
        seen.add(value)
    return duplicated


def validate_raw_csv_header(path: Path) -> list[str]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        try:
            header = next(csv.reader(f))
        except StopIteration as exc:
            raise RuntimeError(f"Empty CSV file: {path}") from exc
    duplicated = duplicate_names(header)
    if duplicated:
        raise RuntimeError(f"Duplicate raw CSV header columns in {path}: {duplicated}")
    return header


def require_columns(df: pd.DataFrame, monitor_path: Path, columns: list[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise RuntimeError(f"Missing required monitor columns in {monitor_path}: {missing}")


def require_any_column(df: pd.DataFrame, monitor_path: Path, columns: list[str], purpose: str) -> str:
    for col in columns:
        if col in df.columns:
            return col
    raise RuntimeError(
        f"Missing required monitor column for {purpose} in {monitor_path}: expected one of {columns}"
    )


def optional_any_column(df: pd.DataFrame, columns: list[str]) -> str | None:
    for col in columns:
        if col in df.columns:
            return col
    return None


def read_monitor_csv(monitor_path: Path, *, required_columns: list[str] | None = None) -> pd.DataFrame:
    validate_raw_csv_header(monitor_path)
    # C2 fix: keep encoding consistent with validate_raw_csv_header above so a
    # BOM does not leak into the first column name (e.g. '﻿timestep').
    df = pd.read_csv(monitor_path, index_col=False, encoding="utf-8-sig")
    if not df.columns.is_unique:
        duplicated = df.columns[df.columns.duplicated()].tolist()
        raise RuntimeError(f"Duplicate monitor columns in {monitor_path}: {duplicated}")
    if required_columns:
        require_columns(df, monitor_path, required_columns)
    return df


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(v) for v in value]
    if isinstance(value, tuple):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_ready(data), indent=2), encoding="utf-8")


def finite_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def safe_checkpoint_action_dim(checkpoint: Path) -> tuple[int | None, str | None]:
    try:
        return checkpoint_action_dim(checkpoint), None
    except Exception as exc:
        return None, str(exc)


def m2_action_dim(action_semantics: str) -> int:
    if action_semantics in {"direction_amp", "direction_amp_hold"}:
        return 5
    return 4


def m2_action_variables(action_semantics: str) -> list[str]:
    if action_semantics in {"direction_amp", "direction_amp_hold"}:
        return [
            "CT_Pump_DRL",
            "CRAH_T_DRL",
            "Chiller_T_DRL",
            "TES_direction_DRL",
            "TES_amplitude_DRL",
        ]
    return ["CT_Pump_DRL", "CRAH_T_DRL", "Chiller_T_DRL", "TES_DRL"]


def requested_action_semantics(args: argparse.Namespace) -> str:
    return str(getattr(args, "tes_action_semantics", "signed_scalar"))


def requested_action_dim(args: argparse.Namespace) -> int:
    return m2_action_dim(requested_action_semantics(args))


def _resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _normalize_data_paths(args: argparse.Namespace) -> None:
    """C1 fix: normalize relative data-file args to ROOT-relative absolute paths.

    Safe to call multiple times; idempotent on already-absolute paths. Only
    touches attributes that exist on ``args`` so it works for every subcommand.
    """
    for attr in ("price_csv", "pv_csv"):
        value = getattr(args, attr, None)
        if value is None:
            continue
        setattr(args, attr, str(_resolve_repo_path(value)))


def _load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _workspace_provenance_sources(workspace: Path) -> list[tuple[Path, dict[str, Any]]]:
    workspace_resolved = _resolve_repo_path(workspace)
    sources: list[tuple[Path, dict[str, Any]]] = []
    metadata_path = workspace_resolved / "m2_training_metadata.json"
    if metadata_path.exists():
        data = _load_json_file(metadata_path)
        if data is not None:
            sources.append((metadata_path, data))
    jobs_root = ROOT / "training_jobs"
    if jobs_root.exists():
        for status_path in jobs_root.glob("*/status.json"):
            data = _load_json_file(status_path)
            if data is None:
                continue
            status_workspace = data.get("workspace_path")
            if not status_workspace:
                continue
            try:
                if _resolve_repo_path(status_workspace) == workspace_resolved:
                    sources.append((status_path, data))
            except OSError:
                continue
    return sources


def validate_workspace_provenance(
    args: argparse.Namespace,
    expected_action_dim: int,
    expected_obs_dim: int,
) -> dict[str, Any]:
    sources = _workspace_provenance_sources(args.workspace)
    provenance = {
        "provenance_metadata_missing": not bool(sources),
        "provenance_metadata_sources": ";".join(str(path) for path, _ in sources),
    }
    for path, data in sources:
        source = str(path)
        semantics = data.get("tes_action_semantics")
        if semantics is not None and semantics != requested_action_semantics(args):
            raise RuntimeError(
                f"Checkpoint provenance mismatch: {source} records "
                f"tes_action_semantics={semantics!r}, but CLI requested "
                f"{requested_action_semantics(args)!r}."
            )
        hold_steps = data.get("tes_option_hold_steps")
        if hold_steps is not None and (
            semantics == "direction_amp_hold" or requested_action_semantics(args) == "direction_amp_hold"
        ):
            requested_hold_steps = int(getattr(args, "tes_option_hold_steps", 4))
            if int(hold_steps) != requested_hold_steps:
                raise RuntimeError(
                    f"Checkpoint provenance mismatch: {source} records "
                    f"tes_option_hold_steps={hold_steps}, but CLI requested "
                    f"{requested_hold_steps}."
                )
        action_dim = data.get("action_dim")
        if action_dim is not None and int(action_dim) != int(expected_action_dim):
            raise RuntimeError(
                f"Checkpoint provenance mismatch: {source} records action_dim={action_dim}, "
                f"but CLI/env expects {expected_action_dim}."
            )
        obs_dim = data.get("obs_dim")
        if obs_dim is not None and int(obs_dim) != int(expected_obs_dim):
            raise RuntimeError(
                f"Checkpoint provenance mismatch: {source} records obs_dim={obs_dim}, "
                f"but CLI/env expects {expected_obs_dim}."
            )
        state_aug = data.get("enable_tes_state_augmentation")
        if state_aug is not None and bool(state_aug) != bool(getattr(args, "enable_tes_state_augmentation", False)):
            raise RuntimeError(
                f"Checkpoint provenance mismatch: {source} records "
                f"enable_tes_state_augmentation={bool(state_aug)}, but CLI requested "
                f"{bool(getattr(args, 'enable_tes_state_augmentation', False))}."
            )
    return provenance


def check_checkpoint_or_skip(checkpoint: Path, expected_action_dim: int = 4) -> dict[str, Any] | None:
    action_dim, error = safe_checkpoint_action_dim(checkpoint)
    if action_dim != expected_action_dim:
        return {
            "status": "skipped_action_dim_mismatch" if action_dim is not None else "skipped_unreadable_checkpoint",
            "action_dim": action_dim,
            "checkpoint": str(checkpoint),
            "reason": error or (
                f"M2-F1 validation requires action_dim={expected_action_dim}, got {action_dim}. "
                "Check --tes-action-semantics and checkpoint provenance."
            ),
        }
    return None


def normalization_stats(workspace: Path, expected_obs_dim: int) -> tuple[np.ndarray, np.ndarray]:
    mean = np.loadtxt(workspace / "mean.txt", dtype="float")
    var = np.loadtxt(workspace / "var.txt", dtype="float")
    if mean.shape[0] != expected_obs_dim or var.shape[0] != expected_obs_dim:
        raise RuntimeError(
            f"Expected {expected_obs_dim}-dim M2 normalization stats, "
            f"got mean={mean.shape}, var={var.shape}."
        )
    return mean, var


def design_config(design: str) -> dict[str, Any]:
    if design == "official":
        return {
            "building_file": "DRL_DC_evaluation.epJSON",
            "evaluation_flag": 1,
            "tes_initial_soc_range": None,
            "description": "Official evaluation epJSON, no SOC override.",
        }
    if design == "official_soc05":
        return {
            "building_file": "DRL_DC_evaluation.epJSON",
            "evaluation_flag": 1,
            "tes_initial_soc_range": (0.5, 0.5),
            "description": "Official evaluation epJSON with physical TES initial SOC fixed at 0.5.",
        }
    if design == "train_default":
        return {
            "building_file": "DRL_DC_training.epJSON",
            "evaluation_flag": 0,
            "tes_initial_soc_range": (0.2, 0.8),
            "description": "Training epJSON with run_m2_training default SOC randomization.",
        }
    if design == "trainlike_soc05":
        return {
            "building_file": "DRL_DC_training.epJSON",
            "evaluation_flag": 0,
            "tes_initial_soc_range": (0.5, 0.5),
            "description": "Training epJSON with physical TES initial SOC fixed at 0.5.",
        }
    raise ValueError(f"Unknown design: {design}")


def build_env(args: argparse.Namespace, design: str, tag: str):
    import gymnasium as gym

    from sinergym.envs.energy_scale_wrapper import EnergyScaleWrapper
    from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
    from sinergym.envs.pv_signal_wrapper import PVSignalWrapper
    from sinergym.envs.temp_trend_wrapper import TempTrendWrapper
    from sinergym.envs.tes_wrapper import (
        FixedActionInsertWrapper,
        TESDirectionAmplitudeActionWrapper,
        TESStateAugmentationWrapper,
        TESTargetValveWrapper,
    )
    from sinergym.envs.time_encoding_wrapper import TimeEncodingWrapper

    cfg = design_config(design)
    config_params: dict[str, Any] = {
        "runperiod": (1, 1, 2025, 31, 12, 2025),
        "timesteps_per_hour": M2_TIMESTEPS_PER_HOUR,
    }
    if cfg["tes_initial_soc_range"] is not None:
        config_params.update(
            {
                "tes_initial_soc_range": cfg["tes_initial_soc_range"],
                # C3 fix: align SOC cold-end with the same PR's epJSON +
                # sinergym/config/modeling.py default of 6.67 °C. Using 6.0 here
                # would skew initial-SOC randomization vs. the SOC observation
                # scaling and break counterfactual metrics.
                "tes_soc_cold_temp": 6.67,
                "tes_soc_hot_temp": 12.0,
                # tes_charge_setpoint is the chiller leaving-water target during
                # forced charge, not the SOC scale lower bound. Keep at 6.0.
                "tes_charge_setpoint": 6.0,
                "tes_initial_schedule_until": "00:15",
            }
        )

    # C4 fix: sinergym expects ``weather_files`` as a list. Passing a bare str
    # makes the env iterate it as a sequence of characters and break weather
    # resolution. Normalize once here so callers can supply either form.
    weather_files = [args.epw] if isinstance(args.epw, str) else list(args.epw)
    env = gym.make(
        "Eplus-DC-Cooling-TES",
        env_name=f"m2-validate-{tag}-{design}",
        building_file=cfg["building_file"],
        weather_files=weather_files,
        config_params=config_params,
        evaluation_flag=cfg["evaluation_flag"],
    )
    if getattr(args, "seed", None) is not None:
        env.action_space.seed(args.seed)

    env = TESTargetValveWrapper(
        env,
        valve_idx=4,
        rate_limit=args.tes_valve_rate_limit,
        soc_low_guard=args.tes_guard_soc_low,
        soc_high_guard=args.tes_guard_soc_high,
    )
    env = FixedActionInsertWrapper(
        env,
        fixed_actions={0: M2_FIXED_FAN_VALUE},
        fixed_action_names={0: "CRAH_Fan_DRL"},
    )
    if requested_action_semantics(args) in {"direction_amp", "direction_amp_hold"}:
        env = TESDirectionAmplitudeActionWrapper(
            env,
            direction_deadband=float(getattr(args, "tes_direction_deadband", 0.15)),
            action_semantics=requested_action_semantics(args),
            hold_steps=int(getattr(args, "tes_option_hold_steps", 4)),
        )
    env = TimeEncodingWrapper(env)
    env = TempTrendWrapper(
        env,
        epw_path=Path("Data/weather") / (args.epw if isinstance(args.epw, str) else args.epw[0]),
        lookahead_hours=6,
    )
    env = PriceSignalWrapper(env, price_csv_path=args.price_csv)
    env = PVSignalWrapper(env, pv_csv_path=args.pv_csv, dc_peak_load_kw=args.dc_peak_load_kw)
    env = EnergyScaleWrapper(env, energy_indices=[13, 14], scale=1.0 / 3.6e9)
    if getattr(args, "enable_tes_state_augmentation", False):
        env = TESStateAugmentationWrapper(
            env,
            high_price_threshold=args.high_price_threshold,
            low_price_threshold=args.low_price_threshold,
            near_peak_threshold=args.near_peak_threshold,
        )
    return env


def attach_eval_reward(env, args: argparse.Namespace):
    from tools.evaluate_m2 import attach_reward as _attach_reward

    return _attach_reward(env, args)


def attach_logger(env):
    from sinergym.utils.wrappers import LoggerWrapper

    obs_vars = list(env.get_wrapper_attr("observation_variables"))
    act_vars = list(env.get_wrapper_attr("action_variables"))
    allowed_act_vars = {
        tuple(m2_action_variables("signed_scalar")),
        tuple(m2_action_variables("direction_amp")),
    }
    if tuple(act_vars) not in allowed_act_vars:
        raise RuntimeError(f"M2-F1 action_variables mismatch: got {act_vars}")
    return LoggerWrapper(
        env,
        monitor_header=["timestep"] + obs_vars + act_vars
        + [
            "time (hours)",
            "reward",
            "energy_term",
            "ITE_term",
            "comfort_term",
            "cost_term",
            "cost_usd_step",
            "mwh_step",
            "lmp_usd_per_mwh",
            "current_price_usd_per_mwh",
            "current_pv_kw",
            "fixed_CRAH_Fan_DRL",
            "action_dim",
            "tes_action_semantics",
            "tes_direction_deadband",
            "tes_direction_raw",
            "tes_amplitude_raw",
            "tes_amplitude_mapped",
            "tes_direction_mode",
            "tes_signed_target_from_semantics",
            "tes_option_hold_steps",
            "tes_option_hold_counter_remaining",
            "tes_option_accepted_new_mode",
            "tes_held_direction_mode",
            "tes_held_amplitude_mapped",
            "tes_valve_target",
            "tes_valve_position",
            "tes_guard_clipped",
            "tes_action_mode",
            "tes_tou_phase_for_state",
            "enable_tes_state_augmentation",
            "terminated",
            "truncated",
        ],
    )


def energy_mwh(series: pd.Series) -> tuple[np.ndarray, str]:
    values = pd.to_numeric(series, errors="coerce").astype(float)
    if float(values.abs().median()) > 1.0e5:
        return (values / 3.6e9).to_numpy(), "J"
    return values.to_numpy(), "MWh"


def numeric(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype=float)
    return pd.to_numeric(df[col], errors="coerce").astype(float)


def bool_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([False] * len(df), index=df.index, dtype=bool)
    values = df[col]
    if values.dtype == bool:
        return values.fillna(False)
    return values.astype(str).str.lower().isin(["true", "1", "yes"])


def guard_metrics_from_df(
    df: pd.DataFrame,
    monitor_path: Path,
    *,
    guard_soc_high: float = 0.90,
    guard_soc_low: float = 0.10,
    warn_soc_high: float = 0.85,
    warn_soc_low: float = 0.15,
) -> dict[str, Any]:
    require_columns(df, monitor_path, ["TES_SOC"])
    raw_col = optional_any_column(df, GUARD_RAW_TARGET_COLUMNS)
    actual_col = optional_any_column(df, GUARD_ACTUAL_VALVE_COLUMNS)
    metrics: dict[str, Any] = {
        "guard_clipped_fraction": float(bool_series(df, "tes_guard_clipped").mean()) if len(df) else None,
        "soc_pre_source": "shifted_TES_SOC",
        "raw_invalid_charge_frac_guard_high": None,
        "raw_invalid_discharge_frac_guard_low": None,
        "raw_warn_limit_charge_frac_085": None,
        "raw_warn_limit_discharge_frac_015": None,
        "guard_soc_high": float(guard_soc_high),
        "guard_soc_low": float(guard_soc_low),
        "warn_soc_high": float(warn_soc_high),
        "warn_soc_low": float(warn_soc_low),
        "raw_actual_divergence": None,
        "raw_actual_divergence_p95": None,
        "tes_intent_to_effect_ratio": None,
        "raw_abs_mean": None,
        "actual_abs_mean": None,
        "raw_target_column": raw_col,
        "actual_valve_column": actual_col,
    }

    raw = numeric(df, raw_col) if raw_col else pd.Series(np.nan, index=df.index, dtype=float)
    actual = numeric(df, actual_col) if actual_col else pd.Series(np.nan, index=df.index, dtype=float)
    if raw_col:
        raw_abs = raw.clip(-1, 1).abs()
        metrics["raw_abs_mean"] = float(raw_abs.mean()) if raw_abs.notna().any() else None
    if actual_col:
        actual_abs = actual.clip(-1, 1).abs()
        metrics["actual_abs_mean"] = float(actual_abs.mean()) if actual_abs.notna().any() else None
    if raw_col is None or actual_col is None:
        return metrics

    soc_pre = numeric(df, "TES_SOC").shift(1)
    valid = pd.DataFrame({"raw": raw, "actual": actual, "soc_pre": soc_pre}).dropna()
    if valid.empty:
        return metrics

    raw = valid["raw"].clip(-1, 1)
    actual = valid["actual"].clip(-1, 1)
    soc_pre = valid["soc_pre"]
    divergence = (raw - actual).abs()
    intent = raw.abs().sum()
    effect = actual.abs().sum()
    metrics.update(
        {
            "raw_invalid_charge_frac_guard_high": float(((soc_pre >= guard_soc_high) & (raw < -0.05)).mean()),
            "raw_invalid_discharge_frac_guard_low": float(((soc_pre <= guard_soc_low) & (raw > 0.05)).mean()),
            "raw_warn_limit_charge_frac_085": float(((soc_pre >= warn_soc_high) & (raw < -0.05)).mean()),
            "raw_warn_limit_discharge_frac_015": float(((soc_pre <= warn_soc_low) & (raw > 0.05)).mean()),
            "raw_actual_divergence": float(divergence.mean()),
            "raw_actual_divergence_p95": float(divergence.quantile(0.95)),
            "tes_intent_to_effect_ratio": float(effect / intent) if intent > 1.0e-12 else None,
            "raw_abs_mean": float(raw.abs().mean()),
            "actual_abs_mean": float(actual.abs().mean()),
        }
    )
    return metrics


def arg_float(args: argparse.Namespace, name: str, default: float) -> float:
    return float(getattr(args, name, default))


def mean_or_none(values: pd.Series) -> float | None:
    valid = values.dropna()
    return float(valid.mean()) if len(valid) else None


def contiguous_true_runs(mask: pd.Series) -> list[tuple[int, int]]:
    arr = mask.fillna(False).to_numpy(dtype=bool)
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for idx, flag in enumerate(arr):
        if flag and start is None:
            start = idx
        elif not flag and start is not None:
            runs.append((start, idx))
            start = None
    if start is not None:
        runs.append((start, len(arr)))
    return runs


def soc_window_delta_mean(mask: pd.Series, soc: pd.Series, soc_pre: pd.Series) -> tuple[float | None, int]:
    deltas: list[float] = []
    for start, end in contiguous_true_runs(mask):
        if end <= start:
            continue
        start_soc = soc_pre.iloc[start]
        if pd.isna(start_soc):
            start_soc = soc.iloc[start]
        end_soc = soc.iloc[end - 1]
        if pd.notna(start_soc) and pd.notna(end_soc):
            deltas.append(float(end_soc - start_soc))
    return (float(np.mean(deltas)) if deltas else None, len(deltas))


def charge_sign_flip_delays(mask: pd.Series, actual: pd.Series) -> tuple[int | None, float | None, float | None]:
    if not actual.notna().any():
        return None, None, None
    runs = contiguous_true_runs(mask)
    if not runs:
        return None, None, None
    first_delay: int | None = None
    delays: list[int] = []
    no_flip = 0
    for run_idx, (start, end) in enumerate(runs):
        hits = np.flatnonzero((actual.iloc[start:end] < -0.05).fillna(False).to_numpy(dtype=bool))
        if len(hits):
            delay = int(hits[0])
            delays.append(delay)
            if run_idx == 0:
                first_delay = delay
        else:
            no_flip += 1
    return (
        first_delay,
        float(np.mean(delays)) if delays else None,
        float(no_flip / len(runs)),
    )


def tes_mechanism_metrics_from_df(
    df: pd.DataFrame,
    args: argparse.Namespace,
    monitor_path: Path,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {field: None for field in TES_MECHANISM_FIELDS}
    low_price_threshold = arg_float(args, "low_price_threshold", -0.50)
    high_price_threshold = arg_float(args, "high_price_threshold", 0.75)
    near_peak_threshold = arg_float(args, "near_peak_threshold", 0.40)
    soc_charge_limit = arg_float(args, "soc_charge_limit", 0.85)
    soc_discharge_limit = arg_float(args, "soc_discharge_limit", 0.25)
    metrics.update(
        {
            "tes_mechanism_low_price_threshold": low_price_threshold,
            "tes_mechanism_high_price_threshold": high_price_threshold,
            "tes_mechanism_near_peak_threshold": near_peak_threshold,
            "tes_mechanism_soc_charge_limit": soc_charge_limit,
            "tes_mechanism_soc_discharge_limit": soc_discharge_limit,
            "tes_valve_sign_convention": "negative=charge, positive=discharge",
            "raw_actual_divergence_switch_radius_steps": TOU_SWITCH_RADIUS_STEPS,
        }
    )

    price_col = "price_current_norm" if "price_current_norm" in df.columns else None
    hours_col = "price_hours_to_next_peak_norm" if "price_hours_to_next_peak_norm" in df.columns else None
    soc_col = "TES_SOC" if "TES_SOC" in df.columns else None
    actual_col = optional_any_column(df, GUARD_ACTUAL_VALVE_COLUMNS)
    raw_col = optional_any_column(df, GUARD_RAW_TARGET_COLUMNS)
    if price_col is None or soc_col is None:
        return metrics

    price = numeric(df, price_col)
    soc = numeric(df, soc_col)
    soc_pre = soc.shift(1)
    actual = numeric(df, actual_col) if actual_col else pd.Series(np.nan, index=df.index, dtype=float)
    low_price = price.notna() & (price <= low_price_threshold)
    high_price = price.notna() & (price >= high_price_threshold)

    if actual_col:
        metrics["low_price_valve_mean"] = mean_or_none(actual[low_price])
        metrics["high_price_valve_mean"] = mean_or_none(actual[high_price])

    low_prepeak = pd.Series(False, index=df.index, dtype=bool)
    if hours_col is not None:
        hours_to_peak = numeric(df, hours_col)
        low_prepeak = low_price & hours_to_peak.notna() & (hours_to_peak <= near_peak_threshold)
        charge_window = low_prepeak & soc_pre.notna() & (soc_pre < soc_charge_limit)
        metrics["charge_window_step_count"] = int(charge_window.sum())
        charge_valid = charge_window & actual.notna()
        if actual_col and bool(charge_valid.any()):
            metrics["charge_window_sign_rate"] = float((actual[charge_valid] < -0.05).mean())
            metrics["low_price_discharge_fraction"] = float((actual[charge_valid] > 0.05).mean())
            metrics["charge_window_valve_mean"] = float(actual[charge_valid].mean())
        delta_prepeak, prepeak_count = soc_window_delta_mean(charge_window, soc, soc_pre)
        metrics["delta_soc_prepeak"] = delta_prepeak
        metrics["prepeak_window_count"] = int(prepeak_count)
        if actual_col:
            first_delay, mean_delay, no_flip_fraction = charge_sign_flip_delays(charge_window, actual)
            metrics["sign_flip_delay_steps"] = first_delay
            metrics["sign_flip_delay_steps_mean"] = mean_delay
            metrics["sign_flip_no_flip_fraction"] = no_flip_fraction

    discharge_window = high_price & soc_pre.notna() & (soc_pre > soc_discharge_limit)
    metrics["discharge_window_step_count"] = int(discharge_window.sum())
    discharge_valid = discharge_window & actual.notna()
    if actual_col and bool(discharge_valid.any()):
        metrics["discharge_window_sign_rate"] = float((actual[discharge_valid] > 0.05).mean())
        metrics["discharge_window_valve_mean"] = float(actual[discharge_valid].mean())
    delta_peak, peak_count = soc_window_delta_mean(discharge_window, soc, soc_pre)
    metrics["delta_soc_peak"] = delta_peak
    metrics["peak_window_count"] = int(peak_count)

    if raw_col and actual_col:
        phase = pd.Series(0, index=df.index, dtype=int)
        phase.loc[high_price] = 2
        phase.loc[low_prepeak] = -1
        phase_np = phase.to_numpy(dtype=int)
        switch_indices = np.flatnonzero(phase_np[1:] != phase_np[:-1]) + 1 if len(phase_np) > 1 else np.array([], dtype=int)
        near_switch: set[int] = set()
        for idx in switch_indices:
            lo = max(0, int(idx) - TOU_SWITCH_RADIUS_STEPS)
            hi = min(len(df), int(idx) + TOU_SWITCH_RADIUS_STEPS + 1)
            near_switch.update(range(lo, hi))
        raw = numeric(df, raw_col).clip(-1, 1)
        divergence = (raw - actual.clip(-1, 1)).abs()
        near_divergence = divergence.iloc[sorted(near_switch)].dropna() if near_switch else pd.Series(dtype=float)
        metrics["raw_actual_divergence_switch_count"] = int(len(near_divergence))
        if len(near_divergence):
            metrics["raw_actual_divergence_switch_mean"] = float(near_divergence.mean())
            metrics["raw_actual_divergence_switch_p95"] = float(near_divergence.quantile(0.95))

    return metrics


def summarize_monitor(
    df: pd.DataFrame,
    args: argparse.Namespace,
    steps: int,
    total_reward: float,
    elapsed: float,
    monitor_path: Path,
) -> dict[str, Any]:
    require_columns(df, monitor_path, SUMMARY_REQUIRED_MONITOR_COLUMNS)

    facility_MWh_step, energy_unit = energy_mwh(df["Electricity:Facility"])
    ite_MWh_step, _ = energy_mwh(df["ITE-CPU:InteriorEquipment:Electricity"])
    temps = numeric(df, "air_temperature")
    valves = numeric(df, "TES_valve_wrapper_position")
    soc = numeric(df, "TES_SOC")

    total_facility_MWh = float(np.nansum(facility_MWh_step))
    total_ite_MWh = float(np.nansum(ite_MWh_step))
    pue = total_facility_MWh / total_ite_MWh if total_ite_MWh > 0 else float("nan")
    comfort_pct = float((temps > 25.0).sum() / max(len(temps), 1) * 100.0)

    # C2 fix: BOM-safe reads aligned with validate_raw_csv_header.
    price = pd.read_csv(args.price_csv, encoding="utf-8-sig")["price_usd_per_mwh"].to_numpy(dtype=np.float64)
    pv = pd.read_csv(args.pv_csv, encoding="utf-8-sig")["power_kw"].to_numpy(dtype=np.float64)
    hour_idx = (np.arange(len(facility_MWh_step)) // M2_TIMESTEPS_PER_HOUR) % len(price)
    lmp_step = price[hour_idx]
    pv_step = pv[hour_idx]
    cost_usd_annual = float(np.nansum(facility_MWh_step * lmp_step))

    dt_hours = 1.0 / M2_TIMESTEPS_PER_HOUR
    facility_kW_step = facility_MWh_step / dt_hours * 1000.0
    self_cons_kWh = np.minimum(facility_kW_step, pv_step).sum() * dt_hours
    facility_kWh = total_facility_MWh * 1000.0
    pv_self_consumption_pct = float(self_cons_kWh / facility_kWh * 100.0 if facility_kWh > 0 else 0.0)

    price_signal = numeric(df, "price_current_norm")
    low_price = valves[price_signal <= price_signal.quantile(0.25)]
    high_price = valves[price_signal >= price_signal.quantile(0.75)]
    price_low_valve_mean = float(low_price.mean()) if len(low_price) else None
    price_high_valve_mean = float(high_price.mean()) if len(high_price) else None
    price_response = (
        price_high_valve_mean - price_low_valve_mean
        if price_high_valve_mean is not None and price_low_valve_mean is not None
        else None
    )

    pv_signal = numeric(df, "pv_current_ratio")
    low_pv = valves[pv_signal <= pv_signal.quantile(0.25)]
    high_pv = valves[pv_signal >= pv_signal.quantile(0.75)]
    pv_low_valve_mean = float(low_pv.mean()) if len(low_pv) else None
    pv_high_valve_mean = float(high_pv.mean()) if len(high_pv) else None
    pv_response = (
        pv_high_valve_mean - pv_low_valve_mean
        if pv_high_valve_mean is not None and pv_low_valve_mean is not None
        else None
    )

    valves_effective = np.where(valves.abs().to_numpy() > 0.01, valves.abs().to_numpy(), 0.0)
    cycles_rough = float(
        valves_effective.sum()
        * TES_MAX_FLOW_KG_S
        * (3600.0 / M2_TIMESTEPS_PER_HOUR)
        / 1000.0
        / TES_TANK_M3
    )

    soc_np = soc.to_numpy(dtype=float)
    steps_per_day = 24 * M2_TIMESTEPS_PER_HOUR
    n_days = len(soc_np) // steps_per_day
    daily_amp = np.array(
        [
            np.nanmax(soc_np[d * steps_per_day:(d + 1) * steps_per_day])
            - np.nanmin(soc_np[d * steps_per_day:(d + 1) * steps_per_day])
            for d in range(n_days)
        ],
        dtype=np.float64,
    )
    soc_daily_amplitude_mean = float(np.nanmean(daily_amp)) if len(daily_amp) else 0.0

    result = {
        "status": "ok",
        "steps": int(steps),
        "max_steps": getattr(args, "max_steps", 0),
        "total_reward": float(total_reward),
        "total_facility_MWh": total_facility_MWh,
        "total_ite_MWh": total_ite_MWh,
        "energy_unit_detected": energy_unit,
        "pue": pue,
        "comfort_violation_pct": comfort_pct,
        "mean_temperature_C": float(temps.mean()),
        "max_temperature_C": float(temps.max()),
        "p95_temperature_C": float(temps.quantile(0.95)),
        "cost_usd_annual": cost_usd_annual,
        "cost_usd": cost_usd_annual,
        "pv_self_consumption_pct": pv_self_consumption_pct,
        "tes_annual_cycles_rough": cycles_rough,
        "tes_soc_daily_amplitude_mean": soc_daily_amplitude_mean,
        "tes_activated": bool(cycles_rough >= 100.0 and soc_daily_amplitude_mean >= 0.3),
        "valve_mean_abs": float(valves.abs().mean()),
        "valve_active_fraction": float((valves.abs() > 0.05).mean()),
        "valve_saturation_fraction": float((valves.abs() > 0.95).mean()),
        "charge_fraction": float((valves < -0.05).mean()),
        "discharge_fraction": float((valves > 0.05).mean()),
        "soc_min": float(soc.min()),
        "soc_mean": float(soc.mean()),
        "soc_max": float(soc.max()),
        "price_low_valve_mean": price_low_valve_mean,
        "price_high_valve_mean": price_high_valve_mean,
        "price_response_high_minus_low": price_response,
        "pv_low_valve_mean": pv_low_valve_mean,
        "pv_high_valve_mean": pv_high_valve_mean,
        "pv_response_high_minus_low": pv_response,
        "monitor_csv": str(monitor_path),
        "elapsed_seconds": float(elapsed),
    }
    result.update(
        guard_metrics_from_df(
            df,
            monitor_path,
            guard_soc_high=getattr(args, "tes_guard_soc_high", 0.90),
            guard_soc_low=getattr(args, "tes_guard_soc_low", 0.10),
        )
    )
    result.update(tes_mechanism_metrics_from_df(df, args, monitor_path))
    return result


def obs_idx(names: list[str], name: str) -> int:
    if name not in names:
        raise RuntimeError(f"{name!r} not found in observation_variables: {names}")
    return names.index(name)


def rule_policy_action(obs: np.ndarray, names: list[str], args: argparse.Namespace) -> np.ndarray:
    soc = float(obs[obs_idx(names, "TES_SOC")])
    price = float(obs[obs_idx(names, "price_current_norm")])
    hours_to_peak = float(obs[obs_idx(names, "price_hours_to_next_peak_norm")])

    tes_target = 0.0
    if price >= args.high_price_threshold and soc > args.soc_discharge_limit:
        tes_target = args.discharge_target
    elif (
        price <= args.low_price_threshold
        and hours_to_peak <= args.near_peak_threshold
        and soc < args.soc_charge_limit
    ):
        tes_target = -args.charge_target

    return np.array(
        [
            args.frozen_ct_pump_action,
            args.frozen_crah_temp_action,
            args.frozen_chiller_temp_action,
            tes_target,
        ],
        dtype=np.float32,
    )


def make_policy(args: argparse.Namespace, mode: str, model: Any, obs_names: list[str]) -> Callable[[np.ndarray], np.ndarray]:
    expected_dim = requested_action_dim(args)
    frozen = np.array(
        [args.frozen_ct_pump_action, args.frozen_crah_temp_action, args.frozen_chiller_temp_action],
        dtype=np.float32,
    )

    def learned(obs: np.ndarray) -> np.ndarray:
        action, _ = model.predict(obs, deterministic=not args.stochastic)
        action = np.asarray(action, dtype=np.float32)
        if action.shape != (expected_dim,):
            raise RuntimeError(f"Expected {expected_dim}D M2-F1 policy action, got {action.shape}")
        return action

    if mode == "full_learned":
        return learned

    if mode == "learned_tes_frozen_hvac":
        def policy(obs: np.ndarray) -> np.ndarray:
            action = learned(obs)
            out = action.copy()
            out[:3] = frozen
            return out.astype(np.float32)
        return policy

    if mode == "rule_tes_frozen_hvac":
        raise RuntimeError(
            "rule_tes_frozen_hvac is unsupported for actual evaluation in this wrapper stack: "
            "NormalizeObservation passes normalized observations to policy(), and raw pre-action "
            "TES_SOC/price_current_norm/price_hours_to_next_peak_norm are not available through "
            "info before selecting the action. Refusing to run rule semantics on normalized signals."
        )

    if mode == "learned_hvac_tes_zero":
        def policy(obs: np.ndarray) -> np.ndarray:
            action = learned(obs)
            if requested_action_semantics(args) in {"direction_amp", "direction_amp_hold"}:
                return np.array([action[0], action[1], action[2], 0.0, -1.0], dtype=np.float32)
            return np.array([action[0], action[1], action[2], 0.0], dtype=np.float32)
        return policy

    raise ValueError(f"Unknown counterfactual mode: {mode}")


def run_policy_eval(args: argparse.Namespace, design: str, tag: str, mode: str) -> dict[str, Any]:
    from sinergym.utils.common import get_ids
    from sinergym.utils.wrappers import NormalizeObservation
    from tools.dsac_t import DSAC_T

    if "Eplus-DC-Cooling-TES" not in get_ids():
        raise RuntimeError("Eplus-DC-Cooling-TES environment is not registered.")

    expected_action_dim = requested_action_dim(args)
    skipped = check_checkpoint_or_skip(args.checkpoint, expected_action_dim)
    if skipped is not None:
        skipped.update({"tag": tag, "design": design, "mode": mode, "workspace": str(args.workspace)})
        return skipped

    expected_obs_dim = 34 if getattr(args, "enable_tes_state_augmentation", False) else 32
    provenance = validate_workspace_provenance(args, expected_action_dim, expected_obs_dim)
    mean, var = normalization_stats(args.workspace, expected_obs_dim)
    env = build_env(args, design, tag)
    env = attach_eval_reward(env, args)
    if env.action_space.shape != (expected_action_dim,):
        raise RuntimeError(f"Expected M2-F1 {expected_action_dim}D action space, got {env.action_space.shape}")
    if env.observation_space.shape != (expected_obs_dim,):
        raise RuntimeError(
            f"Expected M2-F1 obs_dim={expected_obs_dim}, got {env.observation_space.shape}. "
            f"Check --enable-tes-state-augmentation and workspace normalization stats."
        )
    env = NormalizeObservation(env, mean=mean, var=var, automatic_update=False)
    obs_names = list(env.get_wrapper_attr("observation_variables"))
    env = attach_logger(env)
    workspace_post = Path(env.get_wrapper_attr("workspace_path"))
    model = DSAC_T.load(str(args.checkpoint), device="cpu")
    policy = make_policy(args, mode, model, obs_names)

    started = time.perf_counter()
    obs, _ = env.reset(seed=getattr(args, "seed", None))
    terminated = truncated = False
    steps = 0
    total_reward = 0.0
    try:
        while not (terminated or truncated):
            action = policy(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            if float(info.get("fixed_CRAH_Fan_DRL", np.nan)) != M2_FIXED_FAN_VALUE:
                raise RuntimeError("Fixed CRAH_Fan_DRL guard failed during validation.")
            total_reward += float(reward)
            steps += 1
            if args.max_steps and steps >= args.max_steps:
                break
    finally:
        env.close()

    monitor_path = workspace_post / "episode-001" / "monitor.csv"
    if not monitor_path.exists():
        raise RuntimeError(f"Monitor CSV not found: {monitor_path}")
    df = read_monitor_csv(monitor_path, required_columns=SUMMARY_REQUIRED_MONITOR_COLUMNS)
    result = summarize_monitor(
        df=df,
        args=args,
        steps=steps,
        total_reward=total_reward,
        elapsed=time.perf_counter() - started,
        monitor_path=monitor_path,
    )
    result.update(
        {
            "action_dim": expected_action_dim,
            "tes_action_semantics": requested_action_semantics(args),
            "tes_direction_deadband": getattr(args, "tes_direction_deadband", None),
            "tes_option_hold_steps": getattr(args, "tes_option_hold_steps", None),
            "obs_dim": expected_obs_dim,
            "enable_tes_state_augmentation": bool(getattr(args, "enable_tes_state_augmentation", False)),
            **provenance,
            "tag": tag,
            "design": design,
            "mode": mode,
            "checkpoint": str(args.checkpoint),
            "workspace": str(args.workspace),
            "reward_cls": args.reward_cls,
        }
    )
    return result


def should_execute_eval(args: argparse.Namespace) -> bool:
    requested = bool(getattr(args, "run", False) or getattr(args, "confirm_run", False))
    if getattr(args, "dry_run", False) and requested:
        raise ValueError("--dry-run cannot be combined with --run/--confirm-run.")
    if not requested:
        return False
    if getattr(args, "max_steps", 0) <= 0 and not getattr(args, "allow_full_eval", False):
        raise ValueError(
            "Full-episode evaluation requires --allow-full-eval. "
            "For a bounded smoke run, pass --max-steps > 0 with --run/--confirm-run."
        )
    return True


def counterfactual_semantics(args: argparse.Namespace) -> dict[str, Any]:
    tes_zero_action = (
        {"TES_direction_DRL": 0.0, "TES_amplitude_DRL": -1.0}
        if requested_action_semantics(args) in {"direction_amp", "direction_amp_hold"}
        else {"TES_DRL": 0.0}
    )
    return {
        "tes_action_semantics": requested_action_semantics(args),
        "tes_direction_deadband": getattr(args, "tes_direction_deadband", None),
        "tes_option_hold_steps": getattr(args, "tes_option_hold_steps", None),
        "frozen_hvac_action": {
            "CT_Pump_DRL": float(args.frozen_ct_pump_action),
            "CRAH_T_DRL": float(args.frozen_crah_temp_action),
            "Chiller_T_DRL": float(args.frozen_chiller_temp_action),
            "meaning": "These fixed normalized action values replace learned HVAC dimensions in frozen-HVAC modes.",
        },
        "learned_hvac_tes_zero": {
            **tes_zero_action,
            "meaning": "The learned HVAC dimensions are preserved and the TES command is forced to neutral zero under the selected action semantics.",
        },
        "rule_tes_frozen_hvac": {
            "status": "unsupported_for_actual_eval",
            "reason": (
                "The current policy call receives normalized observations after NormalizeObservation; "
                "raw pre-action TES_SOC and price signals are not available through info before action selection."
            ),
            "threshold_source": "CLI defaults/overrides are recorded for diagnostics only unless raw signals are provided.",
            "high_price_threshold": float(args.high_price_threshold),
            "low_price_threshold": float(args.low_price_threshold),
            "near_peak_threshold": float(args.near_peak_threshold),
            "soc_charge_limit": float(args.soc_charge_limit),
            "soc_discharge_limit": float(args.soc_discharge_limit),
            "charge_target": float(args.charge_target),
            "discharge_target": float(args.discharge_target),
        },
    }


def write_manifest(out_dir: Path, args: argparse.Namespace, runs: list[dict[str, Any]]) -> Path:
    execute = bool(getattr(args, "_execute_eval", False))
    expected_obs_dim = 34 if getattr(args, "enable_tes_state_augmentation", False) else 32
    provenance = validate_workspace_provenance(args, requested_action_dim(args), expected_obs_dim)
    manifest = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "subcommand": args.command,
        "checkpoint": str(args.checkpoint),
        "workspace": str(args.workspace),
        "action_dim": safe_checkpoint_action_dim(args.checkpoint)[0],
        "expected_action_dim": requested_action_dim(args),
        "tes_action_semantics": requested_action_semantics(args),
        "tes_direction_deadband": getattr(args, "tes_direction_deadband", None),
        "tes_option_hold_steps": getattr(args, "tes_option_hold_steps", None),
        **provenance,
        "reward_cls": args.reward_cls,
        "dry_run": not execute,
        "run_requested": bool(getattr(args, "run", False) or getattr(args, "confirm_run", False)),
        "allow_full_eval": bool(getattr(args, "allow_full_eval", False)),
        "max_steps": int(getattr(args, "max_steps", 0)),
        "designs": {name: design_config(name) for name in getattr(args, "designs", [])},
        "counterfactual_semantics": counterfactual_semantics(args),
        "runs": runs,
    }
    path = out_dir / "manifest.json"
    write_json(path, manifest)
    return path


def write_summary_files(
    out_dir: Path,
    rows: list[dict[str, Any]],
    title: str,
    metadata: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "summary.json"
    csv_path = out_dir / "summary.csv"
    counterfactual_pairs = compute_counterfactual_marginal_savings(rows)
    payload = {"title": title, "rows": rows}
    if counterfactual_pairs:
        payload["counterfactual_marginal_savings"] = counterfactual_pairs
    if metadata:
        payload.update(metadata)
    write_json(json_path, payload)
    fields = list(dict.fromkeys(CORE_FIELDS + sorted({k for row in rows for k in row.keys()})))
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return json_path, csv_path


def cmd_paired_eval(args: argparse.Namespace) -> int:
    try:
        args._execute_eval = should_execute_eval(args)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    out_dir = args.out_dir / f"action_dim_{safe_checkpoint_action_dim(args.checkpoint)[0] or 'unknown'}" / args.tag
    run_specs = [
        {
            "tag": f"{args.tag}_{design}",
            "design": design,
            "mode": "full_learned",
            "out": str(out_dir / design / "result.json"),
            "description": design_config(design)["description"],
        }
        for design in args.designs
    ]
    manifest_path = write_manifest(out_dir, args, run_specs)

    rows: list[dict[str, Any]] = []
    if not args._execute_eval:
        skipped = check_checkpoint_or_skip(args.checkpoint, requested_action_dim(args))
        rows = []
        for spec in run_specs:
            row = {
                "status": "planned",
                "action_dim": safe_checkpoint_action_dim(args.checkpoint)[0],
                "tes_action_semantics": requested_action_semantics(args),
                "tes_direction_deadband": getattr(args, "tes_direction_deadband", None),
                "tes_option_hold_steps": getattr(args, "tes_option_hold_steps", None),
                "tag": spec["tag"],
                "design": spec["design"],
                "mode": spec["mode"],
                "checkpoint": str(args.checkpoint),
                "workspace": str(args.workspace),
            }
            if skipped is not None:
                row.update(skipped)
                row["tag"] = spec["tag"]
                row["design"] = spec["design"]
                row["mode"] = spec["mode"]
                row["workspace"] = str(args.workspace)
            rows.append(row)
    else:
        for spec in run_specs:
            result = run_policy_eval(args, spec["design"], spec["tag"], spec["mode"])
            write_json(Path(spec["out"]), result)
            rows.append(result)

    summary_json, summary_csv = write_summary_files(out_dir, rows, "M2 paired validation")
    print(f"Wrote {manifest_path}")
    print(f"Wrote {summary_json}")
    print(f"Wrote {summary_csv}")
    return 0


def cmd_counterfactual_eval(args: argparse.Namespace) -> int:
    try:
        args._execute_eval = should_execute_eval(args)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args._execute_eval and "rule_tes_frozen_hvac" in args.modes:
        print(
            "ERROR: rule_tes_frozen_hvac is unsupported for actual evaluation because raw pre-action "
            "TES/price signals are unavailable to policy(); remove that mode or keep the default planned run.",
            file=sys.stderr,
        )
        return 2
    out_dir = args.out_dir / f"action_dim_{safe_checkpoint_action_dim(args.checkpoint)[0] or 'unknown'}" / args.tag
    rows: list[dict[str, Any]] = []
    run_specs = []
    for mode in args.modes:
        tag = f"{args.tag}_{args.design}_{mode}"
        out = out_dir / mode / "result.json"
        run_specs.append({"tag": tag, "design": args.design, "mode": mode, "out": str(out)})
    manifest_path = write_manifest(out_dir, args, run_specs)

    if not args._execute_eval:
        skipped = check_checkpoint_or_skip(args.checkpoint, requested_action_dim(args))
        rows = []
        for spec in run_specs:
            row = {
                "status": "planned",
                "action_dim": safe_checkpoint_action_dim(args.checkpoint)[0],
                "tes_action_semantics": requested_action_semantics(args),
                "tes_direction_deadband": getattr(args, "tes_direction_deadband", None),
                "tes_option_hold_steps": getattr(args, "tes_option_hold_steps", None),
                "tag": spec["tag"],
                "design": spec["design"],
                "mode": spec["mode"],
                "checkpoint": str(args.checkpoint),
                "workspace": str(args.workspace),
            }
            if skipped is not None:
                row.update(skipped)
                row["tag"] = spec["tag"]
                row["design"] = spec["design"]
                row["mode"] = spec["mode"]
                row["workspace"] = str(args.workspace)
            rows.append(row)
    else:
        for spec in run_specs:
            result = run_policy_eval(args, spec["design"], spec["tag"], spec["mode"])
            write_json(Path(spec["out"]), result)
            rows.append(result)

    summary_json, summary_csv = write_summary_files(
        out_dir,
        rows,
        "M2 counterfactual validation",
        metadata={"counterfactual_semantics": counterfactual_semantics(args)},
    )
    print(f"Wrote {manifest_path}")
    print(f"Wrote {summary_json}")
    print(f"Wrote {summary_csv}")
    return 0


def monitor_paths_from_args(args: argparse.Namespace) -> tuple[list[Path], list[dict[str, Any]]]:
    paths: list[Path] = []
    diagnostics: list[dict[str, Any]] = []
    for item in args.inputs:
        path = Path(item)
        if not path.exists():
            diagnostics.append(
                {
                    "status": "error",
                    "input": item,
                    "monitor_csv": str(path),
                    "error": f"Input path does not exist: {path}",
                }
            )
            continue
        if path.is_file() and path.suffix.lower() == ".csv":
            paths.append(path)
        elif path.is_file() and path.suffix.lower() == ".json":
            data = load_json(path)
            monitor = data.get("monitor_csv") if data else None
            if monitor:
                paths.append(Path(monitor))
            else:
                diagnostics.append(
                    {
                        "status": "error",
                        "input": item,
                        "source": str(path),
                        "error": f"JSON input does not contain monitor_csv: {path}",
                    }
                )
        elif path.is_dir():
            found = sorted(path.glob("episode-*/monitor.csv"))
            found.extend(sorted(path.glob("**/monitor.csv")))
            if found:
                paths.extend(found)
            else:
                diagnostics.append(
                    {
                        "status": "error",
                        "input": item,
                        "source": str(path),
                        "error": f"Directory does not contain any monitor.csv files: {path}",
                    }
                )
        else:
            diagnostics.append(
                {
                    "status": "skipped_input",
                    "input": item,
                    "source": str(path),
                    "reason": "Unsupported guard-probe input; expected CSV, result JSON, or directory.",
                }
            )
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path.resolve()) if path.exists() else str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique, diagnostics


def cmd_guard_probe(args: argparse.Namespace) -> int:
    rows: list[dict[str, Any]] = []
    monitor_paths, diagnostics = monitor_paths_from_args(args)
    rows.extend(diagnostics)
    for monitor_path in monitor_paths:
        if not monitor_path.exists():
            rows.append(
                {
                    "status": "error",
                    "monitor_csv": str(monitor_path),
                    "error": f"Monitor CSV not found: {monitor_path}",
                }
            )
            continue
        try:
            df = read_monitor_csv(monitor_path)
            metrics = guard_metrics_from_df(
                df,
                monitor_path,
                guard_soc_high=args.tes_guard_soc_high,
                guard_soc_low=args.tes_guard_soc_low,
            )
            metrics.update(tes_mechanism_metrics_from_df(df, args, monitor_path))
            actual_col = optional_any_column(df, GUARD_ACTUAL_VALVE_COLUMNS)
            actual_valve = numeric(df, actual_col) if actual_col else pd.Series(np.nan, index=df.index, dtype=float)
            soc = numeric(df, "TES_SOC")
            metrics.update(
                {
                    "status": "ok",
                    "monitor_csv": str(monitor_path),
                    "rows": int(len(df)),
                    "valve_mean_abs": float(actual_valve.abs().mean()) if actual_valve.notna().any() else None,
                    "valve_active_fraction": float((actual_valve.abs() > 0.05).mean()) if actual_valve.notna().any() else None,
                    "charge_fraction": float((actual_valve < -0.05).mean()) if actual_valve.notna().any() else None,
                    "discharge_fraction": float((actual_valve > 0.05).mean()) if actual_valve.notna().any() else None,
                    "soc_min": float(soc.min()) if soc.notna().any() else None,
                    "soc_mean": float(soc.mean()) if soc.notna().any() else None,
                    "soc_max": float(soc.max()) if soc.notna().any() else None,
                }
            )
            rows.append(metrics)
        except Exception as exc:
            rows.append({"status": "error", "monitor_csv": str(monitor_path), "error": str(exc)})

    if not rows:
        rows.append({"status": "no_inputs", "reason": "No monitor.csv files resolved from inputs."})
    summary_json, summary_csv = write_summary_files(args.out_dir, rows, "M2 guard probe")
    print(f"Wrote {summary_json}")
    print(f"Wrote {summary_csv}")
    has_ok = any(row.get("status") == "ok" for row in rows)
    has_error = any(row.get("status") != "ok" for row in rows)
    if args.strict and has_error:
        return 1
    return 0 if has_ok else 1


def rows_from_file(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        data = load_json(path)
        if data is None:
            return [{"status": "unreadable_json", "source": str(path)}]
        if isinstance(data.get("rows"), list):
            return [dict(row, source=str(path)) for row in data["rows"]]
        if path.name == "manifest.json" and isinstance(data.get("runs"), list):
            rows = []
            for row in data["runs"]:
                if isinstance(row, dict):
                    rows.append(
                        dict(
                            row,
                            status=row.get("status", "planned"),
                            action_dim=data.get("action_dim"),
                            tes_action_semantics=data.get("tes_action_semantics"),
                            tes_direction_deadband=data.get("tes_direction_deadband"),
                            tes_option_hold_steps=data.get("tes_option_hold_steps"),
                            provenance_metadata_missing=data.get("provenance_metadata_missing"),
                            provenance_metadata_sources=data.get("provenance_metadata_sources"),
                            checkpoint=data.get("checkpoint"),
                            workspace=data.get("workspace"),
                            source=str(path),
                        )
                    )
            return rows
        return [dict(data, source=str(path))]
    if path.suffix.lower() == ".csv":
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            return [dict(row, source=str(path)) for row in csv.DictReader(f)]
    return []


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        identity = {
            k: row.get(k)
            for k in [
                "monitor_csv",
                "checkpoint",
                "workspace",
                "tag",
                "design",
                "mode",
                "action_dim",
                "status",
            ]
            if row.get(k) not in (None, "")
        }
        if row.get("status") not in (None, "", "ok") and row.get("source"):
            identity["source"] = row.get("source")
        if not identity:
            identity = {k: v for k, v in row.items() if k != "source"}
        key = json.dumps(json_ready(identity), sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and not math.isfinite(value):
        return True
    if isinstance(value, str):
        return value.strip().lower() in ("", "none", "null", "nan")
    return False


def row_needs_p02_gate_fill(row: dict[str, Any]) -> bool:
    return any(is_missing_value(row.get(field)) for field in TES_MECHANISM_FIELDS)


def ensure_p02_gate_nulls(row: dict[str, Any]) -> None:
    for field in TES_MECHANISM_FIELDS:
        if is_missing_value(row.get(field)):
            row[field] = None


def resolve_monitor_csv(row: dict[str, Any]) -> tuple[Path | None, str | None]:
    monitor = row.get("monitor_csv")
    if is_missing_value(monitor):
        return None, "missing monitor_csv"

    raw = Path(str(monitor))
    candidates = [raw] if raw.is_absolute() else [ROOT / raw, raw]
    source = row.get("source")
    if not raw.is_absolute() and not is_missing_value(source):
        candidates.append(Path(str(source)).parent / raw)

    seen: set[str] = set()
    unique_candidates: list[Path] = []
    for candidate in candidates:
        key = str(candidate)
        if key not in seen:
            seen.add(key)
            unique_candidates.append(candidate)
    for candidate in unique_candidates:
        if candidate.exists():
            return candidate, None
    searched = ", ".join(str(candidate) for candidate in unique_candidates)
    return None, f"monitor_csv not found; searched: {searched}"


def p02_gate_column_notes(df: pd.DataFrame) -> list[str]:
    notes: list[str] = []
    required = ["TES_SOC", "price_current_norm"]
    missing_required = [col for col in required if col not in df.columns]
    if missing_required:
        notes.append(f"missing required gate columns: {missing_required}")
    if "price_hours_to_next_peak_norm" not in df.columns:
        notes.append("missing price_hours_to_next_peak_norm; low-price pre-peak metrics are null")
    if optional_any_column(df, GUARD_ACTUAL_VALVE_COLUMNS) is None:
        notes.append("missing actual valve column; sign-rate and sign-flip metrics are null")
    if optional_any_column(df, GUARD_RAW_TARGET_COLUMNS) is None:
        notes.append("missing raw target column; switch divergence metrics are null")
    return notes


def fill_p02_gate_metrics_from_monitor(rows: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    for row in rows:
        if not row_needs_p02_gate_fill(row):
            continue

        monitor_path, reason = resolve_monitor_csv(row)
        if monitor_path is None:
            ensure_p02_gate_nulls(row)
            row["p02_gate_metrics_status"] = "not_available"
            row["p02_gate_metrics_reason"] = reason
            status_counts["not_available"] = status_counts.get("not_available", 0) + 1
            continue

        try:
            df = read_monitor_csv(monitor_path)
            metrics = tes_mechanism_metrics_from_df(df, args, monitor_path)
            for key, value in metrics.items():
                if is_missing_value(row.get(key)):
                    row[key] = value
            ensure_p02_gate_nulls(row)
            notes = p02_gate_column_notes(df)
            row["p02_gate_metrics_status"] = "filled_from_monitor_csv"
            row["p02_gate_metrics_monitor_csv"] = str(monitor_path)
            if notes:
                row["p02_gate_metrics_reason"] = "; ".join(notes)
            status_counts["filled_from_monitor_csv"] = status_counts.get("filled_from_monitor_csv", 0) + 1
        except Exception as exc:
            ensure_p02_gate_nulls(row)
            row["p02_gate_metrics_status"] = "error"
            row["p02_gate_metrics_reason"] = str(exc)
            status_counts["error"] = status_counts.get("error", 0) + 1

    return {"status_counts": status_counts}


def row_cost_usd(row: dict[str, Any]) -> float | None:
    cost = finite_float(row.get("cost_usd"))
    return cost if cost is not None else finite_float(row.get("cost_usd_annual"))


def tag_without_mode(row: dict[str, Any]) -> str | None:
    tag = row.get("tag")
    mode = row.get("mode")
    if not tag or not mode:
        return None
    tag_text = str(tag)
    suffix = f"_{mode}"
    if tag_text.endswith(suffix):
        return tag_text[: -len(suffix)]
    return None


def counterfactual_pair_key(row: dict[str, Any]) -> dict[str, Any]:
    key_fields = [
        "action_dim",
        "design",
        "checkpoint",
        "workspace",
        "reward_cls",
        "max_steps",
    ]
    key = {field: row.get(field) for field in key_fields if row.get(field) not in (None, "")}
    tag_base = tag_without_mode(row)
    if tag_base:
        key["tag_base"] = tag_base
    return key


def compute_counterfactual_marginal_savings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, int]] = {}
    key_payloads: dict[str, dict[str, Any]] = {}
    for idx, row in enumerate(rows):
        if row.get("status") not in (None, "", "ok"):
            continue
        mode = row.get("mode")
        if mode not in ("full_learned", "learned_hvac_tes_zero"):
            continue
        key_payload = counterfactual_pair_key(row)
        key = json.dumps(json_ready(key_payload), sort_keys=True)
        grouped.setdefault(key, {})[str(mode)] = idx
        key_payloads[key] = key_payload

    pairs: list[dict[str, Any]] = []
    basis = (
        "cost_usd(learned_hvac_tes_zero) - cost_usd(full_learned); "
        "separate deterministic rollouts matched by checkpoint/design/workspace/tag_base when available"
    )
    for key, modes in grouped.items():
        if "full_learned" not in modes or "learned_hvac_tes_zero" not in modes:
            continue
        full_row = rows[modes["full_learned"]]
        zero_row = rows[modes["learned_hvac_tes_zero"]]
        full_cost = row_cost_usd(full_row)
        zero_cost = row_cost_usd(zero_row)
        if full_cost is None or zero_cost is None:
            continue
        saving = float(zero_cost - full_cost)
        for idx in modes.values():
            rows[idx]["tes_marginal_saving_usd"] = saving
            rows[idx]["tes_marginal_saving_basis"] = basis
            rows[idx]["tes_marginal_saving_pair_key"] = key
        pairs.append(
            {
                "pair_key": key_payloads[key],
                "full_learned_cost_usd": float(full_cost),
                "learned_hvac_tes_zero_cost_usd": float(zero_cost),
                "tes_marginal_saving_usd": saving,
                "basis": basis,
            }
        )
    return pairs


def aggregate_row_subset(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [row for row in rows if row.get("status") in (None, "", "ok")]
    grouped: dict[str, dict[str, Any]] = {}
    for key in ["design", "mode"]:
        values = sorted({str(row.get(key)) for row in ok if row.get(key) not in (None, "")})
        if values:
            grouped[key] = {"values": values, "count": len(values)}

    means: dict[str, float] = {}
    for field in CORE_FIELDS:
        vals = [finite_float(row.get(field)) for row in ok]
        vals = [v for v in vals if v is not None]
        if vals:
            means[f"{field}_mean"] = float(np.mean(vals))
    return {
        "row_count": len(rows),
        "ok_count": len(ok),
        "status_counts": dict(pd.Series([row.get("status", "ok") for row in rows]).value_counts()),
        "groups": grouped,
        "means": means,
    }


def aggregate_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    dims = sorted({str(row.get("action_dim", "unknown")) for row in rows})
    by_action_dim = {
        dim: aggregate_row_subset([row for row in rows if str(row.get("action_dim", "unknown")) == dim])
        for dim in dims
    }
    return {
        "row_count": len(rows),
        "status_counts": dict(pd.Series([row.get("status", "ok") for row in rows]).value_counts()),
        "action_dims": dims,
        "by_action_dim": by_action_dim,
    }


def summary_files_from_dir(path: Path) -> list[Path]:
    result_files = sorted(path.glob("**/result.json"))
    if result_files:
        return result_files
    manifest_files = sorted(path.glob("**/manifest.json"))
    if manifest_files:
        return manifest_files
    summary_json = sorted(path.glob("**/summary.json"))
    if summary_json:
        return summary_json
    return sorted(path.glob("**/summary.csv"))


def cmd_summarize(args: argparse.Namespace) -> int:
    rows: list[dict[str, Any]] = []
    for item in args.inputs:
        path = Path(item)
        if path.is_dir():
            files = summary_files_from_dir(path)
            for file_path in files:
                rows.extend(rows_from_file(file_path))
        elif path.exists():
            rows.extend(rows_from_file(path))
        else:
            rows.append({"status": "missing_input", "source": str(path)})

    if not rows:
        rows.append({"status": "no_inputs", "reason": "No JSON/CSV files found."})
    rows = dedupe_rows(rows)
    p02_gate_fill = fill_p02_gate_metrics_from_monitor(rows, args)
    counterfactual_pairs = compute_counterfactual_marginal_savings(rows)
    aggregate = aggregate_rows(rows)
    if p02_gate_fill["status_counts"]:
        aggregate["p02_gate_fill"] = p02_gate_fill
    if counterfactual_pairs:
        aggregate["counterfactual_marginal_savings"] = counterfactual_pairs

    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "aggregate": aggregate,
        "rows": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.out, payload)
    csv_path = args.out.with_suffix(".csv")
    fields = list(dict.fromkeys(CORE_FIELDS + ["source", "reason", "error"] + sorted({k for row in rows for k in row.keys()})))
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {args.out}")
    print(f"Wrote {csv_path}")
    print(json.dumps(json_ready(payload["aggregate"]), indent=2))
    return 0


def add_common_eval_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--tag", default=datetime.now().strftime("m2_validate_%Y%m%d-%H%M%S"))
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--reward-cls", default="rl_cost", choices=["pue_tes", "rl_cost", "rl_green"])
    ap.add_argument("--epw", default=DEFAULT_EPW)
    ap.add_argument("--price-csv", default=DEFAULT_PRICE_CSV)
    ap.add_argument("--pv-csv", default=DEFAULT_PV_CSV)
    ap.add_argument("--dc-peak-load-kw", type=float, default=6000.0)
    ap.add_argument("--max-steps", type=int, default=0, help="Optional early stop for smoke runs. A full episode also requires --allow-full-eval.")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--stochastic", action="store_true", help="Use stochastic model.predict for learned-policy branches.")
    ap.add_argument("--dry-run", action="store_true", help="Force planned output without starting EnergyPlus. This is also the default.")
    ap.add_argument("--run", action="store_true", help="Actually start EnergyPlus evaluation. Full episodes also require --allow-full-eval.")
    ap.add_argument("--confirm-run", action="store_true", help="Alias for --run for explicit post-review confirmation.")
    ap.add_argument("--allow-full-eval", action="store_true", help="Allow a full episode when --max-steps is 0.")
    ap.add_argument("--alpha", type=float, default=2e-3)
    ap.add_argument("--beta", type=float, default=1.0)
    ap.add_argument("--c-pv", type=float, default=0.0)
    ap.add_argument("--pv-threshold-kw", type=float, default=100.0)
    ap.add_argument("--kappa-shape", type=float, default=0.0)
    ap.add_argument("--gamma-pbrs", type=float, default=0.99)
    ap.add_argument("--tau-decay", type=float, default=4.0)
    ap.add_argument("--p-peak-ref", type=float, default=0.80)
    ap.add_argument("--tes-valve-rate-limit", type=float, default=0.25)
    ap.add_argument("--tes-guard-soc-low", type=float, default=0.10)
    ap.add_argument("--tes-guard-soc-high", type=float, default=0.90)
    ap.add_argument("--high-price-threshold", type=float, default=0.75)
    ap.add_argument("--low-price-threshold", type=float, default=-0.50)
    ap.add_argument("--near-peak-threshold", type=float, default=0.40)
    ap.add_argument("--soc-charge-limit", type=float, default=0.85)
    ap.add_argument("--soc-discharge-limit", type=float, default=0.25)
    ap.add_argument("--charge-target", type=float, default=0.85)
    ap.add_argument("--discharge-target", type=float, default=0.85)
    ap.add_argument("--enable-tes-state-augmentation", action="store_true")
    ap.add_argument("--tes-action-semantics", choices=["signed_scalar", "direction_amp", "direction_amp_hold"], default="signed_scalar")
    ap.add_argument("--tes-direction-deadband", type=float, default=0.15)
    ap.add_argument("--tes-option-hold-steps", type=int, default=4)
    ap.add_argument("--frozen-ct-pump-action", type=float, default=0.5)
    ap.add_argument("--frozen-crah-temp-action", type=float, default=0.5)
    ap.add_argument("--frozen-chiller-temp-action", type=float, default=0.5)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    paired = sub.add_parser("paired-eval", help="Run official/trainlike paired validation designs.")
    add_common_eval_args(paired)
    paired.add_argument(
        "--designs",
        nargs="+",
        default=["official", "official_soc05", "train_default", "trainlike_soc05"],
        choices=["official", "official_soc05", "train_default", "trainlike_soc05"],
    )
    paired.add_argument("--out-dir", type=Path, default=Path("runs/m2_validate_tes_failure_modes/paired_eval"))
    paired.set_defaults(func=cmd_paired_eval)

    guard = sub.add_parser("guard-probe", help="Probe raw TES target vs actual guarded valve from monitor/result paths.")
    guard.add_argument("inputs", nargs="+", help="monitor.csv, result.json, or directories containing monitor.csv.")
    guard.add_argument("--out-dir", type=Path, default=Path("runs/m2_validate_tes_failure_modes/guard_probe"))
    guard.add_argument("--tes-guard-soc-low", type=float, default=0.10)
    guard.add_argument("--tes-guard-soc-high", type=float, default=0.90)
    guard.add_argument("--high-price-threshold", type=float, default=0.75)
    guard.add_argument("--low-price-threshold", type=float, default=-0.50)
    guard.add_argument("--near-peak-threshold", type=float, default=0.40)
    guard.add_argument("--soc-charge-limit", type=float, default=0.85)
    guard.add_argument("--soc-discharge-limit", type=float, default=0.25)
    guard.add_argument("--no-strict", dest="strict", action="store_false", help="Return success when at least one input is ok, even if others fail.")
    guard.set_defaults(strict=True)
    guard.set_defaults(func=cmd_guard_probe)

    cf = sub.add_parser("counterfactual-eval", help="Run learned/rule TES-HVAC isolation evaluations.")
    add_common_eval_args(cf)
    cf.add_argument("--design", default="official", choices=["official", "official_soc05", "train_default", "trainlike_soc05"])
    cf.add_argument(
        "--modes",
        nargs="+",
        default=["full_learned", "learned_tes_frozen_hvac", "rule_tes_frozen_hvac", "learned_hvac_tes_zero"],
        choices=["full_learned", "learned_tes_frozen_hvac", "rule_tes_frozen_hvac", "learned_hvac_tes_zero"],
    )
    cf.add_argument("--out-dir", type=Path, default=Path("runs/m2_validate_tes_failure_modes/counterfactual_eval"))
    cf.set_defaults(func=cmd_counterfactual_eval)

    summ = sub.add_parser("summarize", help="Aggregate validation JSON/CSV metrics.")
    summ.add_argument("inputs", nargs="+", help="result.json, summary.json, summary.csv, or directories.")
    summ.add_argument("--out", type=Path, default=Path("runs/m2_validate_tes_failure_modes/summary.json"))
    summ.add_argument("--high-price-threshold", type=float, default=0.75)
    summ.add_argument("--low-price-threshold", type=float, default=-0.50)
    summ.add_argument("--near-peak-threshold", type=float, default=0.40)
    summ.add_argument("--soc-charge-limit", type=float, default=0.85)
    summ.add_argument("--soc-discharge-limit", type=float, default=0.25)
    summ.set_defaults(func=cmd_summarize)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    _normalize_data_paths(args)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
