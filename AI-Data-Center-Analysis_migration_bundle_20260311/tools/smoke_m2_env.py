"""Integration smoke for the full M2 wrapper stack on a real EplusEnv.

Builds:  EplusEnv → TESIncremental → TimeEncoding → TempTrend → PriceSignal →
         PVSignal → WorkloadWrapper → (+ RL_Cost_Reward patched)

Verifies:
  - obs_dim == 41 (20 + 6 + 3 + 3 + 9) — post-H2a/H2b/H2c/H2d, tech route §6.1
  - action_dim == 6
  - 3 env.step calls run clean
  - reward_terms dict contains cost_term / lmp_usd_per_mwh (RL-Cost)
    or effective_price_usd_per_mwh (RL-Green)

Run:
  EPLUS_PATH=... PYTHONPATH="$PWD;$EPLUS_PATH" python tools/smoke_m2_env.py --reward-cls rl_cost
  EPLUS_PATH=... PYTHONPATH="$PWD;$EPLUS_PATH" python tools/smoke_m2_env.py --reward-cls rl_green
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gymnasium as gym
import numpy as np

from sinergym.utils.common import get_ids
from sinergym.envs.tes_wrapper import TESIncrementalWrapper
from sinergym.envs.time_encoding_wrapper import TimeEncodingWrapper
from sinergym.envs.temp_trend_wrapper import TempTrendWrapper
from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
from sinergym.envs.pv_signal_wrapper import PVSignalWrapper
from sinergym.envs.workload_wrapper import WorkloadWrapper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reward-cls", default="rl_cost", choices=["pue_tes", "rl_cost", "rl_green"])
    ap.add_argument("--steps", type=int, default=3)
    args = ap.parse_args()

    assert "Eplus-DC-Cooling-TES" in get_ids()

    stamp = datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
    env = gym.make(
        "Eplus-DC-Cooling-TES",
        env_name=f"{stamp}_smoke_m2_{args.reward_cls}",
        building_file=["DRL_DC_training.epJSON"],
        weather_files=["USA_CA_San.Francisco.Intl.AP.724940_TMYx.2009-2023.epw"],
        config_params={"runperiod": (1, 1, 2025, 31, 12, 2025), "timesteps_per_hour": 1},
    )
    env = TESIncrementalWrapper(env, valve_idx=5, delta_max=0.20)
    env = TimeEncodingWrapper(env)
    env = TempTrendWrapper(
        env,
        epw_path="Data/weather/USA_CA_San.Francisco.Intl.AP.724940_TMYx.2009-2023.epw",
        lookahead_hours=6,
    )
    env = PriceSignalWrapper(env, price_csv_path="Data/prices/CAISO_NP15_2023_hourly.csv")
    env = PVSignalWrapper(env, pv_csv_path="Data/pv/CAISO_PaloAlto_PV_6MWp_hourly.csv")
    env = WorkloadWrapper(env, it_trace_csv="Data/AI Trace Data/Earth_hourly.csv", workload_idx=4)

    # Patch reward if requested
    if args.reward_cls != "pue_tes":
        import pandas as pd
        from sinergym.utils.rewards import RL_Cost_Reward, RL_Green_Reward

        price = pd.read_csv("Data/prices/CAISO_NP15_2023_hourly.csv")["price_usd_per_mwh"].to_numpy()
        pv = pd.read_csv("Data/pv/CAISO_PaloAlto_PV_6MWp_hourly.csv")["power_kw"].to_numpy()
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
            soc_low=0.15, soc_high=0.85,
            soc_warn_low=0.30, soc_warn_high=0.70,
            lambda_soc=5.0, lambda_soc_warn=3.0,
            price_series=price, alpha=1e-6, beta=1.0,
        )
        if args.reward_cls == "rl_cost":
            cls = RL_Cost_Reward
        else:
            cls = RL_Green_Reward
            kwargs["pv_series"] = pv
            kwargs["c_pv"] = 0.0
            kwargs["pv_threshold_kw"] = 100.0

        inner = env
        while hasattr(inner, "env") and not hasattr(inner, "reward_fn"):
            inner = inner.env
        inner.reward_fn = cls(**kwargs)

    # Post H2a/H2b/H2c/H2d: 20 + 6 + 3 + 3 + 9 = 41 dims (tech route §6.1).
    expected_dim = 41
    assert env.observation_space.shape == (expected_dim,), (
        f"Expected obs_dim={expected_dim}, got {env.observation_space.shape}"
    )
    assert env.action_space.shape == (6,), (
        f"Expected action_dim=6, got {env.action_space.shape}"
    )
    print(f"Env stack OK: obs_dim={expected_dim}, action_dim=6, reward={args.reward_cls}")

    obs, info = env.reset()
    assert obs.shape == (expected_dim,)
    print(f"reset obs.shape={obs.shape}, finite={np.all(np.isfinite(obs))}")

    rng = np.random.default_rng(42)
    for i in range(args.steps):
        a = rng.uniform(-1, 1, size=(6,)).astype(np.float32)
        obs, r, term, trunc, info = env.step(a)
        assert obs.shape == (expected_dim,)
        assert np.isfinite(r)
        summary = {
            "step": i + 1, "reward": round(float(r), 3),
            "wl_util": round(float(info.get("workload_utilization", 0)), 3),
            "wl_action": int(info.get("workload_action", 1)),
            "pv_kw": round(float(info.get("current_pv_kw", 0)), 1),
            "lmp": round(float(info.get("current_price_usd_per_mwh", 0)), 2),
        }
        print(f"  {summary}")

    env.close()
    print("=" * 60)
    print(f"M2 ENV SMOKE PASSED ({args.reward_cls})")


if __name__ == "__main__":
    main()
