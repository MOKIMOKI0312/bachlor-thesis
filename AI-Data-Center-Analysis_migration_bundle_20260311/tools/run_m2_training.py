"""M2 training launcher — 41-dim obs / 6-dim action, CAISO SiliconValley site.

Wrapper chain (inside to outside):
  EplusEnv (19 raw dims, 6 absolute actions)   — built from Eplus-DC-Cooling-TES
  → TESIncrementalWrapper  (+1 dim → 20)      — action[5] = Δvalve
  → TimeEncodingWrapper    (-5 +1 +4 = 20)     — drop raw time & CRAH raw, merge CRAH_diff, add sin/cos
  → TempTrendWrapper       (+6 dim → 26)       — outdoor temperature lookahead trend (§6.1-C)
  → PriceSignalWrapper     (+3 dim → 29)
  → PVSignalWrapper        (+3 dim → 32)
  → WorkloadWrapper        (+9 dim → 41)       — action[4] = discretised workload
  → NormalizeObservation
  → LoggerWrapper

Final obs_dim = 41 (tech route §6.1).

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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gymnasium as gym
import numpy as np
import torch
from stable_baselines3 import SAC
from stable_baselines3.common.callbacks import CallbackList, CheckpointCallback

from sinergym.utils.common import get_ids
from sinergym.utils.training_monitor import StatusCallback, make_probe_logger_factory
from sinergym.utils.wrappers import LoggerWrapper, NormalizeObservation
from sinergym.envs.tes_wrapper import TESIncrementalWrapper
from sinergym.envs.time_encoding_wrapper import TimeEncodingWrapper
from sinergym.envs.temp_trend_wrapper import TempTrendWrapper
from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
from sinergym.envs.pv_signal_wrapper import PVSignalWrapper
from sinergym.envs.workload_wrapper import WorkloadWrapper
from sinergym.envs.energy_scale_wrapper import EnergyScaleWrapper

# M2-E3b-v3 (2026-04-22): CAISO → Nanjing + Jiangsu TOU
# 切换动机：CAISO 重尾 reward (kurtosis=120) 触发 DSAC-T critic σ 爆炸
# 新数据源：Jiangsu 2025 TOU 合成 (kurtosis ≈ -1.3) + Nanjing TMYx + Nanjing PV
DEFAULT_EPW = "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
DEFAULT_PRICE_CSV = "Data/prices/Jiangsu_TOU_2025_hourly.csv"
DEFAULT_PV_CSV = "Data/pv/CHN_Nanjing_PV_6MWp_hourly.csv"
DEFAULT_IT_TRACE = "Data/AI Trace Data/Earth_hourly.csv"


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
        "timesteps_per_hour": 1,
    }
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

    env = TESIncrementalWrapper(env, valve_idx=5, delta_max=0.20)
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
    env = WorkloadWrapper(
        env,
        it_trace_csv=args.it_trace,
        workload_idx=4,
        flexible_fraction=args.flexible_fraction,
    )
    # B3 fix (2026-04-23, corrected): Electricity:Facility (idx 13) and
    # ITE-CPU:InteriorEquipment:Electricity (idx 14) are EnergyPlus Output:Meter
    # cumulative-Joules values ~3e10 J/h. obs[12]=TES_avg_temp (NOT energy! 0-indexed,
    # see expected_names in H2d assertion). All other 39 obs dims sit in [-5e-6, 1560].
    # Rescale J/h -> MWh/h (÷3.6e9) so NormalizeObservation's RunningMeanStd doesn't
    # lose float32 precision absorbing 10^10-magnitude samples.
    env = EnergyScaleWrapper(env, energy_indices=[13, 14], scale=1.0 / 3.6e9)
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
        soc_warn_low=0.30,
        soc_warn_high=0.70,
        lambda_soc=5.0,
        lambda_soc_warn=3.0,
        price_series=price_series,
        alpha=args.alpha,
        beta=args.beta,
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
    parser.add_argument("--it-trace", default=DEFAULT_IT_TRACE)
    parser.add_argument("--dc-peak-load-kw", type=float, default=6000.0)
    parser.add_argument("--flexible-fraction", type=float, default=0.3)
    # M2-E3b: cost 缩放 1e-3 → 5e-4
    # 目标：cost_term 典型值 ~-0.87（vs comfort_term -0.6），量级可比
    # scarcity 事件 cost_term ~-6（vs extreme comfort -4.5）不超标
    # 注意：alpha 不能塞进 sinergym/__init__.py 的 reward_kwargs——PUE_Reward 基类
    # __init__ 无 **kwargs，会 TypeError；必须通过 --alpha CLI 注入 RL_Cost_Reward
    parser.add_argument("--alpha", type=float, default=5e-4, help="Cost reward coefficient (5e-4 → cost_term ~-0.87 USD/h comparable to comfort_term, M2-E3b tuned)")
    parser.add_argument("--beta", type=float, default=1.0, help="Comfort penalty coefficient")
    parser.add_argument("--c-pv", type=float, default=0.0, help="Virtual green-price USD/MWh (RL-Green only)")
    parser.add_argument("--pv-threshold-kw", type=float, default=100.0, help="PV kW above which green price applies")
    args = parser.parse_args()

    if "Eplus-DC-Cooling-TES" not in get_ids():
        raise RuntimeError("Eplus-DC-Cooling-TES is not registered")

    set_global_seed(args.seed)

    env = build_env(args)
    env = attach_reward(env, args)

    # Verify shapes before moving on.
    # Post H2a/H2b/H2c/H2d: 20 (TimeEncoding output) + 6 (TempTrend) + 3 (Price)
    #                       + 3 (PV) + 9 (Workload) = 41, aligned with tech route §6.1.
    expected_obs_dim = 20 + 6 + 3 + 3 + 9  # 41
    assert env.observation_space.shape == (expected_obs_dim,), (
        f"Expected M2 obs_dim={expected_obs_dim}, got {env.observation_space.shape}"
    )
    assert env.action_space.shape == (6,), (
        f"Expected action_dim=6, got {env.action_space.shape}"
    )
    print(f"Env wrapper stack OK: obs_dim={expected_obs_dim}, action_dim=6")

    obs_vars = env.get_wrapper_attr("observation_variables")
    act_vars = env.get_wrapper_attr("action_variables")

    # [H2d] Check observation_variables names match tech route §6.1 layout.
    # 41 dims total; wrapper application order: TES → TimeEncoding → TempTrend
    # → Price → PV → Workload. Names follow the wrapper append order, not the
    # abstract §6.1 group order (groups are interleaved accordingly).
    expected_names = [
        # B: outdoor 2
        'outdoor_temperature', 'outdoor_wet_temperature',
        # D: DC 9 (air_T, air_H, CT, CW, CRAH_diff, 4 actuators)
        'air_temperature', 'air_humidity', 'CT_temperature', 'CW_temperature',
        'CRAH_temp_diff',
        'act_Fan', 'act_Chiller_T', 'act_Chiller_Pump', 'act_CT_Pump',
        # I (partial): TES SOC + avg_temp (valve injected by TESIncrementalWrapper at end)
        'TES_SOC', 'TES_avg_temp',
        # E: energy 2
        'Electricity:Facility', 'ITE-CPU:InteriorEquipment:Electricity',
        # I (remainder): TES valve position from TESIncrementalWrapper
        'TES_valve_wrapper_position',
        # A: sin/cos time 4
        'hour_sin', 'hour_cos', 'month_sin', 'month_cos',
        # C: temperature trend 6 (H2c)
        'temperature_slope', 'temp_mean', 'temp_std', 'temp_percentile',
        'time_to_next_temp_peak', 'time_to_next_temp_valley',
        # G: price 3
        'price_current_norm', 'price_future_slope', 'price_future_mean',
        # H: PV 3
        'pv_current_ratio', 'pv_future_slope', 'time_to_pv_peak',
        # F: queue 9
        'workload_current_utilization', 'workload_queue_norm',
        'workload_oldest_age_norm', 'workload_avg_age_norm',
        'workload_hist_0_6h', 'workload_hist_6_12h',
        'workload_hist_12_18h', 'workload_hist_18_24h',
        'workload_hist_24h_plus',
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
        + ["time (hours)", "reward", "energy_term", "ITE_term", "comfort_term", "cost_term", "terminated", "truncated"],
    )

    # B4 fix (2026-04-23): warmup RunningMeanStd with a baseline-policy episode,
    # then freeze. Prevents non-stationary obs normalization from destabilizing
    # DSAC-T critic during ep60-80 transient window. Skipped on --resume so we
    # keep the obs_rms that rides along with the checkpointed policy.
    if not args.resume:
        print("[B4] Warming up NormalizeObservation with 1 baseline-policy episode...")
        warmup_obs, _ = env.reset()
        done = truncated = False
        center_action = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.0], dtype=np.float32)
        step_count = 0
        while not (done or truncated):
            warmup_obs, _, done, truncated, _ = env.step(center_action)
            step_count += 1
        print(f"[B4] Warmup done: {step_count} steps. Freezing obs_rms.")
        env.deactivate_update()
        print(f"[B4] automatic_update after freeze: {env.get_wrapper_attr('automatic_update')}")

    # M2-D2 网络升级：从 M1 的 [512] 1 层升级到 [256, 256] 2 层
    # 理由：41 维 obs + 9 类异构信号需要 2 层才能学"条件组合型"决策
    # 参考：DSAC-T 原论文 + SB3 默认 + Xiao & You 2026 都用 [256, 256]
    policy_kwargs = dict(net_arch=[256, 256])
    if args.algo == "dsac_t":
        from tools.dsac_t import DSAC_T

        AlgoClass = DSAC_T
    else:
        AlgoClass = SAC

    if args.resume:
        print(f"Resuming from: {args.resume}")
        model = AlgoClass.load(args.resume, env=env, device=args.device)
        replay_path = args.resume.replace(".zip", "_replay_buffer.pkl")
        if os.path.exists(replay_path):
            model.load_replay_buffer(replay_path)
            print(f"Replay buffer loaded: {replay_path}")
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
