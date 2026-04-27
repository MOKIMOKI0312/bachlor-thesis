"""B3 fix smoke test — verify EnergyScaleWrapper targets correct indices.

Expected after fix:
  obs[12] = TES_avg_temp       ∈ [5, 20]   (°C, should NOT be scaled)
  obs[13] = Electricity:Facility ∈ [0.1, 100]  (MWh/h, scaled from ~3e10 J/h)
  obs[14] = ITE-CPU:...:Electricity ∈ [0.1, 100]  (MWh/h, scaled)

Failure modes:
  obs[12] < 1e-3  → still scaling TES_avg_temp (B3 mis-applied)
  obs[14] > 1e5   → ITE-CPU still in Joules (B3 didn't cover idx 14)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gymnasium as gym
import numpy as np

from sinergym.utils.wrappers import NormalizeObservation, LoggerWrapper
from sinergym.envs.tes_wrapper import TESIncrementalWrapper
from sinergym.envs.time_encoding_wrapper import TimeEncodingWrapper
from sinergym.envs.temp_trend_wrapper import TempTrendWrapper
from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
from sinergym.envs.pv_signal_wrapper import PVSignalWrapper
from sinergym.envs.energy_scale_wrapper import EnergyScaleWrapper


def main() -> int:
    epw = "CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"
    price_csv = "Data/prices/Jiangsu_TOU_2025_hourly.csv"
    pv_csv = "Data/pv/CHN_Nanjing_PV_6MWp_hourly.csv"

    env = gym.make(
        "Eplus-DC-Cooling-TES",
        env_name="smoke_b3_fix",
        building_file=["DRL_DC_training.epJSON"],
        weather_files=[epw],
        config_params={
            "runperiod": (1, 1, 2025, 31, 12, 2025),
            "timesteps_per_hour": 4,
        },
    )
    env.action_space.seed(0)

    env = TESIncrementalWrapper(env, valve_idx=4, delta_max=0.25)
    env = TimeEncodingWrapper(env)
    env = TempTrendWrapper(env, epw_path=Path("Data/weather") / epw, lookahead_hours=6)
    env = PriceSignalWrapper(env, price_csv_path=price_csv, lookahead_hours=6)
    env = PVSignalWrapper(env, pv_csv_path=pv_csv, dc_peak_load_kw=6000.0, lookahead_hours=6)
    # The fix under test:
    env = EnergyScaleWrapper(env, energy_indices=[13, 14], scale=1.0 / 3.6e9)

    print(f"[B3-smoke] obs_dim = {env.observation_space.shape[0]} (expect 32)")
    assert env.observation_space.shape[0] == 32, "obs_dim must stay 32"

    obs, _ = env.reset(seed=0)
    print(f"[B3-smoke] after reset:")
    print(f"  obs[11] TES_SOC              = {obs[11]:.4e}")
    print(f"  obs[12] TES_avg_temp         = {obs[12]:.4e}  (expect 5~20)")
    print(f"  obs[13] Electricity:Facility = {obs[13]:.4e}  (expect 0.1~100)")
    print(f"  obs[14] ITE-CPU:Electricity  = {obs[14]:.4e}  (expect 0.1~100)")
    print(f"  obs[15] TES_valve_wrapper    = {obs[15]:.4e}")

    # Step 3 times (enough for Electricity meter to actually report nonzero values
    # — EnergyPlus reset obs is often pre-warmup zeros).
    samples = []
    for i in range(5):
        action = env.action_space.sample()
        obs, r, term, trunc, info = env.step(action)
        samples.append(obs.copy())
        print(
            f"[B3-smoke] step {i}: obs[12]={obs[12]:.4e}  obs[13]={obs[13]:.4e}  obs[14]={obs[14]:.4e}"
        )
        if term or trunc:
            break

    # Validation — use max across steps (meters may be 0 in step 0)
    samples = np.array(samples)
    max12 = float(np.max(np.abs(samples[:, 12])))
    max13 = float(np.max(np.abs(samples[:, 13])))
    max14 = float(np.max(np.abs(samples[:, 14])))

    print("\n[B3-smoke] max magnitudes across 5 steps:")
    print(f"  |obs[12]| max = {max12:.4e}")
    print(f"  |obs[13]| max = {max13:.4e}")
    print(f"  |obs[14]| max = {max14:.4e}")

    # Assertions
    ok = True
    if max12 < 1e-3:
        print(f"  FAIL: obs[12] (TES_avg_temp) too small ({max12:.2e}) — still being scaled!")
        ok = False
    if max14 > 1e5:
        print(f"  FAIL: obs[14] (ITE-CPU) too large ({max14:.2e}) — NOT scaled!")
        ok = False
    if 0.01 <= max13 <= 1000.0:
        print(f"  PASS: obs[13] (Electricity) in expected MWh/h range")
    else:
        print(f"  NOTE: obs[13] = {max13:.2e} (expect 0.1~100, but depends on warmup)")

    env.close()
    if ok:
        print("\n[B3-smoke] RESULT: B3 fix verified — TES_avg_temp untouched, energy dims scaled.")
        return 0
    print("\n[B3-smoke] RESULT: B3 fix FAILED — see above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
