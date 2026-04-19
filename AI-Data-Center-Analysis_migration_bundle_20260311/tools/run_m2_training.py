"""M2 training launcher — 41-dim obs / 6-dim action, CAISO SiliconValley site.

Wrapper chain (inside to outside):
  EplusEnv (22 raw dims, 6 absolute actions)  — built from Eplus-DC-Cooling-TES
  → TESIncrementalWrapper  (+1 dim → 23)     — action[5] = Δvalve
  → TimeEncodingWrapper    (+4 dim → 27)
  → PriceSignalWrapper     (+3 dim → 30)
  → PVSignalWrapper        (+3 dim → 33)
  → WorkloadWrapper        (+9 dim → 42)     — action[4] = discretised workload
  → NormalizeObservation
  → LoggerWrapper

Wait 42? The base env already contributes 22 before TES wrapper.
Actually base env has 21 raw obs, TES wrapper adds 1 → 22. Then +4+3+3+9 = 41.
(See tech route §6.1.)

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
from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
from sinergym.envs.pv_signal_wrapper import PVSignalWrapper
from sinergym.envs.workload_wrapper import WorkloadWrapper

DEFAULT_EPW = "USA_CA_San.Francisco.Intl.AP.724940_TMYx.2009-2023.epw"
DEFAULT_PRICE_CSV = "Data/prices/CAISO_NP15_2023_hourly.csv"
DEFAULT_PV_CSV = "Data/pv/CAISO_PaloAlto_PV_6MWp_hourly.csv"
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
        lambda_temperature=3.0,
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

    # Replace reward_fn on the innermost EplusEnv
    inner = env
    while hasattr(inner, "env") and not hasattr(inner, "reward_fn"):
        inner = inner.env
    if not hasattr(inner, "reward_fn"):
        raise RuntimeError("Could not locate EplusEnv with reward_fn to patch")
    inner.reward_fn = cls(**kwargs)
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
    parser.add_argument("--alpha", type=float, default=1e-3, help="Cost reward coefficient (1e-3 → ~-0.4 per hour at 60 USD/MWh & 6 MW, comparable to base reward ~-5; pilot α/β in M2-C3)")
    parser.add_argument("--beta", type=float, default=1.0, help="Comfort penalty coefficient")
    parser.add_argument("--c-pv", type=float, default=0.0, help="Virtual green-price USD/MWh (RL-Green only)")
    parser.add_argument("--pv-threshold-kw", type=float, default=100.0, help="PV kW above which green price applies")
    args = parser.parse_args()

    if "Eplus-DC-Cooling-TES" not in get_ids():
        raise RuntimeError("Eplus-DC-Cooling-TES is not registered")

    set_global_seed(args.seed)

    env = build_env(args)
    env = attach_reward(env, args)

    # Verify shapes before moving on
    expected_obs_dim = 22 + 4 + 3 + 3 + 9  # 41
    assert env.observation_space.shape == (expected_obs_dim,), (
        f"Expected M2 obs_dim={expected_obs_dim}, got {env.observation_space.shape}"
    )
    assert env.action_space.shape == (6,), (
        f"Expected action_dim=6, got {env.action_space.shape}"
    )
    print(f"Env wrapper stack OK: obs_dim={expected_obs_dim}, action_dim=6")

    obs_vars = env.get_wrapper_attr("observation_variables")
    act_vars = env.get_wrapper_attr("action_variables")
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

    policy_kwargs = dict(net_arch=[512])
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
            learning_rate=5e-5,
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
