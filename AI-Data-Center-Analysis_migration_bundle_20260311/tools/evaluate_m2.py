"""M2 fixed-fan evaluation on Nanjing + Jiangsu TOU + full wrapper stack.

Loads a single seed's 4D checkpoint + training normalization stats (32-dim M2
env, fixed CRAH_Fan_DRL=1.0), runs a deterministic year-long evaluation, outputs:
    - PUE / comfort pct / facility MWh / ITE MWh (standard)
    - cost_usd_annual (LMP × P_facility integrated)
    - pv_self_consumption_pct (min(P_facility, pv_kw) / P_facility)
    - TES activation metrics: annual_cycles / soc_daily_amplitude

TES activation criterion (handoff §4.1 / tech route D5):
    annual_cycles ≥ 100 AND soc_daily_amplitude_mean ≥ 0.3

Usage:
    python tools/evaluate_m2.py --seed 7 \
        --checkpoint runs/train/run-XXX/checkpoints/e3_rl_cost_seed7_NNNNNNN_steps.zip \
        --workspace runs/train/run-XXX \
        --reward-cls rl_cost \
        --tag seed7

M2-F1 default evaluation is trainlike/in-distribution:
    DRL_DC_training.epJSON, evaluation_flag=0, ITE_Set=0.45.
Use --eval-design official_ood only for the high-load ITE_Set=1.0 stress test.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import gymnasium as gym
import numpy as np
import pandas as pd

from sinergym.utils.common import get_ids
from sinergym.utils.wrappers import LoggerWrapper, NormalizeObservation
from sinergym.envs.energy_scale_wrapper import EnergyScaleWrapper
from sinergym.envs.tes_wrapper import (
    FixedActionInsertWrapper,
    TESDirectionAmplitudeActionWrapper,
    TESStateAugmentationWrapper,
    TESTargetValveWrapper,
)
from sinergym.envs.time_encoding_wrapper import TimeEncodingWrapper
from sinergym.envs.temp_trend_wrapper import TempTrendWrapper
from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
from sinergym.envs.pv_signal_wrapper import PVSignalWrapper
from tools.dsac_t import DSAC_T
from tools.m2_action_guard import M2_FIXED_FAN_VALUE, checkpoint_action_dim

# M2-E3b-v3 (2026-04-22): Nanjing + Jiangsu 2025 TOU 合成电价 (见 run_m2_training.py)
DEFAULT_EPW = "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
DEFAULT_PRICE_CSV = "Data/prices/Jiangsu_TOU_2025_hourly.csv"
DEFAULT_PV_CSV = "Data/pv/CHN_Nanjing_PV_6MWp_hourly.csv"
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

# TES sizing (from 建筑模型说明.md) — used for annual cycle estimate
TES_TANK_M3 = 1400.0
TES_MAX_FLOW_KG_S = 389.0  # EMS P_5 Max_Flow, current mixed-tank model
M2_TIMESTEPS_PER_HOUR = 4


def m2_action_dim(action_semantics: str) -> int:
    return 5 if action_semantics in {"direction_amp", "direction_amp_hold"} else 4


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


def assert_checkpoint_action_dim(checkpoint: Path, expected_dim: int) -> None:
    action_dim = checkpoint_action_dim(checkpoint)
    if action_dim != expected_dim:
        raise RuntimeError(
            f"Refusing checkpoint with action_dim={action_dim}; "
            f"evaluation env expects action_dim={expected_dim}. "
            "Check --tes-action-semantics and checkpoint provenance."
        )


def _resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def _load_json_file(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _workspace_provenance_sources(workspace: Path) -> list[tuple[Path, dict]]:
    workspace_resolved = _resolve_repo_path(workspace)
    sources: list[tuple[Path, dict]] = []
    metadata_path = workspace_resolved / "m2_training_metadata.json"
    if metadata_path.exists():
        data = _load_json_file(metadata_path)
        if isinstance(data, dict):
            sources.append((metadata_path, data))
    jobs_root = ROOT / "training_jobs"
    if jobs_root.exists():
        for status_path in jobs_root.glob("*/status.json"):
            data = _load_json_file(status_path)
            if not isinstance(data, dict):
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


def validate_workspace_provenance(args, expected_action_dim: int, expected_obs_dim: int) -> dict:
    sources = _workspace_provenance_sources(args.workspace)
    provenance = {
        "provenance_metadata_missing": not bool(sources),
        "provenance_metadata_sources": [str(path) for path, _ in sources],
    }
    for path, data in sources:
        source = str(path)
        semantics = data.get("tes_action_semantics")
        if semantics is not None and semantics != args.tes_action_semantics:
            raise RuntimeError(
                f"Checkpoint provenance mismatch: {source} records "
                f"tes_action_semantics={semantics!r}, but CLI requested "
                f"{args.tes_action_semantics!r}."
            )
        hold_steps = data.get("tes_option_hold_steps")
        if hold_steps is not None and (
            semantics == "direction_amp_hold" or args.tes_action_semantics == "direction_amp_hold"
        ):
            if int(hold_steps) != int(args.tes_option_hold_steps):
                raise RuntimeError(
                    f"Checkpoint provenance mismatch: {source} records "
                    f"tes_option_hold_steps={hold_steps}, but CLI requested "
                    f"{args.tes_option_hold_steps}."
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
        if state_aug is not None and bool(state_aug) != bool(args.enable_tes_state_augmentation):
            raise RuntimeError(
                f"Checkpoint provenance mismatch: {source} records "
                f"enable_tes_state_augmentation={bool(state_aug)}, but CLI requested "
                f"{bool(args.enable_tes_state_augmentation)}."
            )
    return provenance


def build_env(args) -> gym.Env:
    design = EVAL_DESIGNS[args.eval_design]
    env = gym.make(
        "Eplus-DC-Cooling-TES",
        env_name=f"eval-m2-{args.tag}",
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
        fixed_actions={0: M2_FIXED_FAN_VALUE},
        fixed_action_names={0: "CRAH_Fan_DRL"},
    )
    if args.tes_action_semantics in {"direction_amp", "direction_amp_hold"}:
        env = TESDirectionAmplitudeActionWrapper(
            env,
            direction_deadband=args.tes_direction_deadband,
            action_semantics=args.tes_action_semantics,
            hold_steps=args.tes_option_hold_steps,
        )
    env = TimeEncodingWrapper(env)
    # H2c: 6-dim outdoor temperature trend features (tech route §6.1-C)
    env = TempTrendWrapper(
        env,
        epw_path=Path("Data/weather") / (args.epw if isinstance(args.epw, str) else args.epw[0]),
        lookahead_hours=6,
    )
    env = PriceSignalWrapper(env, price_csv_path=args.price_csv)
    env = PVSignalWrapper(env, pv_csv_path=args.pv_csv, dc_peak_load_kw=args.dc_peak_load_kw)
    env = EnergyScaleWrapper(env, energy_indices=[13, 14], scale=1.0 / 3.6e9)
    if args.enable_tes_state_augmentation:
        env = TESStateAugmentationWrapper(
            env,
            high_price_threshold=args.tes_high_price_threshold,
            low_price_threshold=args.tes_low_price_threshold,
            near_peak_threshold=args.tes_near_peak_threshold,
        )
    return env


def attach_reward(env: gym.Env, args) -> gym.Env:
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
        energy_weight=0.5, lambda_energy=1.0, lambda_temperature=1.0,
        soc_variable="TES_SOC",
        soc_low=0.15, soc_high=0.85,
        # M2-E3b-v4 P3 (2026-04-23): 放松 soc 约束，让 cost_term 主导 TOU 学习
        soc_warn_low=0.15, soc_warn_high=0.85,
        lambda_soc=2.0, lambda_soc_warn=1.0,
        price_series=price, alpha=args.alpha, beta=args.beta,
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

    # R1b fix (2026-04-19): gymnasium.Wrapper.__getattr__ forwards attribute
    # lookup to self.env, so `hasattr(wrapper, "reward_fn")` is always True
    # for every wrapper above EplusEnv. The previous while-loop exited after
    # zero iterations and patched reward_fn on the outermost wrapper, leaving
    # env.unwrapped.reward_fn as the default PUE_TES_Reward — silently
    # corrupting all rl_cost / rl_green ablation evaluations. Use
    # env.unwrapped to land on the innermost EplusEnv directly.
    eplus_env = env.unwrapped
    if not hasattr(eplus_env, "reward_fn"):
        raise RuntimeError(
            f"env.unwrapped={type(eplus_env).__name__} has no reward_fn attribute"
        )
    eplus_env.reward_fn = cls(**kwargs)
    assert isinstance(eplus_env.reward_fn, cls), (
        f"reward_fn patch did not land on EplusEnv, "
        f"got {type(eplus_env.reward_fn).__name__}"
    )
    print(f"[evaluate_m2] reward class swapped to {cls.__name__} on {type(eplus_env).__name__}")
    return env


def evaluate(args) -> dict:
    if "Eplus-DC-Cooling-TES" not in get_ids():
        raise RuntimeError("Eplus-DC-Cooling-TES environment is not registered.")

    expected_obs_dim = 34 if args.enable_tes_state_augmentation else 32
    expected_action_dim = m2_action_dim(args.tes_action_semantics)
    provenance = validate_workspace_provenance(args, expected_action_dim, expected_obs_dim)
    mean = np.loadtxt(args.workspace / "mean.txt", dtype="float")
    var = np.loadtxt(args.workspace / "var.txt", dtype="float")
    if mean.shape[0] != expected_obs_dim or var.shape[0] != expected_obs_dim:
        raise RuntimeError(
            f"Expected {expected_obs_dim}-dim M2 normalization stats for "
            f"enable_tes_state_augmentation={args.enable_tes_state_augmentation}, "
            f"got mean={mean.shape}, var={var.shape}. Confirm --workspace and flag "
            f"match the checkpoint."
        )

    env = build_env(args)
    env = attach_reward(env, args)
    action_dim = int(env.action_space.shape[0])
    assert env.action_space.shape == (expected_action_dim,), (
        f"Expected M2-F1 action_dim={expected_action_dim}, got {env.action_space.shape}"
    )
    if env.observation_space.shape != (expected_obs_dim,):
        raise RuntimeError(
            f"Expected eval obs_dim={expected_obs_dim}, got {env.observation_space.shape}. "
            f"Check --enable-tes-state-augmentation."
        )
    env = NormalizeObservation(env, mean=mean, var=var, automatic_update=False)
    obs_vars = env.get_wrapper_attr("observation_variables")
    act_vars = env.get_wrapper_attr("action_variables")
    expected_act_vars = m2_action_variables(args.tes_action_semantics)
    assert list(act_vars) == expected_act_vars, (
        f"M2-F1 action_variables mismatch: expected {expected_act_vars}, got {list(act_vars)}"
    )
    env = LoggerWrapper(
        env,
        monitor_header=["timestep"] + list(obs_vars) + list(act_vars)
        + ["time (hours)", "reward", "energy_term", "ITE_term", "comfort_term", "cost_term",
           "fixed_CRAH_Fan_DRL",
           "action_dim", "tes_action_semantics", "tes_direction_deadband",
           "tes_direction_raw", "tes_amplitude_raw", "tes_amplitude_mapped",
           "tes_direction_mode", "tes_signed_target_from_semantics",
           "tes_option_hold_steps", "tes_option_hold_counter_remaining",
           "tes_option_accepted_new_mode", "tes_held_direction_mode",
           "tes_held_amplitude_mapped",
           "tes_valve_target", "tes_valve_position", "tes_guard_clipped", "tes_action_mode",
           "tes_tou_phase_for_state", "enable_tes_state_augmentation",
           "terminated", "truncated"],
    )

    assert_checkpoint_action_dim(args.checkpoint, expected_action_dim)
    model = DSAC_T.load(str(args.checkpoint), device="cpu")
    workspace_post = Path(env.get_wrapper_attr("workspace_path"))

    # R1b: reward-class-specific info fields the patched reward_fn MUST emit.
    # Sampled once at step 1 to catch silent reward_fn downgrades (e.g. the
    # previous while-hasattr bug that left PUE_TES_Reward in place).
    if args.reward_cls == "rl_cost":
        required_info_keys = ("cost_term", "cost_usd_step", "lmp_usd_per_mwh")
    elif args.reward_cls == "rl_green":
        required_info_keys = ("cost_term", "effective_price_usd_per_mwh", "pv_kw")
    else:
        required_info_keys = ()

    started = time.perf_counter()
    obs, _ = env.reset()
    obs_dim = int(np.asarray(obs).shape[0])
    term = trunc = False
    step = 0
    total_reward = 0.0
    while not (term or trunc):
        action, _ = model.predict(obs, deterministic=True)
        assert np.asarray(action).shape == (expected_action_dim,), (
            f"Expected {expected_action_dim}D M2-F1 policy action, got {np.asarray(action).shape}"
        )
        obs, reward, term, trunc, info = env.step(action)
        assert float(info.get("fixed_CRAH_Fan_DRL", np.nan)) == M2_FIXED_FAN_VALUE
        total_reward += float(reward)
        step += 1
        if step == 1 and required_info_keys:
            missing = [k for k in required_info_keys if k not in info]
            assert not missing, (
                f"reward_fn patch did not take effect: info missing {missing} "
                f"for reward_cls={args.reward_cls}; got keys={sorted(info.keys())}"
            )

    env.close()

    # Parse monitor.csv with pandas (avoids csv.DictReader duplicate-header issue)
    monitor_path = workspace_post / "episode-001" / "monitor.csv"
    df = pd.read_csv(monitor_path, index_col=False)
    # L1 fix (2026-04-19): guard against duplicate monitor columns — if a
    # wrapper re-introduces a name clash (see M1 TES_valve_position bug),
    # pandas silently renames the second column to `col.1` and a by-name read
    # would pick the wrong series. Fail loud instead of silently mis-reading.
    assert df.columns.is_unique, (
        f"Duplicate columns in {monitor_path}: "
        f"{df.columns[df.columns.duplicated()].tolist()}"
    )

    facility_energy = df["Electricity:Facility"].astype(float)
    ite_energy = df["ITE-CPU:InteriorEquipment:Electricity"].astype(float)
    temps = df["air_temperature"].astype(float)
    valves = df["TES_valve_wrapper_position"].astype(float)
    soc = df["TES_SOC"].astype(float)
    valve_active_fraction = float((valves.abs() > 0.05).mean())
    valve_saturation_fraction = float((valves.abs() > 0.95).mean())
    charge_fraction = float((valves < -0.05).mean())
    discharge_fraction = float((valves > 0.05).mean())

    # M2-F1 evaluation includes EnergyScaleWrapper, so monitor.csv energy
    # columns may already be MWh per timestep. Older runs without that wrapper
    # still contain raw Joules. Detect by magnitude for backward compatibility.
    if float(facility_energy.abs().median()) > 1.0e5:
        facility_MWh_step = (facility_energy / 3.6e9).to_numpy()
        ite_MWh_step = (ite_energy / 3.6e9).to_numpy()
        energy_unit = "J"
    else:
        facility_MWh_step = facility_energy.to_numpy()
        ite_MWh_step = ite_energy.to_numpy()
        energy_unit = "MWh"

    total_facility_MWh = float(facility_MWh_step.sum())
    total_ite_MWh = float(ite_MWh_step.sum())
    pue = total_facility_MWh / total_ite_MWh if total_ite_MWh > 0 else float("nan")
    comfort_pct = float((temps > 25.0).sum() / max(len(temps), 1) * 100)

    # Cost (USD): each row is one EnergyPlus timestep; hourly price/PV data is
    # repeated for all sub-hour timesteps inside that hour.
    steps_per_hour = M2_TIMESTEPS_PER_HOUR
    dt_hours = 1.0 / steps_per_hour
    lmp = pd.read_csv(args.price_csv)["price_usd_per_mwh"].to_numpy()
    hour_idx = (np.arange(len(facility_MWh_step)) // steps_per_hour) % len(lmp)
    lmp_step = lmp[hour_idx]
    cost_usd_annual = float((facility_MWh_step * lmp_step).sum())
    if "price_current_norm" in df.columns:
        price_signal = df["price_current_norm"].astype(float)
    else:
        price_signal = pd.Series(lmp_step, index=df.index, dtype=float)
    low_price = valves[price_signal <= price_signal.quantile(0.25)]
    high_price = valves[price_signal >= price_signal.quantile(0.75)]
    price_low_valve_mean = float(low_price.mean()) if len(low_price) else None
    price_high_valve_mean = float(high_price.mean()) if len(high_price) else None
    price_response_high_minus_low = (
        price_high_valve_mean - price_low_valve_mean
        if price_high_valve_mean is not None and price_low_valve_mean is not None
        else None
    )

    # PV self-consumption
    pv = pd.read_csv(args.pv_csv)["power_kw"].to_numpy()
    pv_step = pv[hour_idx]
    if "pv_current_ratio" in df.columns:
        pv_signal = df["pv_current_ratio"].astype(float)
    else:
        pv_signal = pd.Series(pv_step, index=df.index, dtype=float)
    low_pv = valves[pv_signal <= pv_signal.quantile(0.25)]
    high_pv = valves[pv_signal >= pv_signal.quantile(0.75)]
    pv_low_valve_mean = float(low_pv.mean()) if len(low_pv) else None
    pv_high_valve_mean = float(high_pv.mean()) if len(high_pv) else None
    pv_response_high_minus_low = (
        pv_high_valve_mean - pv_low_valve_mean
        if pv_high_valve_mean is not None and pv_low_valve_mean is not None
        else None
    )
    facility_kW_step = facility_MWh_step / dt_hours * 1000.0
    self_cons_kWh = np.minimum(facility_kW_step, pv_step).sum() * dt_hours
    facility_kWh = facility_MWh_step.sum() * 1000.0
    pv_self_consumption_pct = float(
        self_cons_kWh / facility_kWh * 100 if facility_kWh > 0 else 0
    )

    # TES activation: annual cycles + SOC daily amplitude
    # 1 cycle = |valve_fraction| × TES_MAX_FLOW integrated over each timestep / tank_volume
    # Rough proxy: total_charge_volume_kg / rho_water ≈ cumulative valve hours × 97.2 kg/s × 3600
    valve_abs_mean = float(valves.abs().mean())
    # M4 fix (2026-04-19): apply EMS P_5 deadband before the linear scaling.
    # Data/buildings/DRL_DC_{training,evaluation}.epJSON -> Program P_5:
    #   SET Flow = @Abs TES_Signal * Max_Flow   (Max_Flow = 389.0 kg/s, strictly linear)
    #   IF TES_Signal > 0.01         -> charge at Flow
    #   ELSEIF TES_Signal < -0.01    -> discharge at Flow
    #   (else)                       -> Flow = 0  (dead band, avoids valve chatter)
    # So the true instantaneous flow is `Flow * 1_{|v|>0.01}`, NOT `Flow` everywhere.
    # Without this mask, tiny residual valve positions from the incremental
    # wrapper inflate cycles_rough and can flip `tes_activated` spuriously.
    # No upper saturation is needed: the wrapper clips v to [-1, 1] upstream,
    # and P_5 has no other non-linearities (no PID, no hysteresis).
    # Each M2 timestep is 15 min at 389.0 kg/s max. |valve| fraction of that:
    #   mass_kg_step  = |v|_eff * 389.0 * (3600 / steps_per_hour)
    #   volume_m3     = mass_kg / 1000 (rho_water ~= 1000 kg/m^3)
    #   cycles        = sum(volume_m3) / tank_volume_m3
    valves_effective = np.where(valves.abs() > 0.01, valves.abs(), 0.0)
    cycles_rough = float(
        valves_effective.sum()
        * TES_MAX_FLOW_KG_S
        * (3600 / steps_per_hour)
        / 1000
        / TES_TANK_M3
    )
    # SOC daily amplitude: mean of (daily max - daily min)
    soc_np = soc.to_numpy()
    steps_per_day = 24 * steps_per_hour
    n_days = len(soc_np) // steps_per_day
    daily_amp = np.array([soc_np[d*steps_per_day:(d+1)*steps_per_day].max() - soc_np[d*steps_per_day:(d+1)*steps_per_day].min()
                          for d in range(n_days)])
    soc_daily_amplitude_mean = float(daily_amp.mean()) if len(daily_amp) else 0.0

    tes_activated = bool(cycles_rough >= 100 and soc_daily_amplitude_mean >= 0.3)

    return {
        "seed": args.tag,
        "reward_cls": args.reward_cls,
        "eval_design": args.eval_design,
        "eval_design_description": EVAL_DESIGNS[args.eval_design]["description"],
        "building_file": EVAL_DESIGNS[args.eval_design]["building_file"],
        "evaluation_flag": EVAL_DESIGNS[args.eval_design]["evaluation_flag"],
        "ITE_Set": EVAL_DESIGNS[args.eval_design]["ite_set"],
        "action_dim": action_dim,
        "obs_dim": obs_dim,
        "tes_action_semantics": args.tes_action_semantics,
        "tes_direction_deadband": args.tes_direction_deadband,
        "tes_option_hold_steps": args.tes_option_hold_steps,
        "enable_tes_state_augmentation": bool(args.enable_tes_state_augmentation),
        **provenance,
        "checkpoint": str(args.checkpoint),
        "steps": step,
        "total_reward": total_reward,
        "total_facility_MWh": total_facility_MWh,
        "total_ite_MWh": total_ite_MWh,
        "total_ITE_MWh": total_ite_MWh,
        "energy_unit_detected": energy_unit,
        "pue": pue,
        "comfort_violation_pct": comfort_pct,
        "mean_temperature_C": float(temps.mean()),
        "max_temperature_C": float(temps.max()),
        "p95_temperature_C": float(temps.quantile(0.95)),
        "cost_usd_annual": cost_usd_annual,
        "pv_self_consumption_pct": pv_self_consumption_pct,
        "tes_annual_cycles_rough": cycles_rough,
        "tes_soc_daily_amplitude_mean": soc_daily_amplitude_mean,
        "tes_activated": tes_activated,
        "valve_mean_abs": valve_abs_mean,
        "valve_active_fraction": valve_active_fraction,
        "valve_saturation_fraction": valve_saturation_fraction,
        "charge_fraction": charge_fraction,
        "discharge_fraction": discharge_fraction,
        "price_low_valve_mean": price_low_valve_mean,
        "price_high_valve_mean": price_high_valve_mean,
        "price_response_high_minus_low": price_response_high_minus_low,
        "pv_low_valve_mean": pv_low_valve_mean,
        "pv_high_valve_mean": pv_high_valve_mean,
        "pv_response_high_minus_low": pv_response_high_minus_low,
        "monitor_csv": str(monitor_path),
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="seedN tag for naming")
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument(
        "--eval-design",
        default="trainlike",
        choices=sorted(EVAL_DESIGNS),
        help=(
            "Evaluation load domain. 'trainlike' is the M2-F1 in-distribution "
            "gate (DRL_DC_training.epJSON, ITE_Set=0.45). 'official_ood' is "
            "the high-load stress test (DRL_DC_evaluation.epJSON, ITE_Set=1.0)."
        ),
    )
    ap.add_argument("--reward-cls", default="rl_cost", choices=["pue_tes", "rl_cost", "rl_green"])
    ap.add_argument("--epw", default=DEFAULT_EPW)
    ap.add_argument("--price-csv", default=DEFAULT_PRICE_CSV)
    ap.add_argument("--pv-csv", default=DEFAULT_PV_CSV)
    ap.add_argument("--dc-peak-load-kw", type=float, default=6000.0)
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
    ap.add_argument("--tes-high-price-threshold", type=float, default=0.75)
    ap.add_argument("--tes-low-price-threshold", type=float, default=-0.50)
    ap.add_argument("--tes-near-peak-threshold", type=float, default=0.40)
    ap.add_argument("--enable-tes-state-augmentation", action="store_true")
    ap.add_argument("--tes-action-semantics", choices=["signed_scalar", "direction_amp", "direction_amp_hold"], default="signed_scalar")
    ap.add_argument("--tes-direction-deadband", type=float, default=0.15)
    ap.add_argument("--tes-option-hold-steps", type=int, default=4)
    ap.add_argument("--out", type=Path, default=None, help="Output JSON path (default: runs/eval_m2/<tag>/result.json)")
    args = ap.parse_args()

    result = evaluate(args)
    print(json.dumps(result, indent=2))

    out = args.out or Path("runs/eval_m2") / args.tag / "result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
