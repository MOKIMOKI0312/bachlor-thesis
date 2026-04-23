"""PBRS smoke test (analysis/pbrs_design_2026-04-23.md §4).

Verifies that `RL_Cost_Reward` correctly emits `shaping_term` and `phi_value`
into reward terms, and that the first-step F=0 invariant holds.

Builds the full M2 wrapper stack + RL_Cost_Reward (with PBRS enabled), runs
3 steps, and asserts:
  1. step 1: shaping_term == 0.0 (first_step guard)
  2. step 2+: shaping_term = γ·Φ(s') − Φ(s_prev)
  3. |shaping_term| < 1.0 (per design, κ=2.0 bounds |Φ|≤0.5 → |F|≤~1.0 absolute)
  4. phi_value is bounded in [-0.5, 0.5] (κ=2.0 × (SOC-0.5) × (0.5-signal))

Run:
  EPLUS_PATH=... PYTHONPATH="$PWD;$EPLUS_PATH" python tools/smoke_pbrs.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gymnasium as gym
import numpy as np
import pandas as pd

from sinergym.utils.common import get_ids
from sinergym.envs.tes_wrapper import TESIncrementalWrapper
from sinergym.envs.time_encoding_wrapper import TimeEncodingWrapper
from sinergym.envs.temp_trend_wrapper import TempTrendWrapper
from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
from sinergym.envs.pv_signal_wrapper import PVSignalWrapper
from sinergym.envs.workload_wrapper import WorkloadWrapper
from sinergym.utils.rewards import RL_Cost_Reward


def main() -> int:
    assert "Eplus-DC-Cooling-TES" in get_ids()

    stamp = datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
    env = gym.make(
        "Eplus-DC-Cooling-TES",
        env_name=f"{stamp}_smoke_pbrs",
        building_file=["DRL_DC_training.epJSON"],
        weather_files=["CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"],
        config_params={"runperiod": (1, 1, 2025, 31, 12, 2025), "timesteps_per_hour": 1},
    )
    env = TESIncrementalWrapper(env, valve_idx=5, delta_max=0.20)
    env = TimeEncodingWrapper(env)
    env = TempTrendWrapper(
        env,
        epw_path="Data/weather/CHN_JS_Nanjing.582380_TMYx.2009-2023.epw",
        lookahead_hours=6,
    )
    env = PriceSignalWrapper(env, price_csv_path="Data/prices/Jiangsu_TOU_2025_hourly.csv")
    env = PVSignalWrapper(env, pv_csv_path="Data/pv/CHN_Nanjing_PV_6MWp_hourly.csv")
    env = WorkloadWrapper(env, it_trace_csv="Data/AI Trace Data/Earth_hourly.csv", workload_idx=4)

    # --- RL_Cost_Reward WITH PBRS ----------------------------------------
    price = pd.read_csv("Data/prices/Jiangsu_TOU_2025_hourly.csv")["price_usd_per_mwh"].to_numpy()
    reward_fn = RL_Cost_Reward(
        temperature_variables=["air_temperature"],
        energy_variables=["Electricity:Facility"],
        ITE_variables=["ITE-CPU:InteriorEquipment:Electricity"],
        range_comfort_winter=(18.0, 25.0),
        range_comfort_summer=(18.0, 25.0),
        energy_weight=0.5,
        lambda_energy=1.0,
        lambda_temperature=1.0,
        soc_variable="TES_SOC",
        soc_low=0.15, soc_high=0.85,
        soc_warn_low=0.15, soc_warn_high=0.85,
        lambda_soc=2.0, lambda_soc_warn=1.0,
        price_series=price,
        alpha=2e-3, beta=1.0,
        kappa_shape=2.0,
        gamma_pbrs=0.99,
    )
    env.unwrapped.reward_fn = reward_fn
    assert isinstance(env.unwrapped.reward_fn, RL_Cost_Reward)

    # Verify PBRS state initialized correctly
    assert reward_fn._first_step is True, "first_step should start True before reset"
    assert reward_fn._prev_phi == 0.0

    # --- Reset ----------------------------------------------------------
    obs, info = env.reset()
    print(f"reset: obs.shape={obs.shape}, first_step={reward_fn._first_step}, prev_phi={reward_fn._prev_phi}")
    # EplusEnv.reset calls reward_fn.reset_episode() — should still be True
    assert reward_fn._first_step is True, "reset_episode should re-arm first_step"
    assert reward_fn._prev_phi == 0.0

    # --- Step loop ------------------------------------------------------
    rng = np.random.default_rng(42)
    results = []

    for i in range(3):
        a = rng.uniform(-1, 1, size=(6,)).astype(np.float32)
        obs, r, term, trunc, info = env.step(a)

        # EplusEnv.step does info.update(rw_terms), so shaping_term/phi_value
        # land in info.
        shaping = info.get('shaping_term', None)
        phi = info.get('phi_value', None)
        soc = info.get('soc_value', None)
        lmp = info.get('lmp_usd_per_mwh', None)

        # Internal signal_norm (what _phi sees for price)
        # Reconstruct to verify: signal_norm should be in [0, 1]
        sig_norm = (np.clip((lmp - reward_fn._price_mean_phi) / reward_fn._price_std_phi, -1.0, 2.0) + 1.0) / 3.0

        # Re-derive phi from SOC and sig_norm — should equal info phi_value
        phi_reconstructed = 2.0 * (float(soc) - 0.5) * (0.5 - float(sig_norm))

        print(f"step {i+1}: soc={soc:.4f}, lmp={lmp:.2f}, "
              f"sig_norm={sig_norm:.4f}, phi={phi:.6f} (reconstructed={phi_reconstructed:.6f}), "
              f"shaping={shaping:.6f}, reward={r:.4f}")

        results.append({
            'step': i + 1, 'soc': float(soc), 'lmp': float(lmp),
            'sig_norm': float(sig_norm), 'phi': float(phi),
            'phi_reconstructed': float(phi_reconstructed),
            'shaping': float(shaping), 'reward': float(r),
        })

        # Assertions
        assert shaping is not None, "shaping_term missing from info"
        assert phi is not None, "phi_value missing from info"
        # phi bounded [-0.5, 0.5] (κ=2.0, SOC in [0,1], sig in [0,1])
        assert -0.5 - 1e-6 <= phi <= 0.5 + 1e-6, f"phi={phi} outside [-0.5, 0.5]"
        # |F| bounded: max ≈ γ·0.5 − (−0.5) = 0.99·0.5 + 0.5 = 0.995 (< 1.0)
        assert abs(shaping) < 1.0, f"|shaping_term|={abs(shaping)} >= 1.0"

        # Verify reconstruction matches (confirms _phi implementation)
        assert abs(phi - phi_reconstructed) < 1e-4, (
            f"phi={phi} vs reconstructed={phi_reconstructed} diverged by "
            f"{abs(phi - phi_reconstructed):.2e}"
        )

    # Step 1: shaping_term == 0.0 (first_step guard)
    assert results[0]['shaping'] == 0.0, (
        f"step 1 shaping_term should be 0.0, got {results[0]['shaping']}"
    )

    # Step 2: shaping = γ·phi_2 − phi_1
    expected_shaping_2 = 0.99 * results[1]['phi'] - results[0]['phi']
    assert abs(results[1]['shaping'] - expected_shaping_2) < 1e-5, (
        f"step 2 shaping mismatch: got {results[1]['shaping']}, "
        f"expected γ·{results[1]['phi']} − {results[0]['phi']} = {expected_shaping_2}"
    )

    # Step 3: shaping = γ·phi_3 − phi_2
    expected_shaping_3 = 0.99 * results[2]['phi'] - results[1]['phi']
    assert abs(results[2]['shaping'] - expected_shaping_3) < 1e-5, (
        f"step 3 shaping mismatch: got {results[2]['shaping']}, "
        f"expected γ·{results[2]['phi']} − {results[1]['phi']} = {expected_shaping_3}"
    )

    env.close()

    print("=" * 60)
    print("PBRS SMOKE PASSED")
    print(f"  step1 shaping=0.0 (first_step) OK")
    print(f"  step2 shaping={results[1]['shaping']:.6f} = γ·Φ(s2) - Φ(s1) OK")
    print(f"  step3 shaping={results[2]['shaping']:.6f} = γ·Φ(s3) - Φ(s2) OK")
    print(f"  |Φ| ≤ 0.5 across all steps OK")
    print(f"  |F| < 1.0 across all steps OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
