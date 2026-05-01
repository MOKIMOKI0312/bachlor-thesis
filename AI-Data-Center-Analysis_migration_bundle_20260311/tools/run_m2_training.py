"""M2 training launcher — 32-dim obs / 4-dim action, Nanjing + Jiangsu TOU site.

Wrapper chain (inside to outside):
  EplusEnv (19 raw dims, 5 absolute actions, 15-min timestep) — built from Eplus-DC-Cooling-TES
  → TESTargetValveWrapper  (+1 dim → 20)      — full action[4] = target TES valve, rate_limit=0.25
  → FixedActionInsertWrapper                   — fixed full action[0] CRAH_Fan_DRL = 1.0
  → TimeEncodingWrapper    (-5 +1 +4 = 20)     — drop raw time & CRAH raw, merge CRAH_diff, add sin/cos
  → TempTrendWrapper       (+6 dim → 26)       — outdoor temperature lookahead trend (§6.1-C)
  → PriceSignalWrapper     (+3 dim → 29)
  → PVSignalWrapper        (+3 dim → 32)
  → EnergyScaleWrapper     (scale MWh meter obs only)
  → TESPriceShapingWrapper (training reward shaping only)
  → NormalizeObservation
  → LoggerWrapper

Final obs_dim = 32. The exposed agent action is
[CT_Pump_DRL, CRAH_T_DRL, Chiller_T_DRL, TES_DRL].  M2 does not include a
workload action; ITE load stays on the fixed epJSON schedule unless changed
outside this agent action stack.

Reward class selectable via --reward-cls {rl_cost, rl_green}. Defaults to
rl_cost. RL_Cost and RL_Green accept the PriceSignalWrapper / PVSignalWrapper
instances at construction (so they can read raw USD/MWh and kW each step
without re-parsing CSVs).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

# Torch + EnergyPlus both ship libiomp5md.dll on Windows; allow duplicate
# (unsafe but universally used workaround — same as M1 env setup).
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gymnasium as gym
import numpy as np
import torch
torch.set_num_threads(2)
torch.set_num_interop_threads(1)
from stable_baselines3 import SAC
from stable_baselines3.common.callbacks import CallbackList, CheckpointCallback

from sinergym.utils.common import get_ids
from sinergym.utils.training_monitor import StatusCallback, make_probe_logger_factory
from sinergym.utils.wrappers import LoggerWrapper, NormalizeObservation
from sinergym.envs.tes_wrapper import (
    FixedActionInsertWrapper,
    TESPriceShapingWrapper,
    TESTargetValveWrapper,
)
from sinergym.envs.time_encoding_wrapper import TimeEncodingWrapper
from sinergym.envs.temp_trend_wrapper import TempTrendWrapper
from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
from sinergym.envs.pv_signal_wrapper import PVSignalWrapper
from sinergym.envs.energy_scale_wrapper import EnergyScaleWrapper
from tools.m2_action_guard import M2_FIXED_FAN_VALUE, assert_m2_4d_checkpoint

# M2-E3b-v3 (2026-04-22): CAISO → Nanjing + Jiangsu TOU
# 切换动机：CAISO 重尾 reward (kurtosis=120) 触发 DSAC-T critic σ 爆炸
# 新数据源：Jiangsu 2025 TOU 合成 (kurtosis ≈ -1.3) + Nanjing TMYx + Nanjing PV
DEFAULT_EPW = "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
DEFAULT_PRICE_CSV = "Data/prices/Jiangsu_TOU_2025_hourly.csv"
DEFAULT_PV_CSV = "Data/pv/CHN_Nanjing_PV_6MWp_hourly.csv"


def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def build_env(args) -> gym.Env:
    """Build the full M2 wrapper stack."""
    environment = "Eplus-DC-Cooling-TES"
    building_file = ["DRL_DC_training.epJSON"]
    weather_files = [args.epw]
    config_params = {
        "runperiod": (1, 1, 2025, 31, 12, 2025),
        "timesteps_per_hour": 4,
    }
    if not args.disable_tes_init_randomization:
        config_params.update({
            "tes_initial_soc_range": (args.tes_init_soc_low, args.tes_init_soc_high),
            "tes_soc_cold_temp": 6.0,
            "tes_soc_hot_temp": 12.0,
            "tes_charge_setpoint": 6.0,
            "tes_initial_schedule_until": "00:15",
        })
    stamp = datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
    env_name = f"{stamp}_m2_{args.reward_cls}_seed{args.seed}"

    env = gym.make(
        environment,
        env_name=env_name,
        building_file=building_file,
        weather_files=weather_files,
        config_params=config_params,
    )
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
    env = TimeEncodingWrapper(env)
    # H2c: 6-dim outdoor temperature trend features (tech route §6.1-C)
    env = TempTrendWrapper(
        env,
        epw_path=Path("Data/weather") / args.epw,
        lookahead_hours=6,
    )
    env = PriceSignalWrapper(env, price_csv_path=args.price_csv, lookahead_hours=6)
    env = PVSignalWrapper(
        env, pv_csv_path=args.pv_csv, dc_peak_load_kw=args.dc_peak_load_kw, lookahead_hours=6
    )
    # B3 fix (2026-04-23, corrected): Electricity:Facility (idx 13) and
    # ITE-CPU:InteriorEquipment:Electricity (idx 14) are EnergyPlus Output:Meter
    # cumulative-Joules values ~3e10 J/h. obs[12]=TES_avg_temp (NOT energy! 0-indexed,
    # see expected_names in H2d assertion). Other obs dims sit in much smaller ranges.
    # Rescale J/h -> MWh/h (÷3.6e9) so NormalizeObservation's RunningMeanStd doesn't
    # lose float32 precision absorbing 10^10-magnitude samples.
    env = EnergyScaleWrapper(env, energy_indices=[13, 14], scale=1.0 / 3.6e9)
    if not args.disable_tes_tou_shaping:
        env = TESPriceShapingWrapper(
            env,
            gamma=args.gamma_pbrs,
            kappa=args.tes_target_soc_kappa,
            teacher_initial_weight=args.tes_teacher_weight,
            teacher_decay_episodes=args.tes_teacher_decay_episodes,
            valve_penalty_weight=args.tes_valve_penalty_weight,
            invalid_action_penalty_weight=args.tes_invalid_action_penalty_weight,
            high_price_threshold=args.tes_high_price_threshold,
            low_price_threshold=args.tes_low_price_threshold,
            near_peak_threshold=args.tes_near_peak_threshold,
            target_soc_high=args.tes_target_soc_high,
            target_soc_low=args.tes_target_soc_low,
            target_soc_neutral=args.tes_target_soc_neutral,
            soc_charge_limit=args.tes_soc_charge_limit,
            soc_discharge_limit=args.tes_soc_discharge_limit,
        )
    return env


def attach_reward(env: gym.Env, args) -> gym.Env:
    """Inject M2 reward class by swapping EplusEnv.reward_fn AFTER the wrapper
    chain is built (so the reward can reach into wrapped env for price/PV).
    Reward is computed inside EplusEnv.step() from obs_dict."""
    if args.reward_cls == "pue_tes":
        # No swap — env already uses PUE_TES_Reward per __init__.py registration
        return env

    from sinergym.utils.rewards import RL_Cost_Reward, RL_Green_Reward

    # Build reward fn with data series loaded inline (not via wrapper refs —
    # keeps reward_fn standalone & picklable for SB3 save).
    import pandas as pd

    price_series = pd.read_csv(args.price_csv)["price_usd_per_mwh"].to_numpy(dtype=np.float32)
    pv_series = pd.read_csv(args.pv_csv)["power_kw"].to_numpy(dtype=np.float32)

    kwargs = dict(
        temperature_variables=["air_temperature"],
        energy_variables=["Electricity:Facility"],
        ITE_variables=["ITE-CPU:InteriorEquipment:Electricity"],
        range_comfort_winter=(18.0, 25.0),
        range_comfort_summer=(18.0, 25.0),
        energy_weight=0.5,
        lambda_energy=1.0,
        lambda_temperature=1.0,  # M2-E3b: 3.0 → 1.0（M1 λ=3 诊断出 comfort 项比 energy 大 5-9×, 4/4 seed 违规 >90%, 确认主导病因, 回退 E0.3 验证值）
        soc_variable="TES_SOC",
        soc_low=0.15,
        soc_high=0.85,
        soc_warn_low=0.15,   # M2-E3b-v4 P3 (2026-04-23): 放松 soc 约束，让 cost_term 主导 TOU 学习
        soc_warn_high=0.85,  # M2-E3b-v4 P3 (2026-04-23): 放松 soc 约束，让 cost_term 主导 TOU 学习
        lambda_soc=2.0,      # M2-E3b-v4 P3 (2026-04-23): 放松 soc 约束，让 cost_term 主导 TOU 学习
        lambda_soc_warn=1.0, # M2-E3b-v4 P3 (2026-04-23): 放松 soc 约束，让 cost_term 主导 TOU 学习
        price_series=price_series,
        alpha=args.alpha,
        beta=args.beta,
        kappa_shape=args.kappa_shape,
        gamma_pbrs=args.gamma_pbrs,
        tau_decay=args.tau_decay,
        p_peak_ref=args.p_peak_ref,
    )
    if args.reward_cls == "rl_cost":
        cls = RL_Cost_Reward
    elif args.reward_cls == "rl_green":
        cls = RL_Green_Reward
        kwargs["pv_series"] = pv_series
        kwargs["c_pv"] = args.c_pv
        kwargs["pv_threshold_kw"] = args.pv_threshold_kw
    else:
        raise ValueError(f"Unknown reward class: {args.reward_cls}")

    # R1 fix (2026-04-19): gymnasium.Wrapper.__getattr__ forwards attribute
    # lookup to self.env, so `hasattr(wrapper, "reward_fn")` is always True
    # for any wrapper above EplusEnv. The previous while-loop exited after
    # zero iterations and patched only the outermost wrapper, leaving
    # env.unwrapped.reward_fn as the default PUE_TES_Reward. Use
    # env.unwrapped to hit the innermost EplusEnv directly.
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
    print(f"Reward class swapped to {cls.__name__}; alpha={args.alpha}, beta={args.beta}")
    return env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=2)
    parser.add_argument("--timesteps", type=int)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--model-name", default="m2_model")
    parser.add_argument("--checkpoint-episodes", type=int, default=10)
    parser.add_argument("--status-file")
    parser.add_argument("--status-every-steps", type=int, default=500)
    parser.add_argument("--probe-step-sample-interval", type=int, default=12)
    parser.add_argument("--probe-recent-window", type=int, default=192)
    parser.add_argument("--algo", default="dsac_t", choices=["sac", "dsac_t"])
    parser.add_argument("--xi", type=float, default=3.0)
    parser.add_argument("--eps-sigma", type=float, default=0.1)
    parser.add_argument("--eps-omega", type=float, default=0.1)
    parser.add_argument("--resume", type=str, default=None)
    parser.add_argument("--wandb", action="store_true")
    parser.add_argument("--wandb-project", default="dc-cooling-optimization")
    parser.add_argument("--wandb-group", default=None)

    # M2-specific args
    parser.add_argument("--reward-cls", default="rl_cost", choices=["pue_tes", "rl_cost", "rl_green"])
    parser.add_argument("--epw", default=DEFAULT_EPW)
    parser.add_argument("--price-csv", default=DEFAULT_PRICE_CSV)
    parser.add_argument("--pv-csv", default=DEFAULT_PV_CSV)
    parser.add_argument("--dc-peak-load-kw", type=float, default=6000.0)
    # M2-E3b-v4 (2026-04-23): cost 缩放 5e-4 → 2e-3
    # 目标：在 Jiangsu TOU 下让 cost_term 峰谷量级 >= soc/comfort 惩罚，
    # 避免 agent 感受不到 TOU 峰谷信号。2e-3 × 10.7 MWh × 29 USD/MWh ≈
    # -0.62（谷段），× 150 ≈ -3.2（peak 段，被 RL_Cost_Reward 内部 ±3.0 clip
    # 轻微截断）；scarcity 事件保持防御。
    # 注意：alpha 不能塞进 sinergym/__init__.py 的 reward_kwargs——PUE_Reward 基类
    # __init__ 无 **kwargs，会 TypeError；必须通过 --alpha CLI 注入 RL_Cost_Reward
    parser.add_argument("--alpha", type=float, default=2e-3, help="Cost reward coefficient (2e-3 → cost_term typical -0.5 at shoulder tier 83 USD/MWh, -3.0 clip at super-peak, M2-E3b-v4 retuned)")
    parser.add_argument("--beta", type=float, default=1.0, help="Comfort penalty coefficient")
    parser.add_argument("--c-pv", type=float, default=0.0, help="Virtual green-price USD/MWh (RL-Green only)")
    parser.add_argument("--pv-threshold-kw", type=float, default=100.0, help="PV kW above which green price applies")
    parser.add_argument("--tes-init-soc-low", type=float, default=0.20, help="Lower bound for per-episode physical TES initial SOC randomization")
    parser.add_argument("--tes-init-soc-high", type=float, default=0.80, help="Upper bound for per-episode physical TES initial SOC randomization")
    parser.add_argument("--disable-tes-init-randomization", action="store_true", help="Keep TES initial state deterministic at the epJSON setpoint")
    parser.add_argument("--tes-valve-rate-limit", type=float, default=0.25, help="Rate limit for target TES valve command per timestep")
    parser.add_argument("--tes-guard-soc-low", type=float, default=0.10, help="SOC below which TES discharge commands are clipped toward neutral")
    parser.add_argument("--tes-guard-soc-high", type=float, default=0.90, help="SOC above which TES charge commands are clipped toward neutral")
    parser.add_argument("--disable-tes-tou-shaping", action="store_true", help="Disable M2-F1 TES TOU shaping wrapper")
    parser.add_argument("--tes-target-soc-kappa", type=float, default=1.0, help="Target-SOC PBRS potential scale")
    parser.add_argument("--tes-teacher-weight", type=float, default=0.0, help="Initial short-term TES direction teacher weight; default 0 keeps M2-F1 PBRS-only")
    parser.add_argument("--tes-teacher-decay-episodes", type=float, default=15.0, help="Episode count over which TES teacher weight decays to zero")
    parser.add_argument("--tes-valve-penalty-weight", type=float, default=0.02, help="Quadratic TES valve regularization weight")
    parser.add_argument("--tes-invalid-action-penalty-weight", type=float, default=0.0, help="Linear penalty weight for raw TES charge/discharge intents beyond SOC limits; pass 0.05 for M2-F1 invalid-action shaping experiments")
    parser.add_argument("--tes-high-price-threshold", type=float, default=0.75, help="price_current_norm threshold for high-price discharge target")
    parser.add_argument("--tes-low-price-threshold", type=float, default=-0.50, help="price_current_norm threshold for low-price charge target")
    parser.add_argument("--tes-near-peak-threshold", type=float, default=0.40, help="price_hours_to_next_peak_norm threshold for near-peak charge preparation")
    parser.add_argument("--tes-target-soc-high", type=float, default=0.85, help="Target SOC before upcoming peaks")
    parser.add_argument("--tes-target-soc-low", type=float, default=0.30, help="Target SOC during high-price periods")
    parser.add_argument("--tes-target-soc-neutral", type=float, default=0.50, help="Target SOC during neutral price periods")
    parser.add_argument("--tes-soc-charge-limit", type=float, default=0.85, help="SOC above which low-price teacher stops encouraging charge")
    parser.add_argument("--tes-soc-discharge-limit", type=float, default=0.20, help="SOC below which high-price teacher stops encouraging discharge")
    # Legacy DPBA PBRS (analysis/pbrs_upgrade_DPBA_2026-04-23.md). M2-F1
    # defaults this off so the active shaping signal is the target-SOC PBRS
    # in TESPriceShapingWrapper. Pass --kappa-shape 0.8 for a DPBA ablation.
    parser.add_argument("--kappa-shape", type=float, default=0.0, help="Legacy DPBA potential scaling; default 0 disables it so target-SOC PBRS is the only default TES PBRS")
    parser.add_argument("--gamma-pbrs", type=float, default=0.99, help="PBRS discount (must match SAC/DSAC-T gamma)")
    parser.add_argument("--tau-decay", type=float, default=4.0, help="DPBA exp-decay scale in hours (shorter = sharper near-peak signal)")
    parser.add_argument("--p-peak-ref", type=float, default=0.80, help="Reference peak price_norm (Jiangsu TOU: $160-200 / 250 ≈ 0.80)")
    # M2-PBRS-v2 (2026-04-23, Xu 2023 discrete SAC): target_entropy = -|A|/3.
    # With CRAH_Fan_DRL fixed outside the agent, |A|=4.
    parser.add_argument("--target-entropy", type=float, default=-(4.0 / 3.0), help="SAC/DSAC-T target entropy (Xu 2023: -dim(A)/3 = -1.3333 for 4-dim action)")
    args = parser.parse_args()

    if "Eplus-DC-Cooling-TES" not in get_ids():
        raise RuntimeError("Eplus-DC-Cooling-TES is not registered")

    set_global_seed(args.seed)

    env = build_env(args)
    env = attach_reward(env, args)

    # Verify shapes before moving on.
    # Post H2a/H2b/H2c/H2d: 20 (TimeEncoding output) + 6 (TempTrend) + 3 (Price)
    #                       + 3 (PV) = 32.
    expected_obs_dim = 20 + 6 + 3 + 3  # 32
    assert env.observation_space.shape == (expected_obs_dim,), (
        f"Expected M2 obs_dim={expected_obs_dim}, got {env.observation_space.shape}"
    )
    assert env.action_space.shape == (4,), (
        f"Expected action_dim=4, got {env.action_space.shape}"
    )
    assert np.allclose(env.action_space.low, np.array([0.0, 0.0, 0.0, -1.0], dtype=np.float32))
    assert np.allclose(env.action_space.high, np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32))
    print(
        f"Env wrapper stack OK: obs_dim={expected_obs_dim}, action_dim=4, "
        f"fixed_CRAH_Fan_DRL={M2_FIXED_FAN_VALUE}"
    )

    obs_vars = env.get_wrapper_attr("observation_variables")
    act_vars = env.get_wrapper_attr("action_variables")
    expected_act_vars = ["CT_Pump_DRL", "CRAH_T_DRL", "Chiller_T_DRL", "TES_DRL"]
    assert list(act_vars) == expected_act_vars, (
        f"M2-F1 action_variables mismatch: expected {expected_act_vars}, got {list(act_vars)}"
    )

    # [H2d] Check observation_variables names match tech route §6.1 layout.
    # 32 dims total; wrapper application order: TES → TimeEncoding → TempTrend
    # → Price → PV. Names follow the wrapper append order, not the
    # abstract §6.1 group order (groups are interleaved accordingly).
    expected_names = [
        # B: outdoor 2
        'outdoor_temperature', 'outdoor_wet_temperature',
        # D: DC 9 (air_T, air_H, CT, CW, CRAH_diff, 4 actuators)
        'air_temperature', 'air_humidity', 'CT_temperature', 'CW_temperature',
        'CRAH_temp_diff',
        'act_Fan', 'act_Chiller_T', 'act_Chiller_Pump', 'act_CT_Pump',
        # I (partial): TES SOC + avg_temp (valve injected by TESTargetValveWrapper at end)
        'TES_SOC', 'TES_avg_temp',
        # E: energy 2
        'Electricity:Facility', 'ITE-CPU:InteriorEquipment:Electricity',
        # I (remainder): TES valve position from TESTargetValveWrapper
        'TES_valve_wrapper_position',
        # A: sin/cos time 4
        'hour_sin', 'hour_cos', 'month_sin', 'month_cos',
        # C: temperature trend 6 (H2c)
        'temperature_slope', 'temp_mean', 'temp_std', 'temp_percentile',
        'time_to_next_temp_peak', 'time_to_next_temp_valley',
        # G: price 3 (TOU-aware post bc10db0: replaced polyfit slope+mean with tier-delta+hours_to_peak)
        'price_current_norm', 'price_delta_next_1h', 'price_hours_to_next_peak_norm',
        # H: PV 3
        'pv_current_ratio', 'pv_future_slope', 'time_to_pv_peak',
    ]
    actual_names = list(obs_vars)
    assert actual_names == expected_names, (
        f"observation_variables mismatch (tech route §6.1).\n"
        f"  expected ({len(expected_names)}): {expected_names}\n"
        f"  actual   ({len(actual_names)}): {actual_names}"
    )
    print(f"observation_variables name check OK ({len(actual_names)} dims)")
    env = NormalizeObservation(env)
    env = LoggerWrapper(
        env,
        logger_class=make_probe_logger_factory(
            observation_variables=obs_vars,
            action_variables=act_vars,
            step_sample_interval=args.probe_step_sample_interval,
            recent_step_window=args.probe_recent_window,
        ),
        monitor_header=["timestep"] + list(obs_vars) + list(act_vars)
        + [
            "time (hours)", "reward", "energy_term", "ITE_term", "comfort_term", "cost_term",
            "fixed_CRAH_Fan_DRL",
            "tes_valve_target", "tes_valve_position", "tes_guard_clipped", "tes_action_mode",
            "tes_soc_target", "tes_pbrs_term", "tes_teacher_term", "tes_teacher_weight",
            "tes_valve_penalty", "tes_invalid_action_penalty", "tes_shaping_total",
            "terminated", "truncated",
        ],
    )

    # B4 fix (2026-04-23): warmup RunningMeanStd with a baseline-policy episode,
    # then freeze. Prevents non-stationary obs normalization from destabilizing
    # DSAC-T critic during ep60-80 transient window. Skipped on --resume so we
    # keep the obs_rms that rides along with the checkpointed policy.
    #
    # B4-v2 (2026-04-23): use random actions during warmup so the TES valve
    # dimension covers its range, then clamp near-zero variances to avoid
    # excessive normalization gain.
    #   (1) Use random actions (action_space.sample).
    #   (2) Clamp obs_rms.var to a floor of 1e-2 after freezing, bounding max
    #       normalization amplification to 10× (= 1/sqrt(1e-2)).
    if not args.resume:
        print("[B4] Warming up NormalizeObservation with 1 random-policy episode (seed-consistent)...")
        warmup_obs, _ = env.reset()
        done = truncated = False
        # Deterministic-but-independent warmup seed (offset by 1000 so the
        # post-warmup policy training still sees its intended action_space seed).
        env.action_space.seed(args.seed + 1000)
        step_count = 0
        while not (done or truncated):
            action = env.action_space.sample()
            warmup_obs, _, done, truncated, _ = env.step(action)
            step_count += 1
        print(f"[B4] Warmup done: {step_count} steps. Freezing obs_rms.")
        env.deactivate_update()
        print(f"[B4] automatic_update after freeze: {env.get_wrapper_attr('automatic_update')}")

        # B4-v2 safety: clamp obs_rms.var to a floor so dims with zero/near-zero
        # activity during warmup don't amplify by 10^4×. Floor 1e-2 caps max
        # amplification at 10× (= 1/sqrt(1e-2)).
        var_floor = 1e-2
        try:
            obs_rms = env.get_wrapper_attr('obs_rms')
        except (AttributeError, KeyError):
            def _find_obs_rms(e):
                while hasattr(e, 'env'):
                    if hasattr(e, 'obs_rms'):
                        return e.obs_rms
                    e = e.env
                raise RuntimeError("obs_rms not found in wrapper chain")
            obs_rms = _find_obs_rms(env)
        n_clipped = int((obs_rms.var < var_floor).sum())
        min_var_before = float(obs_rms.var.min())
        obs_rms.var = np.maximum(obs_rms.var, var_floor)
        print(
            f"[B4] var floor clamp: {n_clipped}/{len(obs_rms.var)} dims raised to {var_floor} "
            f"(min before clamp: {min_var_before:.2e}, min after: {float(obs_rms.var.min()):.2e})"
        )

    # M2-D2 网络升级：从 M1 的 [512] 1 层升级到 [256, 256] 2 层
    # 理由：32 维 obs + 异构时序/价格/PV/TES 信号需要 2 层才能学"条件组合型"决策
    # 参考：DSAC-T 原论文 + SB3 默认 + Xiao & You 2026 都用 [256, 256]
    policy_kwargs = dict(net_arch=[256, 256])
    if args.algo == "dsac_t":
        from tools.dsac_t import DSAC_T

        AlgoClass = DSAC_T
    else:
        AlgoClass = SAC

    if args.resume:
        print(f"Resuming from: {args.resume}")
        assert_m2_4d_checkpoint(args.resume)
        model = AlgoClass.load(args.resume, env=env, device=args.device)
        replay_path = args.resume.replace(".zip", "_replay_buffer.pkl")
        if os.path.exists(replay_path):
            print(
                f"Replay buffer not auto-loaded under M2-F1 fixed-fan guard: {replay_path}. "
                "Start a fresh 4D replay buffer unless it has been explicitly audited."
            )
    else:
        extra = {}
        if args.algo == "dsac_t":
            extra = {"xi": args.xi, "eps_sigma": args.eps_sigma, "eps_omega": args.eps_omega}
        model = AlgoClass(
            "MlpPolicy",
            env,
            batch_size=512,
            learning_rate=5e-5,   # M2-E3b: 1e-4 → 5e-5（lr=1e-4 下 3/4 seed policy collapse, 回退 M1 验证值恢复 DSAC-T R3 阻尼裕度, 保留 [256,256] 网络）
            learning_starts=8760,
            gamma=0.99,
            target_entropy=args.target_entropy,  # M2-PBRS-v2: -dim(A)/3 = -1.3333 for 4-dim action.
            policy_kwargs=policy_kwargs,
            verbose=1,
            seed=args.seed,
            device=args.device,
            **extra,
        )

    episodes = args.episodes
    timesteps_per_episode = env.get_wrapper_attr("timestep_per_episode") - 1
    if args.timesteps is not None:
        timesteps = int(args.timesteps)
    else:
        timesteps = episodes * timesteps_per_episode

    workspace_path = Path(env.get_wrapper_attr("workspace_path"))
    checkpoints_path = workspace_path / "checkpoints"
    checkpoints_path.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    callbacks = [
        CheckpointCallback(
            save_freq=max(1, args.checkpoint_episodes * timesteps_per_episode),
            save_path=str(checkpoints_path),
            name_prefix=args.model_name,
            save_replay_buffer=True,
            save_vecnormalize=False,
        )
    ]
    if args.status_file:
        callbacks.append(
            StatusCallback(
                status_file=Path(args.status_file),
                workspace_path=workspace_path,
                timesteps_per_episode=timesteps_per_episode,
                started=started,
                update_every_steps=args.status_every_steps,
            )
        )
    if args.wandb:
        from tools.wandb_callback import WandbCallback

        wandb_name = f"{args.wandb_group or 'M2'}-seed{args.seed}"
        callbacks.append(
            WandbCallback(
                project=args.wandb_project,
                name=wandb_name,
                group=args.wandb_group,
                tags=["M2", args.reward_cls, f"seed{args.seed}"],
                config={
                    "seed": args.seed,
                    "episodes": episodes,
                    "reward_cls": args.reward_cls,
                    "alpha": args.alpha,
                    "beta": args.beta,
                    "weather": args.epw,
                },
                log_interval=1000,
            )
        )

    model.learn(
        total_timesteps=timesteps,
        log_interval=1,
        callback=CallbackList(callbacks),
        reset_num_timesteps=not bool(args.resume),
    )
    elapsed = time.perf_counter() - started

    model_path = workspace_path / args.model_name
    model.save(str(model_path))
    model.save_replay_buffer(str(workspace_path / f"{args.model_name}_replay_buffer.pkl"))
    env.close()

    print(
        json.dumps(
            {
                "episodes": episodes,
                "timesteps": timesteps,
                "timesteps_per_episode": timesteps_per_episode,
                "seed": args.seed,
                "reward_cls": args.reward_cls,
                "alpha": args.alpha,
                "beta": args.beta,
                "kappa_shape": args.kappa_shape,
                "gamma_pbrs": args.gamma_pbrs,
                "elapsed_seconds": elapsed,
                "workspace_path": str(workspace_path),
                "model_path": str(model_path) + ".zip",
                "checkpoints_path": str(checkpoints_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
