"""M2-F1 TES-only MPC oracle evaluation.

This script runs the fixed-fan M2 environment with a deterministic TES planner.
It does not train or load any RL policy.  The exposed action is the M2-F1 4D
vector:

    [CT_Pump_DRL, CRAH_T_DRL, Chiller_T_DRL, TES_signed_target]

CRAH_Fan_DRL is inserted as a fixed full-environment action.  The TES sign
convention follows TESTargetValveWrapper:

    negative: charge cold storage
    positive: discharge cold storage
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")


def _ensure_pyenergyplus_path() -> None:
    try:
        from pyenergyplus.api import EnergyPlusAPI  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    candidates: list[Path] = []
    for env_name in ("ENERGYPLUS_DIR", "ENERGYPLUS_PATH"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(Path(value))
    candidates.extend(Path.home().glob("EnergyPlus-*/*"))
    for candidate in candidates:
        if not (candidate / "pyenergyplus").is_dir():
            continue
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
        os.environ.setdefault("EPLUS_PATH", candidate_str)
        os.environ.setdefault("ENERGYPLUS_PATH", candidate_str)
        os.environ["PATH"] = candidate_str + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(candidate_str)
            except OSError:
                pass
        try:
            from pyenergyplus.api import EnergyPlusAPI  # noqa: F401
            return
        except ModuleNotFoundError:
            continue


_ensure_pyenergyplus_path()

import gymnasium as gym
import numpy as np
import pandas as pd

from sinergym.envs.energy_scale_wrapper import EnergyScaleWrapper
from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
from sinergym.envs.pv_signal_wrapper import PVSignalWrapper
from sinergym.envs.temp_trend_wrapper import TempTrendWrapper
from sinergym.envs.tes_wrapper import FixedActionInsertWrapper, TESTargetValveWrapper
from sinergym.envs.time_encoding_wrapper import TimeEncodingWrapper
from sinergym.utils.common import get_ids
from tools.m2_action_guard import M2_FIXED_FAN_VALUE


DEFAULT_EPW = "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
DEFAULT_PRICE_CSV = "Data/prices/Jiangsu_TOU_2025_hourly.csv"
DEFAULT_PV_CSV = "Data/pv/CHN_Nanjing_PV_6MWp_hourly.csv"
M2_TIMESTEPS_PER_HOUR = 4
TES_TANK_M3 = 1400.0
TES_MAX_FLOW_KG_S = 389.0
SUMMARY_CSV = Path("analysis/m2f1_mpc_oracle_summary_202605.csv")
SUMMARY_JSON = Path("analysis/m2f1_mpc_oracle_summary_202605.json")

EVAL_DESIGNS = {
    "trainlike": {
        "building_file": "DRL_DC_training.epJSON",
        "evaluation_flag": 0,
        "ite_set": 0.45,
        "description": "M2-F1 in-distribution evaluation using the training load level.",
    },
    "official_ood": {
        "building_file": "DRL_DC_evaluation.epJSON",
        "evaluation_flag": 1,
        "ite_set": 1.0,
        "description": "High-load OOD stress evaluation, not the M2-F1 success gate.",
    },
}


@dataclass(frozen=True)
class PlannerDecision:
    target: float
    mode: str
    feasible: bool
    infeasible_reason: str
    solver_status: str = "heuristic"
    objective_terms: dict[str, float] | None = None
    optimizer_diagnostics: dict[str, Any] | None = None

    @property
    def amplitude(self) -> float:
        return abs(float(self.target))


@dataclass(frozen=True)
class SocDynamics:
    charge_gain_per_step: float
    discharge_gain_per_step: float
    source: str
    calibration_monitor: str | None
    sample_counts: dict[str, int]
    fallback_reason: str | None = None


def finite_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return number


def json_sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_sanitize(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if np.isfinite(number) else None
    return value


def build_env(args: argparse.Namespace) -> gym.Env:
    design = EVAL_DESIGNS[args.eval_design]
    env = gym.make(
        "Eplus-DC-Cooling-TES",
        env_name=f"{args.controller_type}-{args.tag}",
        building_file=design["building_file"],
        weather_files=args.epw,
        config_params={
            "runperiod": (1, 1, 2025, 31, 12, 2025),
            "timesteps_per_hour": M2_TIMESTEPS_PER_HOUR,
        },
        evaluation_flag=design["evaluation_flag"],
    )
    env = TESTargetValveWrapper(
        env,
        valve_idx=4,
        rate_limit=args.tes_valve_rate_limit,
        soc_low_guard=args.tes_guard_soc_low,
        soc_high_guard=args.tes_guard_soc_high,
    )
    env = FixedActionInsertWrapper(
        env,
        fixed_actions={0: args.fan_action},
        fixed_action_names={0: "CRAH_Fan_DRL"},
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
    return env


def attach_reward(env: gym.Env, args: argparse.Namespace) -> gym.Env:
    if args.reward_cls == "pue_tes":
        return env

    from sinergym.utils.rewards import RL_Cost_Reward, RL_Green_Reward

    price = pd.read_csv(args.price_csv)["price_usd_per_mwh"].to_numpy(dtype=np.float32)
    pv = pd.read_csv(args.pv_csv)["power_kw"].to_numpy(dtype=np.float32)
    kwargs = dict(
        temperature_variables=["air_temperature"],
        energy_variables=["Electricity:Facility"],
        ITE_variables=["ITE-CPU:InteriorEquipment:Electricity"],
        range_comfort_winter=(18.0, 25.0),
        range_comfort_summer=(18.0, 25.0),
        energy_weight=0.5,
        lambda_energy=1.0,
        lambda_temperature=1.0,
        soc_variable="TES_SOC",
        soc_low=0.15,
        soc_high=0.85,
        soc_warn_low=0.15,
        soc_warn_high=0.85,
        lambda_soc=2.0,
        lambda_soc_warn=1.0,
        price_series=price,
        alpha=args.alpha,
        beta=args.beta,
        kappa_shape=args.kappa_shape,
        gamma_pbrs=args.gamma_pbrs,
        tau_decay=args.tau_decay,
        p_peak_ref=args.p_peak_ref,
    )
    if args.reward_cls == "rl_cost":
        cls = RL_Cost_Reward
    else:
        cls = RL_Green_Reward
        kwargs["pv_series"] = pv
        kwargs["c_pv"] = args.c_pv
        kwargs["pv_threshold_kw"] = args.pv_threshold_kw

    eplus_env = env.unwrapped
    if not hasattr(eplus_env, "reward_fn"):
        raise RuntimeError(f"env.unwrapped={type(eplus_env).__name__} has no reward_fn")
    eplus_env.reward_fn = cls(**kwargs)
    return env


def obs_map(obs: np.ndarray, names: list[str]) -> dict[str, float]:
    if not np.all(np.isfinite(obs)):
        bad = [names[i] if i < len(names) else str(i) for i, v in enumerate(obs) if not np.isfinite(v)]
        raise RuntimeError(f"Non-finite observation values: {bad}")
    return {name: float(obs[i]) for i, name in enumerate(names)}


def plan_tes_action_heuristic(obs_values: dict[str, float], args: argparse.Namespace) -> PlannerDecision:
    soc = obs_values.get("TES_SOC")
    price = obs_values.get("price_current_norm")
    hours_to_peak = obs_values.get("price_hours_to_next_peak_norm")
    if soc is None or price is None or hours_to_peak is None:
        return PlannerDecision(0.0, "hold", False, "missing_required_observation")

    target = 0.0
    mode = "hold"
    if price >= args.high_price_threshold:
        if soc > args.soc_discharge_limit:
            target = args.discharge_target
            mode = "discharge"
        else:
            return PlannerDecision(0.0, "hold", False, "soc_discharge_limit_empty")
    elif price <= args.low_price_threshold and hours_to_peak <= args.near_peak_threshold:
        if soc < args.soc_charge_limit:
            target = -args.charge_target
            mode = "charge"
        else:
            return PlannerDecision(0.0, "hold", False, "soc_charge_limit_full")
    else:
        error = args.terminal_soc_target - soc
        correction = min(args.charge_target, args.discharge_target) * 0.35
        if error > 0.08 and soc < args.soc_charge_limit and price < args.high_price_threshold:
            target = -correction
            mode = "terminal_charge"
        elif error < -0.08 and soc > args.soc_discharge_limit and price > args.low_price_threshold:
            target = correction
            mode = "terminal_discharge"

    feasible = True
    reason = ""
    if target < 0.0 and soc >= args.tes_guard_soc_high:
        feasible = False
        reason = "soc_high_guard"
    elif target > 0.0 and soc <= args.tes_guard_soc_low:
        feasible = False
        reason = "soc_low_guard"
    return PlannerDecision(float(target), mode, feasible, reason)


def plan_tes_action(obs_values: dict[str, float], args: argparse.Namespace) -> PlannerDecision:
    return plan_tes_action_heuristic(obs_values, args)


def _candidate_calibration_monitors(args: argparse.Namespace) -> list[Path]:
    candidates: list[Path] = []
    explicit = getattr(args, "soc_calibration_monitor", None)
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend(
        [
            Path("runs/m2_tes_mpc_oracle/m2f1_mpc_oracle_672/monitor.csv"),
            Path("runs/m2_mpc_lite/m2f1_mpc_lite_672/monitor.csv"),
        ]
    )
    return candidates


def _calibrate_from_monitor(path: Path) -> SocDynamics | None:
    if not path.exists():
        return None
    df = pd.read_csv(path)
    if "TES_SOC" not in df:
        return None
    valve_col = "TES_valve_wrapper_position" if "TES_valve_wrapper_position" in df else None
    if valve_col is None and "tes_valve_position" in df:
        valve_col = "tes_valve_position"
    if valve_col is None:
        return None

    soc = pd.to_numeric(df["TES_SOC"], errors="coerce")
    valve = pd.to_numeric(df[valve_col], errors="coerce")
    delta = soc.shift(-1) - soc
    valid = soc.notna() & valve.notna() & delta.notna()
    deadband = 0.05
    charge_mask = valid & (valve < -deadband) & (delta > 0.0)
    discharge_mask = valid & (valve > deadband) & (delta < 0.0)

    def fit(mask: pd.Series, sign: float) -> float | None:
        x = valve[mask].to_numpy(dtype=np.float64)
        y = (sign * delta[mask]).to_numpy(dtype=np.float64)
        if len(x) < 8:
            return None
        denom = float(np.dot(x, x))
        if denom <= 0.0:
            return None
        gain = float(np.dot(np.abs(x), y) / denom)
        if not np.isfinite(gain) or gain <= 0.0:
            return None
        return gain

    charge_gain = fit(charge_mask, 1.0)
    discharge_gain = fit(discharge_mask, -1.0)
    if charge_gain is None or discharge_gain is None:
        return None
    return SocDynamics(
        charge_gain_per_step=charge_gain,
        discharge_gain_per_step=discharge_gain,
        source="monitor_calibration",
        calibration_monitor=str(path),
        sample_counts={
            "charge": int(charge_mask.sum()),
            "discharge": int(discharge_mask.sum()),
        },
    )


def _physical_soc_dynamics_fallback(reason: str) -> SocDynamics:
    timestep_s = 3600.0 / M2_TIMESTEPS_PER_HOUR
    tank_mass_kg = TES_TANK_M3 * 1000.0
    gain = TES_MAX_FLOW_KG_S * timestep_s / tank_mass_kg
    return SocDynamics(
        charge_gain_per_step=float(gain),
        discharge_gain_per_step=float(gain),
        source="physical_capacity_fallback",
        calibration_monitor=None,
        sample_counts={"charge": 0, "discharge": 0},
        fallback_reason=reason,
    )


def resolve_soc_dynamics(args: argparse.Namespace) -> SocDynamics:
    charge_cli = getattr(args, "soc_charge_gain", None)
    discharge_cli = getattr(args, "soc_discharge_gain", None)
    if charge_cli is not None or discharge_cli is not None:
        if charge_cli is None or discharge_cli is None:
            raise RuntimeError("--soc-charge-gain and --soc-discharge-gain must be provided together.")
        if charge_cli <= 0.0 or discharge_cli <= 0.0:
            raise RuntimeError("SOC gains must be positive.")
        return SocDynamics(
            charge_gain_per_step=float(charge_cli),
            discharge_gain_per_step=float(discharge_cli),
            source="cli",
            calibration_monitor=None,
            sample_counts={"charge": 0, "discharge": 0},
        )

    failed: list[str] = []
    for candidate in _candidate_calibration_monitors(args):
        dynamics = _calibrate_from_monitor(candidate)
        if dynamics is not None:
            return dynamics
        failed.append(str(candidate))
    return _physical_soc_dynamics_fallback(
        "No usable monitor calibration found; tried: " + "; ".join(failed)
    )


def _expanded_price_series(args: argparse.Namespace, horizon_steps: int, step_idx: int) -> np.ndarray:
    hourly = pd.read_csv(args.price_csv)["price_usd_per_mwh"].to_numpy(dtype=np.float64)
    if hourly.size == 0:
        raise RuntimeError(f"Empty price CSV: {args.price_csv}")
    step_indices = (np.arange(step_idx, step_idx + horizon_steps) // M2_TIMESTEPS_PER_HOUR) % hourly.size
    return _apply_forecast_noise(
        hourly[step_indices],
        args=args,
        step_idx=step_idx,
        stream_name="price_series",
    )


def _forecast_noise_stream_seed(base_seed: int, step_idx: int, stream_name: str) -> int:
    stream_offset = sum((idx + 1) * ord(char) for idx, char in enumerate(stream_name))
    return int(base_seed + step_idx * 1009 + stream_offset)


def _apply_forecast_noise(
    values: np.ndarray,
    args: argparse.Namespace,
    step_idx: int,
    stream_name: str,
    *,
    preserve_current_step: bool = True,
) -> np.ndarray:
    forecast_mode = getattr(args, "forecast_noise_mode", "perfect")
    series = np.asarray(values, dtype=np.float64)
    if series.size == 0 or forecast_mode == "perfect":
        return series.copy()

    output = series.copy()
    start_idx = 1 if preserve_current_step else 0
    if start_idx >= output.size:
        return output

    if forecast_mode == "gaussian":
        sigma = max(0.0, float(getattr(args, "forecast_noise_sigma", 0.0)))
        if sigma == 0.0:
            return output
        rng = np.random.RandomState(
            _forecast_noise_stream_seed(int(getattr(args, "forecast_noise_seed", 0)), step_idx, stream_name)
        )
        noise = rng.normal(loc=0.0, scale=sigma, size=output.size - start_idx)
        output[start_idx:] = output[start_idx:] * (1.0 + noise)
        return output

    if forecast_mode == "persistence_h":
        lag_steps = max(1, int(getattr(args, "forecast_noise_persist_h", 1)) * M2_TIMESTEPS_PER_HOUR)
        for idx in range(start_idx, output.size):
            output[idx] = series[max(0, idx - lag_steps)]
        return output

    raise RuntimeError(f"Unsupported forecast noise mode: {forecast_mode}")


def _price_feature_cache(args: argparse.Namespace) -> dict[str, np.ndarray]:
    hourly = pd.read_csv(args.price_csv)["price_usd_per_mwh"].to_numpy(dtype=np.float64)
    if hourly.size != 8760:
        raise RuntimeError(f"Price CSV must have 8760 rows for wrapper-aligned features, got {hourly.size}")
    std = max(float(np.std(hourly)), 1.0e-6)
    norm = np.clip((hourly - float(np.mean(hourly))) / std, -1.0, 2.0)
    peak_threshold = float(np.percentile(hourly, 75.0))
    peak_mask = hourly >= peak_threshold
    hours_to_peak = np.zeros(8760, dtype=np.float64)
    if peak_mask.any():
        for h in range(8760):
            if peak_mask[h]:
                continue
            for k in range(1, 8761):
                if peak_mask[(h + k) % 8760]:
                    hours_to_peak[h] = float(k)
                    break
        max_gap = max(float(hours_to_peak.max()), 1.0)
    else:
        max_gap = 1.0
    return {
        "price": hourly,
        "norm": norm.astype(np.float64),
        "hours_to_peak_norm": (hours_to_peak / max_gap).astype(np.float64),
        "_price_mean": np.asarray([float(np.mean(hourly))], dtype=np.float64),
        "_price_std": np.asarray([std], dtype=np.float64),
    }


def _expanded_price_features(
    args: argparse.Namespace,
    planner_state: dict[str, Any],
    horizon_steps: int,
    step_idx: int,
) -> dict[str, np.ndarray]:
    cache = planner_state.get("price_feature_cache")
    if cache is None:
        cache = _price_feature_cache(args)
        planner_state["price_feature_cache"] = cache

    forecast_mode = getattr(args, "forecast_noise_mode", "perfect")
    hour_indices = (np.arange(step_idx, step_idx + horizon_steps) // M2_TIMESTEPS_PER_HOUR) % 8760
    perfect_price = np.asarray(cache["price"][hour_indices], dtype=np.float64)
    perfect_hours_to_peak = np.asarray(cache["hours_to_peak_norm"][hour_indices], dtype=np.float64)
    perfect_norm = np.asarray(cache["norm"][hour_indices], dtype=np.float64)
    if forecast_mode == "perfect":
        return {
            "price": perfect_price,
            "norm": perfect_norm,
            "hours_to_peak_norm": perfect_hours_to_peak,
        }

    noisy_price = _apply_forecast_noise(
        perfect_price,
        args=args,
        step_idx=step_idx,
        stream_name="price_features",
    )
    price_mean = float(np.asarray(cache["_price_mean"], dtype=np.float64)[0])
    price_std = max(float(np.asarray(cache["_price_std"], dtype=np.float64)[0]), 1.0e-6)
    noisy_norm = np.clip((noisy_price - price_mean) / price_std, -1.0, 2.0)
    noisy_hours_to_peak = (
        _apply_forecast_noise(
            perfect_hours_to_peak,
            args=args,
            step_idx=step_idx,
            stream_name="price_hours_to_peak",
        )
        if forecast_mode == "persistence_h"
        else perfect_hours_to_peak
    )
    return {
        "price": noisy_price,
        "norm": noisy_norm.astype(np.float64),
        "hours_to_peak_norm": np.asarray(noisy_hours_to_peak, dtype=np.float64),
    }


def plan_tes_action_scipy_highs(
    obs_values: dict[str, float],
    args: argparse.Namespace,
    planner_state: dict[str, Any],
    step_idx: int,
) -> PlannerDecision:
    if getattr(args, "comfort_risk_weight", 0.0) != 0.0:
        raise RuntimeError(
            "comfort_risk_penalty is recorded as a zero-weight placeholder in this milestone; "
            "nonzero --comfort-risk-weight is not implemented."
        )
    try:
        from scipy.optimize import linprog
    except Exception as exc:
        raise RuntimeError("solver=scipy-highs requested, but scipy.optimize.linprog is unavailable.") from exc

    soc0 = obs_values.get("TES_SOC")
    if soc0 is None or not np.isfinite(soc0):
        return PlannerDecision(0.0, "hold", False, "missing_tes_soc", "scipy-highs:no_soc")

    dynamics = planner_state["soc_dynamics"]
    horizon_steps = max(1, int(round(float(args.horizon_hours) * M2_TIMESTEPS_PER_HOUR)))
    price_features = _expanded_price_features(args, planner_state, horizon_steps, step_idx)
    price_norm = price_features["norm"]
    hours_to_peak = price_features["hours_to_peak_norm"]
    low_window = price_norm <= float(args.low_price_threshold)
    high_window = price_norm >= float(args.high_price_threshold)
    low_prepeak_window = low_window & (hours_to_peak <= float(args.near_peak_threshold))
    strict_soc_min = float(args.tes_guard_soc_low)
    strict_soc_max = float(args.tes_guard_soc_high)
    planning_soc_min = float(getattr(args, "soc_planning_min", getattr(args, "optimizer_soc_min", strict_soc_min)))
    planning_soc_max = float(getattr(args, "soc_planning_max", getattr(args, "optimizer_soc_max", strict_soc_max)))
    safety_margin = max(0.0, float(args.soc_safety_margin))
    actual_low_protect = float(soc0) <= planning_soc_min + safety_margin
    actual_high_protect = float(soc0) >= planning_soc_max - safety_margin
    strict_low_recovery = float(soc0) < strict_soc_min
    strict_high_recovery = float(soc0) > strict_soc_max
    safety_override = ""
    safety_recovery = False
    if actual_low_protect:
        safety_override = "low_soc_protect"
    if actual_high_protect:
        safety_override = "high_soc_protect" if not safety_override else f"{safety_override};high_soc_protect"
    if strict_low_recovery or strict_high_recovery:
        safety_recovery = True

    n = horizon_steps
    idx_pos = 0
    idx_neg = idx_pos + n
    idx_switch = idx_neg + n
    idx_terminal = idx_switch + n
    idx_soc_hi_slack = idx_terminal + 1
    idx_soc_lo_slack = idx_soc_hi_slack + n
    idx_soc_schedule_slack = idx_soc_lo_slack + n
    var_count = idx_soc_schedule_slack + n
    c = np.zeros(var_count, dtype=np.float64)
    pos_cost = -float(args.electricity_cost_weight) * price_norm + float(args.neutral_action_penalty)
    neg_cost = float(args.electricity_cost_weight) * price_norm + float(args.neutral_action_penalty)
    pos_cost[high_window] -= float(args.high_price_discharge_reward)
    neg_cost[low_prepeak_window] -= float(args.low_prepeak_charge_reward)
    pos_cost[low_window] += float(args.low_price_discharge_penalty)
    neg_cost[high_window] += float(args.high_price_charge_penalty)
    c[idx_pos:idx_pos + n] = pos_cost
    c[idx_neg:idx_neg + n] = neg_cost
    c[idx_switch:idx_switch + n] = float(args.switch_penalty)
    c[idx_terminal] = float(args.terminal_soc_weight)
    c[idx_soc_hi_slack:idx_soc_hi_slack + n] = float(args.soc_bound_penalty)
    c[idx_soc_lo_slack:idx_soc_lo_slack + n] = float(args.soc_bound_penalty)
    c[idx_soc_schedule_slack:idx_soc_schedule_slack + n] = float(args.soc_schedule_weight)

    discharge_limit = max(0.0, float(args.discharge_target))
    charge_limit = max(0.0, float(args.charge_target))
    prev_target = float(planner_state.get("last_target", 0.0))
    rate = max(0.0, float(args.tes_valve_rate_limit))
    pos_bounds: list[tuple[float, float | None]] = [(0.0, discharge_limit) for _ in range(n)]
    neg_bounds: list[tuple[float, float | None]] = [(0.0, charge_limit) for _ in range(n)]
    for k in range(n):
        if low_window[k] and not (k == 0 and strict_high_recovery):
            pos_bounds[k] = (0.0, 0.0)
        if high_window[k] and not (k == 0 and strict_low_recovery):
            neg_bounds[k] = (0.0, 0.0)
    if actual_low_protect:
        pos_bounds[0] = (0.0, 0.0)
    if actual_high_protect:
        neg_bounds[0] = (0.0, 0.0)

    def ensure_upper_bound(
        bounds_list: list[tuple[float, float | None]],
        index: int,
        minimum_upper: float,
    ) -> None:
        old_lower, old_upper = bounds_list[index]
        if old_upper is None or old_upper >= minimum_upper:
            return
        bounds_list[index] = (old_lower, float(minimum_upper))

    def set_lower_bound(
        bounds_list: list[tuple[float, float | None]],
        index: int,
        lower: float,
    ) -> None:
        old_lower, old_upper = bounds_list[index]
        if old_upper is not None and lower > old_upper + 1.0e-12:
            return
        bounds_list[index] = (max(float(old_lower), float(lower)), old_upper)

    max_discharge_by_rate = max(0.0, prev_target + rate)
    max_charge_by_rate = max(0.0, rate - prev_target)
    unavoidable_discharge_by_rate = max(0.0, prev_target - rate)
    unavoidable_charge_by_rate = max(0.0, -prev_target - rate)
    if unavoidable_discharge_by_rate > 1.0e-9:
        ensure_upper_bound(pos_bounds, 0, min(unavoidable_discharge_by_rate, discharge_limit))
        if low_window[0] or actual_low_protect:
            safety_recovery = True
            label = "rate_limit_unwind_discharge"
            safety_override = label if not safety_override else f"{safety_override};{label}"
    if unavoidable_charge_by_rate > 1.0e-9:
        ensure_upper_bound(neg_bounds, 0, min(unavoidable_charge_by_rate, charge_limit))
        if high_window[0] or actual_high_protect:
            safety_recovery = True
            label = "rate_limit_unwind_charge"
            safety_override = label if not safety_override else f"{safety_override};{label}"
    max_discharge_by_soc = max(0.0, (float(soc0) - planning_soc_min) / dynamics.discharge_gain_per_step)
    max_charge_by_soc = max(0.0, (planning_soc_max - float(soc0)) / dynamics.charge_gain_per_step)
    if strict_high_recovery:
        min_discharge = min(float(args.high_price_min_discharge), discharge_limit, max_discharge_by_rate)
        if min_discharge > 1.0e-9:
            set_lower_bound(pos_bounds, 0, min_discharge)
    elif high_window[0] and float(soc0) > float(args.soc_discharge_limit) and not actual_low_protect:
        min_discharge = min(
            float(args.high_price_min_discharge),
            discharge_limit,
            max_discharge_by_rate,
            max_discharge_by_soc,
        )
        if min_discharge > 1.0e-9:
            set_lower_bound(pos_bounds, 0, min_discharge)
    if strict_low_recovery:
        min_charge = min(float(args.low_prepeak_min_charge), charge_limit, max_charge_by_rate)
        if min_charge > 1.0e-9:
            set_lower_bound(neg_bounds, 0, min_charge)
    elif low_prepeak_window[0] and float(soc0) < float(args.soc_charge_limit) and not actual_high_protect:
        min_charge = min(
            float(args.low_prepeak_min_charge),
            charge_limit,
            max_charge_by_rate,
            max_charge_by_soc,
        )
        if min_charge > 1.0e-9:
            set_lower_bound(neg_bounds, 0, min_charge)
    bounds: list[tuple[float, float | None]] = (
        pos_bounds
        + neg_bounds
        + [(0.0, None)] * n
        + [(0.0, None)]
        + [(0.0, None)] * n
        + [(0.0, None)] * n
        + [(0.0, None)] * n
    )

    a_ub: list[np.ndarray] = []
    b_ub: list[float] = []

    def soc_row(k: int) -> np.ndarray:
        row = np.zeros(var_count, dtype=np.float64)
        row[idx_neg:idx_neg + k] = dynamics.charge_gain_per_step
        row[idx_pos:idx_pos + k] = -dynamics.discharge_gain_per_step
        return row

    soc_min_config = planning_soc_min
    soc_max_config = planning_soc_max
    soc_min = soc_min_config
    soc_max = soc_max_config
    for k in range(1, n + 1):
        row = soc_row(k)
        row[idx_soc_hi_slack + k - 1] = -1.0
        a_ub.append(row)
        b_ub.append(soc_max - float(soc0))
        low_row = -soc_row(k)
        low_row[idx_soc_lo_slack + k - 1] = -1.0
        a_ub.append(low_row)
        b_ub.append(float(soc0) - soc_min)

    desired_soc = np.full(n, float(args.terminal_soc_target), dtype=np.float64)
    desired_soc[high_window] = float(args.high_price_soc_target)
    has_future_prepeak = np.maximum.accumulate(low_prepeak_window[::-1])[::-1].astype(bool)
    desired_soc[has_future_prepeak & ~low_window & ~high_window] = float(args.reserve_headroom_soc_target)
    desired_soc[low_prepeak_window] = float(args.low_prepeak_soc_target)
    desired_soc = np.clip(desired_soc, soc_min_config, soc_max_config)
    for k in range(1, n + 1):
        row = soc_row(k)
        row[idx_soc_schedule_slack + k - 1] = -1.0
        a_ub.append(row)
        b_ub.append(float(desired_soc[k - 1]) - float(soc0))
        low_track_row = -soc_row(k)
        low_track_row[idx_soc_schedule_slack + k - 1] = -1.0
        a_ub.append(low_track_row)
        b_ub.append(float(soc0) - float(desired_soc[k - 1]))

    for k in range(n):
        row = np.zeros(var_count, dtype=np.float64)
        row[idx_pos + k] = 1.0
        row[idx_neg + k] = -1.0
        if k == 0:
            a_ub.append(row)
            b_ub.append(prev_target + rate)
            a_ub.append(-row)
            b_ub.append(rate - prev_target)
        else:
            row[idx_pos + k - 1] -= 1.0
            row[idx_neg + k - 1] += 1.0
            a_ub.append(row)
            b_ub.append(rate)
            a_ub.append(-row)
            b_ub.append(rate)

        diff_row = np.zeros(var_count, dtype=np.float64)
        diff_row[idx_pos + k] = 1.0
        diff_row[idx_neg + k] = -1.0
        if k > 0:
            diff_row[idx_pos + k - 1] -= 1.0
            diff_row[idx_neg + k - 1] += 1.0
            baseline = 0.0
        else:
            baseline = prev_target
        switch_row_pos = diff_row.copy()
        switch_row_pos[idx_switch + k] = -1.0
        a_ub.append(switch_row_pos)
        b_ub.append(baseline)
        switch_row_neg = -diff_row
        switch_row_neg[idx_switch + k] = -1.0
        a_ub.append(switch_row_neg)
        b_ub.append(-baseline)

        mutual_row = np.zeros(var_count, dtype=np.float64)
        mutual_row[idx_pos + k] = 1.0
        mutual_row[idx_neg + k] = 1.0
        a_ub.append(mutual_row)
        b_ub.append(max(charge_limit, discharge_limit))

    terminal = soc_row(n)
    terminal_target = float(args.terminal_soc_target)
    terminal_tol = max(0.0, float(args.terminal_soc_tolerance))
    terminal[idx_terminal] = -1.0
    a_ub.append(terminal)
    b_ub.append(terminal_target + terminal_tol - float(soc0))
    terminal_neg = -soc_row(n)
    terminal_neg[idx_terminal] = -1.0
    a_ub.append(terminal_neg)
    b_ub.append(float(soc0) - terminal_target + terminal_tol)

    res = linprog(
        c,
        A_ub=np.vstack(a_ub),
        b_ub=np.asarray(b_ub, dtype=np.float64),
        bounds=bounds,
        method="highs",
    )
    if not res.success or res.x is None:
        raise RuntimeError(f"scipy-highs failed at step {step_idx}: status={res.status}, message={res.message}")

    u_pos = float(res.x[idx_pos])
    u_neg = float(res.x[idx_neg])
    target = float(np.clip(u_pos - u_neg, -charge_limit, discharge_limit))
    if target < -0.05:
        mode = "charge"
    elif target > 0.05:
        mode = "discharge"
    else:
        mode = "hold"
    feasible = True
    reason = ""
    if target < 0.0 and actual_high_protect:
        feasible = False
        reason = safety_override or "high_soc_protect"
        target = 0.0
        mode = "hold"
    elif target > 0.0 and actual_low_protect:
        feasible = False
        reason = safety_override or "low_soc_protect"
        target = 0.0
        mode = "hold"
    objective_terms = {
        "electricity_cost_proxy": float(
            np.dot(price_norm, res.x[idx_neg:idx_neg + n] - res.x[idx_pos:idx_pos + n])
        ),
        "switch_penalty": float(args.switch_penalty) * float(np.sum(res.x[idx_switch:idx_switch + n])),
        "terminal_soc_penalty": float(args.terminal_soc_weight) * float(res.x[idx_terminal]),
        "soc_bound_penalty": float(args.soc_bound_penalty)
        * float(
            np.sum(res.x[idx_soc_hi_slack:idx_soc_hi_slack + n])
            + np.sum(res.x[idx_soc_lo_slack:idx_soc_lo_slack + n])
        ),
        "soc_schedule_penalty": float(args.soc_schedule_weight)
        * float(np.sum(res.x[idx_soc_schedule_slack:idx_soc_schedule_slack + n])),
        "comfort_risk_penalty": 0.0,
    }
    predicted_soc = (
        float(soc0)
        + np.cumsum(res.x[idx_neg:idx_neg + n]) * dynamics.charge_gain_per_step
        - np.cumsum(res.x[idx_pos:idx_pos + n]) * dynamics.discharge_gain_per_step
    )
    soc_hi_slack = res.x[idx_soc_hi_slack:idx_soc_hi_slack + n]
    soc_lo_slack = res.x[idx_soc_lo_slack:idx_soc_lo_slack + n]
    terminal_abs_slack = abs(float(predicted_soc[-1]) - float(args.terminal_soc_target))
    diagnostics = {
        "soc_hi_slack_sum": float(np.sum(soc_hi_slack)),
        "soc_hi_slack_max": float(np.max(soc_hi_slack)) if len(soc_hi_slack) else 0.0,
        "soc_hi_slack_first_step": int(np.argmax(soc_hi_slack > 1.0e-9)) if np.any(soc_hi_slack > 1.0e-9) else None,
        "soc_lo_slack_sum": float(np.sum(soc_lo_slack)),
        "soc_lo_slack_max": float(np.max(soc_lo_slack)) if len(soc_lo_slack) else 0.0,
        "soc_lo_slack_first_step": int(np.argmax(soc_lo_slack > 1.0e-9)) if np.any(soc_lo_slack > 1.0e-9) else None,
        "terminal_abs_slack": terminal_abs_slack,
        "predicted_soc_1": float(predicted_soc[0]),
        "predicted_soc_n": float(predicted_soc[-1]),
        "predicted_soc_min": float(np.min(predicted_soc)),
        "predicted_soc_max": float(np.max(predicted_soc)),
        "current_low_price_window": bool(low_window[0]),
        "current_low_prepeak_window": bool(low_prepeak_window[0]),
        "current_high_price_window": bool(high_window[0]),
        "desired_soc_1": float(desired_soc[0]),
        "desired_soc_n": float(desired_soc[-1]),
        "safety_override": safety_override,
        "safety_recovery": bool(safety_recovery),
        "initial_out_of_bounds": bool(step_idx == 0 and (strict_low_recovery or strict_high_recovery)),
        "planning_soc_min": planning_soc_min,
        "planning_soc_max": planning_soc_max,
    }
    if low_prepeak_window[0] and float(soc0) >= float(args.soc_charge_limit) and target >= -0.05:
        feasible = False
        reason = "soc_charge_limit_full"
    return PlannerDecision(
        target=target,
        mode=mode,
        feasible=feasible,
        infeasible_reason=reason,
        solver_status="optimal",
        objective_terms=objective_terms,
        optimizer_diagnostics=diagnostics,
    )


def prepare_planner(args: argparse.Namespace) -> dict[str, Any]:
    state: dict[str, Any] = {"last_target": 0.0}
    requested_solver = getattr(args, "solver", "milp")
    if requested_solver == "lp_highs":
        state["planner_fn"] = plan_tes_action_scipy_highs
        state["solver_used"] = "lp_highs"
        state["solver_status"] = "lp_highs"
    elif requested_solver == "milp":
        # W1-0 keeps the default CLI stable until the MILP path lands in W1-2.
        state["planner_fn"] = plan_tes_action_scipy_highs
        state["solver_used"] = "lp_highs"
        state["solver_status"] = "milp_not_implemented_fallback_lp_highs"
        print("WARNING: --solver milp requested before W1-2; temporarily falling back to lp_highs.")
    else:
        state["planner_fn"] = plan_tes_action_heuristic
        state["solver_used"] = "heuristic"
        state["solver_status"] = "heuristic"

    args.solver_used = str(state["solver_used"])
    args.solver_status = str(state["solver_status"])
    if str(state["solver_used"]) == "lp_highs":
        state["soc_dynamics"] = resolve_soc_dynamics(args)
    return state


def plan_controller_action(
    obs_values: dict[str, float],
    args: argparse.Namespace,
    planner_state: dict[str, Any],
    step_idx: int,
) -> PlannerDecision:
    planner_fn = planner_state["planner_fn"]
    if planner_fn is plan_tes_action_scipy_highs:
        return plan_tes_action_scipy_highs(obs_values, args, planner_state, step_idx)
    return planner_fn(obs_values, args)


def action_from_decision(decision: PlannerDecision, args: argparse.Namespace) -> np.ndarray:
    return np.asarray(
        [
            args.ct_pump_action,
            args.crah_temp_action,
            args.chiller_temp_action,
            decision.target,
        ],
        dtype=np.float32,
    )


def _info_value(info: dict[str, Any], key: str) -> Any:
    value = info.get(key)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def make_monitor_row(
    step_idx: int,
    obs_values: dict[str, float],
    action: np.ndarray,
    decision: PlannerDecision,
    reward: float,
    terminated: bool,
    truncated: bool,
    info: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    if not np.isfinite(reward):
        raise RuntimeError(f"Non-finite reward at step {step_idx}: {reward}")
    row: dict[str, Any] = {"step": step_idx, **obs_values}
    row.update(
        {
            "CT_Pump_DRL": float(action[0]),
            "CRAH_T_DRL": float(action[1]),
            "Chiller_T_DRL": float(action[2]),
            "TES_DRL": float(action[3]),
            "forecast_noise_mode": getattr(args, "forecast_noise_mode", "perfect"),
            "forecast_noise_sigma": float(getattr(args, "forecast_noise_sigma", 0.0)),
            "forecast_noise_seed": int(getattr(args, "forecast_noise_seed", 0)),
            "forecast_noise_persist_h": int(getattr(args, "forecast_noise_persist_h", 1)),
            "tes_mpc_mode_label": decision.mode,
            "tes_mpc_amp_label": decision.amplitude,
            "tes_mpc_signed_target_label": decision.target,
            "tes_mpc_feasible": bool(decision.feasible),
            "tes_mpc_infeasible_reason": decision.infeasible_reason,
            "tes_mpc_solver_status": decision.solver_status,
            "fixed_CRAH_Fan_DRL": float(args.fan_action),
            "fixed_CT_Pump_DRL": float(args.ct_pump_action),
            "fixed_CRAH_T_DRL": float(args.crah_temp_action),
            "fixed_Chiller_T_DRL": float(args.chiller_temp_action),
            "reward": float(reward),
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "TES_valve_wrapper_position": finite_or_none(info.get("tes_valve_position")),
            "tes_valve_target": finite_or_none(info.get("tes_valve_target")),
            "tes_guard_clipped": bool(info.get("tes_guard_clipped", False)),
        }
    )
    objective_terms = decision.objective_terms or {}
    row.update(
        {
            "tes_mpc_objective_electricity_cost_proxy": objective_terms.get("electricity_cost_proxy"),
            "tes_mpc_objective_switch_penalty": objective_terms.get("switch_penalty"),
            "tes_mpc_objective_terminal_soc_penalty": objective_terms.get("terminal_soc_penalty"),
            "tes_mpc_objective_soc_bound_penalty": objective_terms.get("soc_bound_penalty"),
            "tes_mpc_objective_soc_schedule_penalty": objective_terms.get("soc_schedule_penalty"),
            "tes_mpc_objective_comfort_risk_penalty": objective_terms.get("comfort_risk_penalty"),
        }
    )
    diagnostics = decision.optimizer_diagnostics or {}
    row.update(
        {
            "tes_mpc_soc_hi_slack_sum": diagnostics.get("soc_hi_slack_sum"),
            "tes_mpc_soc_hi_slack_max": diagnostics.get("soc_hi_slack_max"),
            "tes_mpc_soc_hi_slack_first_step": diagnostics.get("soc_hi_slack_first_step"),
            "tes_mpc_soc_lo_slack_sum": diagnostics.get("soc_lo_slack_sum"),
            "tes_mpc_soc_lo_slack_max": diagnostics.get("soc_lo_slack_max"),
            "tes_mpc_soc_lo_slack_first_step": diagnostics.get("soc_lo_slack_first_step"),
            "tes_mpc_terminal_abs_slack": diagnostics.get("terminal_abs_slack"),
            "tes_mpc_predicted_soc_1": diagnostics.get("predicted_soc_1"),
            "tes_mpc_predicted_soc_n": diagnostics.get("predicted_soc_n"),
            "tes_mpc_predicted_soc_min": diagnostics.get("predicted_soc_min"),
            "tes_mpc_predicted_soc_max": diagnostics.get("predicted_soc_max"),
            "tes_mpc_current_low_price_window": diagnostics.get("current_low_price_window"),
            "tes_mpc_current_low_prepeak_window": diagnostics.get("current_low_prepeak_window"),
            "tes_mpc_current_high_price_window": diagnostics.get("current_high_price_window"),
            "tes_mpc_desired_soc_1": diagnostics.get("desired_soc_1"),
            "tes_mpc_desired_soc_n": diagnostics.get("desired_soc_n"),
            "tes_mpc_safety_override": diagnostics.get("safety_override", ""),
            "tes_mpc_safety_recovery": bool(diagnostics.get("safety_recovery", False)),
            "tes_mpc_initial_out_of_bounds": bool(diagnostics.get("initial_out_of_bounds", False)),
            "tes_mpc_planning_soc_min": diagnostics.get("planning_soc_min"),
            "tes_mpc_planning_soc_max": diagnostics.get("planning_soc_max"),
        }
    )
    for key in (
        "time_elapsed(hours)",
        "energy_term",
        "ITE_term",
        "comfort_term",
        "cost_term",
        "cost_usd_step",
        "mwh_step",
        "lmp_usd_per_mwh",
        "current_price_usd_per_mwh",
        "current_pv_kw",
        "total_temperature_violation",
    ):
        row[key] = _info_value(info, key)
    return row


def _energy_mwh(series: pd.Series) -> tuple[np.ndarray | None, str | None]:
    if series.empty:
        return None, None
    values = pd.to_numeric(series, errors="coerce")
    if values.isna().all():
        return None, None
    if float(values.abs().median()) > 1.0e5:
        return (values / 3.6e9).to_numpy(dtype=np.float64), "J"
    return values.to_numpy(dtype=np.float64), "MWh"


def _mean_or_none(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.mean())


def _fraction_or_none(mask: pd.Series | np.ndarray) -> float | None:
    values = pd.Series(mask).dropna()
    if values.empty:
        return None
    return float(values.astype(bool).mean())


def _first_true_index(mask: pd.Series | np.ndarray) -> int | None:
    values = pd.Series(mask).fillna(False).astype(bool)
    if not values.any():
        return None
    return int(values[values].index[0])


def _delta_or_none(series: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if len(values) < 2:
        return None
    return float(values.iloc[-1] - values.iloc[0])


def _contiguous_delta_mean(series: pd.Series, mask: pd.Series) -> float | None:
    values = pd.to_numeric(series, errors="coerce")
    active = mask.fillna(False).astype(bool)
    deltas: list[float] = []
    start_value: float | None = None
    last_value: float | None = None
    for is_active, value in zip(active.to_list(), values.to_list()):
        if not is_active or pd.isna(value):
            if start_value is not None and last_value is not None and last_value != start_value:
                deltas.append(float(last_value - start_value))
            start_value = None
            last_value = None
            continue
        number = float(value)
        if start_value is None:
            start_value = number
        last_value = number
    if start_value is not None and last_value is not None and last_value != start_value:
        deltas.append(float(last_value - start_value))
    if not deltas:
        return None
    return float(np.mean(deltas))


def summarize_monitor(
    df: pd.DataFrame,
    args: argparse.Namespace,
    steps: int,
    total_reward: float,
    elapsed: float,
    monitor_path: Path,
    action_dim: int,
    obs_dim: int,
) -> dict[str, Any]:
    notes: dict[str, str] = {}
    if not df.columns.is_unique:
        duplicated = df.columns[df.columns.duplicated()].tolist()
        raise RuntimeError(f"Duplicate monitor columns in {monitor_path}: {duplicated}")

    temps = pd.to_numeric(df.get("air_temperature"), errors="coerce")
    valves = pd.to_numeric(df.get("TES_valve_wrapper_position"), errors="coerce")
    soc = pd.to_numeric(df.get("TES_SOC"), errors="coerce")
    price = pd.to_numeric(df.get("price_current_norm"), errors="coerce")
    hours_to_peak = pd.to_numeric(df.get("price_hours_to_next_peak_norm"), errors="coerce")
    targets = pd.to_numeric(df.get("tes_mpc_signed_target_label"), errors="coerce")
    safety_recovery = (
        df["tes_mpc_safety_recovery"].fillna(False).astype(bool)
        if "tes_mpc_safety_recovery" in df
        else pd.Series(False, index=df.index)
    )

    comfort_pct = None
    if temps.notna().any():
        comfort_pct = float((temps > 25.0).mean() * 100.0)
    else:
        notes["comfort"] = "air_temperature unavailable in monitor."

    guard_pct = None
    if "tes_guard_clipped" in df:
        guard_pct = float(df["tes_guard_clipped"].astype(bool).mean() * 100.0)
    else:
        notes["guard"] = "tes_guard_clipped unavailable in monitor."

    charge_window = (
        (price <= args.low_price_threshold)
        & (hours_to_peak <= args.near_peak_threshold)
    )
    discharge_window = price >= args.high_price_threshold
    low_price_window = price <= args.low_price_threshold
    feasible = df["tes_mpc_feasible"].astype(bool) if "tes_mpc_feasible" in df else pd.Series(True, index=df.index)
    feasible_charge_window = charge_window & feasible
    economic_low_price_window = low_price_window & ~safety_recovery
    economic_feasible_charge_window = charge_window & feasible & ~safety_recovery

    charge_window_sign_rate = None
    if economic_feasible_charge_window.fillna(False).any():
        charge_window_sign_rate = float((targets[economic_feasible_charge_window] < -0.05).mean())
    else:
        notes["charge_window_sign_rate"] = "No feasible charge-window rows matched thresholds and SOC-space constraints."

    low_price_discharge_fraction = None
    if low_price_window.fillna(False).any():
        low_price_discharge_fraction = float((valves[low_price_window] > 0.05).mean())
    else:
        notes["low_price_discharge_fraction"] = "No low-price rows matched threshold."
    economic_low_price_discharge_fraction = None
    if economic_low_price_window.fillna(False).any():
        economic_low_price_discharge_fraction = float((valves[economic_low_price_window] > 0.05).mean())
    else:
        notes["economic_low_price_discharge_fraction"] = "No non-safety-recovery low-price rows matched threshold."

    charge_window_valve_mean = _mean_or_none(valves[charge_window])
    if charge_window_valve_mean is None:
        notes["charge_window_valve_mean"] = "No charge-window valve samples available."
    economic_charge_window_valve_mean = _mean_or_none(valves[charge_window & ~safety_recovery])
    if economic_charge_window_valve_mean is None:
        notes["economic_charge_window_valve_mean"] = "No non-safety-recovery charge-window valve samples available."
    discharge_window_valve_mean = _mean_or_none(valves[discharge_window])
    if discharge_window_valve_mean is None:
        notes["discharge_window_valve_mean"] = "No discharge-window valve samples available."

    delta_soc_prepeak = _contiguous_delta_mean(soc, economic_feasible_charge_window)
    if delta_soc_prepeak is None:
        notes["delta_soc_prepeak"] = "Need at least two feasible charge-window SOC samples in a contiguous segment."
    delta_soc_peak = _contiguous_delta_mean(soc, discharge_window)
    if delta_soc_peak is None:
        notes["delta_soc_peak"] = "Need at least two discharge-window SOC samples in a contiguous segment."

    soc_daily_amplitude_mean = None
    if soc.notna().any():
        soc_np = soc.dropna().to_numpy(dtype=np.float64)
        steps_per_day = 24 * M2_TIMESTEPS_PER_HOUR
        n_days = len(soc_np) // steps_per_day
        if n_days:
            daily_amp = np.asarray(
                [
                    soc_np[d * steps_per_day:(d + 1) * steps_per_day].max()
                    - soc_np[d * steps_per_day:(d + 1) * steps_per_day].min()
                    for d in range(n_days)
                ],
                dtype=np.float64,
            )
            soc_daily_amplitude_mean = float(daily_amp.mean())
        else:
            soc_daily_amplitude_mean = float(soc_np.max() - soc_np.min())
            notes["soc_daily_amplitude_mean"] = "Run shorter than one day; reported run amplitude."
    else:
        notes["soc_daily_amplitude_mean"] = "TES_SOC unavailable in monitor."

    facility_mwh_step = None
    ite_mwh_step = None
    energy_unit = None
    total_facility_mwh = None
    total_ite_mwh = None
    pue = None
    cost_usd = None
    if "Electricity:Facility" in df:
        facility_mwh_step, energy_unit = _energy_mwh(df["Electricity:Facility"])
    if "ITE-CPU:InteriorEquipment:Electricity" in df:
        ite_mwh_step, _ = _energy_mwh(df["ITE-CPU:InteriorEquipment:Electricity"])
    if facility_mwh_step is not None:
        total_facility_mwh = float(np.nansum(facility_mwh_step))
    else:
        notes["total_facility_MWh"] = "Electricity:Facility unavailable or nonnumeric."
    if ite_mwh_step is not None:
        total_ite_mwh = float(np.nansum(ite_mwh_step))
    else:
        notes["total_ite_MWh"] = "ITE-CPU:InteriorEquipment:Electricity unavailable or nonnumeric."
    if total_facility_mwh is not None and total_ite_mwh and total_ite_mwh > 0:
        pue = float(total_facility_mwh / total_ite_mwh)
    else:
        notes["pue"] = "PUE requires nonzero facility and ITE energy."

    if "cost_usd_step" in df and pd.to_numeric(df["cost_usd_step"], errors="coerce").notna().any():
        cost_usd = float(pd.to_numeric(df["cost_usd_step"], errors="coerce").sum())
    elif facility_mwh_step is not None:
        price_series = pd.read_csv(args.price_csv)["price_usd_per_mwh"].to_numpy(dtype=np.float64)
        hour_idx = (np.arange(len(facility_mwh_step)) // M2_TIMESTEPS_PER_HOUR) % len(price_series)
        cost_usd = float(np.nansum(facility_mwh_step * price_series[hour_idx]))
    else:
        notes["cost_usd"] = "Cost requires cost_usd_step or facility energy plus price CSV."

    valves_effective = np.where(valves.abs().fillna(0.0).to_numpy() > 0.01, valves.abs().fillna(0.0).to_numpy(), 0.0)
    cycles_rough = float(
        valves_effective.sum()
        * TES_MAX_FLOW_KG_S
        * (3600.0 / M2_TIMESTEPS_PER_HOUR)
        / 1000.0
        / TES_TANK_M3
    )

    soc_below_guard = soc < float(args.tes_guard_soc_low)
    soc_above_guard = soc > float(args.tes_guard_soc_high)
    soc_below_guard_count = int(soc_below_guard.fillna(False).sum())
    soc_above_guard_count = int(soc_above_guard.fillna(False).sum())
    actual_soc_bound_violation_count = soc_below_guard_count + soc_above_guard_count
    actual_soc_bound_violation_fraction = (
        float(actual_soc_bound_violation_count / len(soc)) if len(soc) else None
    )
    in_strict_bounds = ~(soc_below_guard | soc_above_guard)
    initial_out_of_bounds = bool(len(soc) and not bool(in_strict_bounds.fillna(False).iloc[0]))
    if initial_out_of_bounds:
        first_recovered = _first_true_index(in_strict_bounds)
        soc_recovery_steps = int(first_recovered) if first_recovered is not None else int(len(soc))
    else:
        soc_recovery_steps = 0
    initial_recovery_mask = pd.Series(False, index=df.index)
    if soc_recovery_steps > 0:
        initial_recovery_mask.iloc[:soc_recovery_steps] = True
    soc_violation_excluding_initial_recovery = int(
        ((soc_below_guard | soc_above_guard) & ~initial_recovery_mask).fillna(False).sum()
    )

    def numeric_monitor_col(name: str) -> pd.Series:
        if name not in df:
            return pd.Series(dtype=np.float64)
        return pd.to_numeric(df[name], errors="coerce")

    hi_slack_sum_series = numeric_monitor_col("tes_mpc_soc_hi_slack_sum")
    hi_slack_max_series = numeric_monitor_col("tes_mpc_soc_hi_slack_max")
    lo_slack_sum_series = numeric_monitor_col("tes_mpc_soc_lo_slack_sum")
    lo_slack_max_series = numeric_monitor_col("tes_mpc_soc_lo_slack_max")
    terminal_abs_slack_series = numeric_monitor_col("tes_mpc_terminal_abs_slack")
    pred_soc_1_series = numeric_monitor_col("tes_mpc_predicted_soc_1")
    pred_soc_n_series = numeric_monitor_col("tes_mpc_predicted_soc_n")
    pred_soc_min_series = numeric_monitor_col("tes_mpc_predicted_soc_min")
    pred_soc_max_series = numeric_monitor_col("tes_mpc_predicted_soc_max")
    solver_status_counts = (
        df["tes_mpc_solver_status"].fillna("missing").astype(str).value_counts().to_dict()
        if "tes_mpc_solver_status" in df
        else {}
    )

    mechanism_gate = {
        "comfort_lt_3pct": comfort_pct is not None and comfort_pct < 3.0,
        "guard_lt_5pct": guard_pct is not None and guard_pct < 5.0,
        "charge_window_sign_rate_ge_0_80": charge_window_sign_rate is not None and charge_window_sign_rate >= 0.80,
        "economic_low_price_discharge_fraction_le_0_10": (
            economic_low_price_discharge_fraction is not None
            and economic_low_price_discharge_fraction <= 0.10
        ),
        "economic_charge_window_valve_mean_lt_neg_0_05": (
            economic_charge_window_valve_mean is not None and economic_charge_window_valve_mean < -0.05
        ),
        "discharge_window_valve_mean_gt_0_05": discharge_window_valve_mean is not None and discharge_window_valve_mean > 0.05,
        "delta_soc_prepeak_gt_0": delta_soc_prepeak is not None and delta_soc_prepeak > 0.0,
        "delta_soc_peak_lt_0": delta_soc_peak is not None and delta_soc_peak < 0.0,
    }
    physical_bound_gate = {
        "actual_soc_bounds_respected": actual_soc_bound_violation_count == 0,
    }
    mechanism_gate_pass = bool(all(mechanism_gate.values()))
    physical_bound_gate_pass = bool(all(physical_bound_gate.values()))
    gate = {**mechanism_gate, **physical_bound_gate}

    result: dict[str, Any] = {
        "tag": args.tag,
        "controller_type": args.controller_type,
        "controller_family": getattr(args, "controller_family", args.controller_type),
        "controller_type_detail": getattr(args, "controller_type_detail", args.controller_type),
        "solver_requested": getattr(args, "solver", "heuristic"),
        "solver_used": getattr(args, "solver_used", "heuristic"),
        "solver_status": getattr(args, "solver_status", "heuristic"),
        "forecast_noise_mode": getattr(args, "forecast_noise_mode", "perfect"),
        "forecast_noise_sigma": float(getattr(args, "forecast_noise_sigma", 0.0)),
        "forecast_noise_seed": int(getattr(args, "forecast_noise_seed", 0)),
        "forecast_noise_persist_h": int(getattr(args, "forecast_noise_persist_h", 1)),
        "eval_design": args.eval_design,
        "eval_design_description": EVAL_DESIGNS[args.eval_design]["description"],
        "building_file": EVAL_DESIGNS[args.eval_design]["building_file"],
        "evaluation_flag": EVAL_DESIGNS[args.eval_design]["evaluation_flag"],
        "ITE_Set": EVAL_DESIGNS[args.eval_design]["ite_set"],
        "reward_cls": args.reward_cls,
        "action_dim": action_dim,
        "obs_dim": obs_dim,
        "steps": steps,
        "max_steps": args.max_steps,
        "horizon_hours": args.horizon_hours,
        "terminal_soc_target": args.terminal_soc_target,
        "total_reward": total_reward,
        "comfort": comfort_pct,
        "comfort_violation_pct": comfort_pct,
        "guard": guard_pct,
        "tes_guard_clipped_pct": guard_pct,
        "charge_window_sign_rate": charge_window_sign_rate,
        "low_price_discharge_fraction": low_price_discharge_fraction,
        "raw_low_price_discharge_fraction": low_price_discharge_fraction,
        "economic_low_price_discharge_fraction_excluding_safety_recovery": economic_low_price_discharge_fraction,
        "charge_window_valve_mean": charge_window_valve_mean,
        "raw_charge_window_valve_mean": charge_window_valve_mean,
        "economic_charge_window_valve_mean_excluding_safety_recovery": economic_charge_window_valve_mean,
        "discharge_window_valve_mean": discharge_window_valve_mean,
        "delta_soc_prepeak": delta_soc_prepeak,
        "delta_soc_peak": delta_soc_peak,
        "soc_daily_amplitude_mean": soc_daily_amplitude_mean,
        "cost_usd": cost_usd,
        "pue": pue,
        "total_facility_MWh": total_facility_mwh,
        "total_ite_MWh": total_ite_mwh,
        "energy_unit_detected": energy_unit,
        "tes_annual_cycles_rough": cycles_rough,
        "soc_min": finite_or_none(soc.min()),
        "soc_mean": finite_or_none(soc.mean()),
        "soc_max": finite_or_none(soc.max()),
        "soc_below_guard_count": soc_below_guard_count,
        "soc_above_guard_count": soc_above_guard_count,
        "actual_soc_bound_violation_count": actual_soc_bound_violation_count,
        "actual_soc_bound_violation_fraction": actual_soc_bound_violation_fraction,
        "actual_soc_bound_violation_first_step": _first_true_index(soc_below_guard | soc_above_guard),
        "initial_out_of_bounds": initial_out_of_bounds,
        "soc_recovery_steps": soc_recovery_steps,
        "soc_violation_excluding_initial_recovery": soc_violation_excluding_initial_recovery,
        "soc_hi_slack_sum": finite_or_none(hi_slack_sum_series.sum()) if not hi_slack_sum_series.empty else None,
        "soc_hi_slack_max": finite_or_none(hi_slack_max_series.max()) if not hi_slack_max_series.empty else None,
        "soc_hi_slack_first_step": _first_true_index(hi_slack_max_series > 1.0e-9) if not hi_slack_max_series.empty else None,
        "soc_lo_slack_sum": finite_or_none(lo_slack_sum_series.sum()) if not lo_slack_sum_series.empty else None,
        "soc_lo_slack_max": finite_or_none(lo_slack_max_series.max()) if not lo_slack_max_series.empty else None,
        "soc_lo_slack_first_step": _first_true_index(lo_slack_max_series > 1.0e-9) if not lo_slack_max_series.empty else None,
        "terminal_abs_slack": finite_or_none(terminal_abs_slack_series.dropna().iloc[-1])
        if terminal_abs_slack_series.notna().any()
        else None,
        "predicted_soc_1": finite_or_none(pred_soc_1_series.dropna().iloc[0])
        if pred_soc_1_series.notna().any()
        else None,
        "predicted_soc_n": finite_or_none(pred_soc_n_series.dropna().iloc[-1])
        if pred_soc_n_series.notna().any()
        else None,
        "predicted_soc_min": finite_or_none(pred_soc_min_series.min()) if not pred_soc_min_series.empty else None,
        "predicted_soc_max": finite_or_none(pred_soc_max_series.max()) if not pred_soc_max_series.empty else None,
        "solver_status_counts": solver_status_counts,
        "valve_mean_abs": finite_or_none(valves.abs().mean()),
        "valve_active_fraction": finite_or_none((valves.abs() > 0.05).mean()),
        "valve_saturation_fraction": finite_or_none((valves.abs() > 0.95).mean()),
        "charge_fraction": finite_or_none((valves < -0.05).mean()),
        "discharge_fraction": finite_or_none((valves > 0.05).mean()),
        "monitor_csv": str(monitor_path),
        "elapsed_seconds": elapsed,
        "gate": gate,
        "mechanism_gate": mechanism_gate,
        "physical_bound_gate": physical_bound_gate,
        "mechanism_gate_pass": mechanism_gate_pass,
        "physical_bound_gate_pass": physical_bound_gate_pass,
        "gate_pass": bool(mechanism_gate_pass and physical_bound_gate_pass),
        "unavailable_metric_notes": notes,
        "fixed_actions": {
            "CRAH_Fan_DRL": args.fan_action,
            "CT_Pump_DRL": args.ct_pump_action,
            "CRAH_T_DRL": args.crah_temp_action,
            "Chiller_T_DRL": args.chiller_temp_action,
        },
        "guard_config": {
            "tes_guard_soc_low": args.tes_guard_soc_low,
            "tes_guard_soc_high": args.tes_guard_soc_high,
            "tes_valve_rate_limit": args.tes_valve_rate_limit,
        },
        "optimizer_config": {
            "horizon_steps": int(round(float(args.horizon_hours) * M2_TIMESTEPS_PER_HOUR)),
            "time_step_minutes": 60.0 / M2_TIMESTEPS_PER_HOUR,
            "objective_terms": {
                "electricity_cost": "price-centered TES arbitrage proxy from price CSV",
                "switch_penalty": getattr(args, "switch_penalty", 0.0),
                "terminal_soc_penalty": getattr(args, "terminal_soc_weight", None),
                "soc_bound_penalty": getattr(args, "soc_bound_penalty", None),
                "soc_schedule_penalty": getattr(args, "soc_schedule_weight", None),
                "low_prepeak_charge_reward": getattr(args, "low_prepeak_charge_reward", None),
                "high_price_discharge_reward": getattr(args, "high_price_discharge_reward", None),
                "comfort_risk_penalty": "zero-weight placeholder; not modeled in M2-F1 optimizer",
            },
            "constraints": [
                "SOC bounds with high-penalty slack for rolling feasibility",
                "TES target rate limit",
                "low-price windows forbid discharge",
                "high-price windows forbid charge",
                "current low-price pre-peak window applies minimum charge when SOC/rate constraints make it feasible",
                "current high-price window applies minimum discharge when SOC/rate constraints make it feasible",
                "actual low/high SOC protection can override economic action bounds",
                "strict out-of-bound SOC recovery is labeled as safety_recovery",
                "charge/discharge convex relaxation via u_charge + u_discharge bound",
                "terminal SOC soft-near target with tolerance and slack penalty",
                "rolling SOC inventory schedule for headroom before pre-peak charging and reserve after discharge",
            ],
            "terminal_soc_tolerance": getattr(args, "terminal_soc_tolerance", None),
            "soc_planning_min": getattr(args, "soc_planning_min", None),
            "soc_planning_max": getattr(args, "soc_planning_max", None),
            "soc_safety_margin": getattr(args, "soc_safety_margin", None),
            "optimizer_soc_min_legacy": getattr(args, "optimizer_soc_min", None),
            "optimizer_soc_max_legacy": getattr(args, "optimizer_soc_max", None),
            "low_prepeak_min_charge": getattr(args, "low_prepeak_min_charge", None),
            "high_price_min_discharge": getattr(args, "high_price_min_discharge", None),
            "low_prepeak_soc_target": getattr(args, "low_prepeak_soc_target", None),
            "reserve_headroom_soc_target": getattr(args, "reserve_headroom_soc_target", None),
            "high_price_soc_target": getattr(args, "high_price_soc_target", None),
        },
        "heuristic": {
            "low_price_threshold": args.low_price_threshold,
            "high_price_threshold": args.high_price_threshold,
            "near_peak_threshold": args.near_peak_threshold,
            "soc_charge_limit": args.soc_charge_limit,
            "soc_discharge_limit": args.soc_discharge_limit,
            "charge_target": -args.charge_target,
            "discharge_target": args.discharge_target,
        },
        "metric_scope": {
            "charge_window_sign_rate": "low-price pre-peak rows with tes_mpc_feasible=True",
            "delta_soc_prepeak": "mean SOC delta over contiguous feasible low-price pre-peak segments",
            "delta_soc_peak": "mean SOC delta over contiguous high-price segments",
        },
    }
    dynamics = getattr(args, "soc_dynamics", None)
    if dynamics is not None:
        result["soc_dynamics"] = {
            "charge_gain_per_step": dynamics.charge_gain_per_step,
            "discharge_gain_per_step": dynamics.discharge_gain_per_step,
            "source": dynamics.source,
            "calibration_monitor": dynamics.calibration_monitor,
            "sample_counts": dynamics.sample_counts,
            "fallback_reason": dynamics.fallback_reason,
        }
    for attr in (
        "switch_penalty",
        "terminal_soc_weight",
        "soc_bound_penalty",
        "soc_schedule_weight",
        "low_price_discharge_penalty",
        "high_price_charge_penalty",
        "low_prepeak_charge_reward",
        "high_price_discharge_reward",
        "soc_planning_min",
        "soc_planning_max",
        "soc_safety_margin",
    ):
        if hasattr(args, attr):
            result[attr] = getattr(args, attr)
    return json_sanitize(result)


def write_summary_files(result: dict[str, Any]) -> None:
    SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    flat = {
        key: value
        for key, value in result.items()
        if not isinstance(value, (dict, list))
    }
    row = pd.DataFrame([flat])
    if SUMMARY_CSV.exists():
        existing = pd.read_csv(SUMMARY_CSV)
        existing = existing[existing.get("tag") != result["tag"]] if "tag" in existing else existing
        pd.concat([existing, row], ignore_index=True).to_csv(SUMMARY_CSV, index=False)
    else:
        row.to_csv(SUMMARY_CSV, index=False)

    records: list[dict[str, Any]]
    if SUMMARY_JSON.exists():
        try:
            loaded = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
            records = loaded if isinstance(loaded, list) else [loaded]
        except json.JSONDecodeError:
            records = []
        records = [item for item in records if item.get("tag") != result["tag"]]
    else:
        records = []
    records.append(result)
    SUMMARY_JSON.write_text(json.dumps(records, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def evaluate_controller(args: argparse.Namespace) -> dict[str, Any]:
    if "Eplus-DC-Cooling-TES" not in get_ids():
        raise RuntimeError("Eplus-DC-Cooling-TES environment is not registered.")
    if abs(args.fan_action - M2_FIXED_FAN_VALUE) > 1e-9:
        print(
            f"[{args.controller_type}] forcing CRAH_Fan_DRL={M2_FIXED_FAN_VALUE} "
            f"instead of requested {args.fan_action}."
        )
        args.fan_action = M2_FIXED_FAN_VALUE

    out_dir = Path(args.out_dir) / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    monitor_path = out_dir / "monitor.csv"
    result_path = out_dir / "result.json"

    env = build_env(args)
    env = attach_reward(env, args)
    if env.action_space.shape != (4,):
        raise RuntimeError(f"Expected fixed-fan M2-F1 4D action space, got {env.action_space.shape}")
    action_dim = int(env.action_space.shape[0])
    obs_dim = int(env.observation_space.shape[0])
    obs_names = list(env.get_wrapper_attr("observation_variables"))
    planner_state = prepare_planner(args)
    if "soc_dynamics" in planner_state:
        args.soc_dynamics = planner_state["soc_dynamics"]

    started = time.perf_counter()
    obs, _ = env.reset()
    total_reward = 0.0
    steps = 0
    terminated = truncated = False
    rows: list[dict[str, Any]] = []
    try:
        while not (terminated or truncated):
            obs_values = obs_map(np.asarray(obs, dtype=np.float64), obs_names)
            decision = plan_controller_action(obs_values, args, planner_state, steps)
            action = action_from_decision(decision, args)
            if action.shape != (4,):
                raise RuntimeError(f"Planner emitted {action.shape}, expected (4,)")
            next_obs, reward, terminated, truncated, info = env.step(action)
            rows.append(
                make_monitor_row(
                    step_idx=steps,
                    obs_values=obs_values,
                    action=action,
                    decision=decision,
                    reward=float(reward),
                    terminated=terminated,
                    truncated=truncated,
                    info=info,
                    args=args,
                )
            )
            total_reward += float(reward)
            steps += 1
            actual_valve = finite_or_none(info.get("tes_valve_position"))
            if actual_valve is None:
                actual_valve = finite_or_none(info.get("tes_valve_target"))
            planner_state["last_target"] = actual_valve if actual_valve is not None else decision.target
            obs = next_obs
            if args.max_steps and steps >= args.max_steps:
                break
    finally:
        env.close()

    if not rows:
        raise RuntimeError("No monitor rows were collected.")
    df = pd.DataFrame(rows)
    df.to_csv(monitor_path, index=False)
    if df.isna().all(axis=None):
        raise RuntimeError(f"Monitor appears empty: {monitor_path}")

    result = summarize_monitor(
        df=df,
        args=args,
        steps=steps,
        total_reward=total_reward,
        elapsed=time.perf_counter() - started,
        monitor_path=monitor_path,
        action_dim=action_dim,
        obs_dim=obs_dim,
    )
    result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    write_summary_files(result)
    return result


def add_common_args(ap: argparse.ArgumentParser) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ap.add_argument("--tag", default=f"m2f1_mpc_oracle_{stamp}")
    ap.add_argument("--eval-design", default="trainlike", choices=sorted(EVAL_DESIGNS))
    ap.add_argument("--max-steps", type=int, default=0, help="Optional early stop for validation runs.")
    ap.add_argument("--out-dir", type=Path, default=Path("runs/m2_tes_mpc_oracle"))
    ap.add_argument(
        "--forecast-noise-mode",
        choices=["perfect", "gaussian", "persistence_h"],
        default="perfect",
        help="Forecast perturbation mode for planner-side predicted signals.",
    )
    ap.add_argument(
        "--forecast-noise-sigma",
        type=float,
        default=0.10,
        help="Relative Gaussian sigma for future-step forecast perturbations.",
    )
    ap.add_argument(
        "--forecast-noise-seed",
        type=int,
        default=0,
        help="Base RNG seed for reproducible forecast perturbations.",
    )
    ap.add_argument(
        "--forecast-noise-persist-h",
        type=int,
        default=1,
        help="Backward lag in hours for persistence_h forecast substitution.",
    )
    ap.add_argument(
        "--solver",
        choices=["heuristic", "lp_highs", "milp"],
        default="milp",
        help=(
            "Optimizer family. heuristic = original rolling rule. "
            "lp_highs = scipy-highs LP relaxation. "
            "milp = reserved for HiGHS MILP in W1-2 and temporarily falls back to lp_highs."
        ),
    )
    ap.add_argument("--horizon-hours", type=float, default=24.0)
    ap.add_argument("--terminal-soc-target", type=float, default=0.50)
    ap.add_argument("--terminal-soc-tolerance", type=float, default=0.08)
    ap.add_argument("--charge-target", type=float, default=0.85)
    ap.add_argument("--discharge-target", type=float, default=0.85)
    ap.add_argument("--tes-valve-rate-limit", type=float, default=0.25)
    ap.add_argument("--tes-guard-soc-low", type=float, default=0.10)
    ap.add_argument("--tes-guard-soc-high", type=float, default=0.90)
    ap.add_argument("--ct-pump-action", type=float, default=1.0)
    ap.add_argument("--crah-temp-action", type=float, default=0.0)
    ap.add_argument("--chiller-temp-action", type=float, default=0.0)
    ap.add_argument("--fan-action", type=float, default=M2_FIXED_FAN_VALUE)
    ap.add_argument("--low-price-threshold", type=float, default=-0.50)
    ap.add_argument("--high-price-threshold", type=float, default=0.75)
    ap.add_argument("--near-peak-threshold", type=float, default=0.40)
    ap.add_argument("--soc-charge-limit", type=float, default=0.85)
    ap.add_argument("--soc-discharge-limit", type=float, default=0.25)
    ap.add_argument("--epw", default=DEFAULT_EPW)
    ap.add_argument("--price-csv", default=DEFAULT_PRICE_CSV)
    ap.add_argument("--pv-csv", default=DEFAULT_PV_CSV)
    ap.add_argument("--reward-cls", default="rl_cost", choices=["pue_tes", "rl_cost", "rl_green"])
    ap.add_argument("--kappa-shape", type=float, default=0.8)
    ap.add_argument("--dc-peak-load-kw", type=float, default=6000.0)
    ap.add_argument("--alpha", type=float, default=2e-3)
    ap.add_argument("--beta", type=float, default=1.0)
    ap.add_argument("--c-pv", type=float, default=0.0)
    ap.add_argument("--pv-threshold-kw", type=float, default=100.0)
    ap.add_argument("--gamma-pbrs", type=float, default=0.99)
    ap.add_argument("--tau-decay", type=float, default=4.0)
    ap.add_argument("--p-peak-ref", type=float, default=0.80)
    ap.add_argument("--soc-calibration-monitor", type=Path, default=None)
    ap.add_argument("--soc-charge-gain", type=float, default=None)
    ap.add_argument("--soc-discharge-gain", type=float, default=None)
    ap.add_argument("--optimizer-soc-min", type=float, default=0.15)
    ap.add_argument("--optimizer-soc-max", type=float, default=0.85)
    ap.add_argument("--soc-planning-min", type=float, default=0.15)
    ap.add_argument("--soc-planning-max", type=float, default=0.85)
    ap.add_argument("--soc-safety-margin", type=float, default=0.02)
    ap.add_argument("--soc-bound-penalty", type=float, default=1000.0)
    ap.add_argument("--soc-schedule-weight", type=float, default=6.0)
    ap.add_argument(
        "--switch-penalty",
        type=float,
        default=0.0,
        help="LP path mode-switch L1 penalty coefficient; 0.0 matches the historical summary default.",
    )
    ap.add_argument(
        "--terminal-soc-weight",
        type=float,
        default=1.0,
        help="LP path terminal SOC deviation linear weight; 1.0 matches the historical summary default.",
    )
    ap.add_argument("--electricity-cost-weight", type=float, default=1.0)
    ap.add_argument("--neutral-action-penalty", type=float, default=0.03)
    ap.add_argument("--low-price-discharge-penalty", type=float, default=200.0)
    ap.add_argument("--high-price-charge-penalty", type=float, default=200.0)
    ap.add_argument("--low-prepeak-charge-reward", type=float, default=8.0)
    ap.add_argument("--high-price-discharge-reward", type=float, default=6.0)
    ap.add_argument("--low-prepeak-min-charge", type=float, default=0.20)
    ap.add_argument("--high-price-min-discharge", type=float, default=0.20)
    ap.add_argument("--low-prepeak-soc-target", type=float, default=0.84)
    ap.add_argument("--reserve-headroom-soc-target", type=float, default=0.55)
    ap.add_argument("--high-price-soc-target", type=float, default=0.35)
    ap.add_argument("--comfort-risk-weight", type=float, default=0.0)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    add_common_args(ap)
    args = ap.parse_args()
    args.controller_type = "mpc_oracle"
    args.controller_family = "mpc_oracle"
    args.controller_type_detail = "mpc_oracle_physical_reachable_baseline"
    args.solver_used = args.solver
    args.solver_status = args.solver
    return args


def main() -> None:
    args = parse_args()
    result = evaluate_controller(args)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    print(f"Wrote {Path(args.out_dir) / args.tag / 'result.json'}")
    print(f"Wrote {Path(args.out_dir) / args.tag / 'monitor.csv'}")
    print(f"Updated {SUMMARY_CSV}")
    print(f"Updated {SUMMARY_JSON}")


if __name__ == "__main__":
    main()
