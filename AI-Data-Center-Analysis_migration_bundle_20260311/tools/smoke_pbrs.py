"""PBRS v2 smoke test (analysis/pbrs_upgrade_DPBA_2026-04-23.md).

Verifies that `RL_Cost_Reward` with the DPBA Φ formula correctly emits
`shaping_term` and `phi_value` into reward terms, and that:
  1. step 1: shaping_term == 0.0 (first_step guard)
  2. step 2+: shaping_term = γ·Φ(s') − Φ(s_prev)
  3. |Φ| ≤ 0.40 (κ=0.8 × 0.5 × max_spread ≈ 0.32, 0.40 safety margin)
  4. |shaping_term| < 1.0 (episode-safe |F|)
  5. DIRECTIONAL: at 15:00 (distance-to-peak ≈ 4h, shoulder price),
     dΦ/dSOC > 0 — agent rewarded for charging high before the peak.

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
from sinergym.envs.tes_wrapper import FixedActionInsertWrapper, TESTargetValveWrapper
from sinergym.envs.time_encoding_wrapper import TimeEncodingWrapper
from sinergym.envs.temp_trend_wrapper import TempTrendWrapper
from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
from sinergym.envs.pv_signal_wrapper import PVSignalWrapper
from sinergym.utils.rewards import RL_Cost_Reward
from tools.m2_action_guard import M2_FIXED_FAN_VALUE


# Design §"量级验算" bounds
ASSERT_PHI_MAX = 0.40  # κ=0.8 · 0.5 · 0.8 = 0.32, +25% safety


def _directional_test(reward_fn: RL_Cost_Reward) -> None:
    """Directional test: at 15:00 distance-to-peak ≈ 4h (Jiangsu TOU shoulder
    at $83/MWh, peak at 19:00), Φ at SOC=0.7 should be GREATER than at SOC=0.3
    — i.e. dΦ/dSOC > 0 encourages charging.

    Uses a mock obs_dict (no env needed); exercises _phi directly.
    """
    # Construct a mock obs_dict approximating 15:00 on a typical day.
    # Pick July 15 (mid-summer peak) to align with tech route's peak season
    # assumption. In Jiangsu TOU, July is peak tier; 15:00 is shoulder
    # ($83/MWh), and 19:00 is peak ($200/MWh) → 4h to peak.
    mock_obs_low = {
        'month': 7, 'day_of_month': 15, 'hour': 15,
        reward_fn.soc_variable: 0.3,
    }
    mock_obs_high = dict(mock_obs_low)
    mock_obs_high[reward_fn.soc_variable] = 0.7

    phi_low = reward_fn._phi(mock_obs_low)
    phi_high = reward_fn._phi(mock_obs_high)
    dphi_dsoc = (phi_high - phi_low) / (0.7 - 0.3)

    print(f"[directional] 15:00 distance-to-peak test:")
    print(f"  Φ(SOC=0.3) = {phi_low:+.5f}")
    print(f"  Φ(SOC=0.7) = {phi_high:+.5f}")
    print(f"  ΔΦ/ΔSOC    = {dphi_dsoc:+.5f}  (must be > 0 → charge-ahead-of-peak)")

    assert phi_high > phi_low, (
        f"DIRECTIONAL FAILED: Φ(SOC=0.7) = {phi_high} should exceed "
        f"Φ(SOC=0.3) = {phi_low} at 15:00 (distance-to-peak ≈ 4h). "
        f"Check spread sign / p_peak_ref."
    )
    assert dphi_dsoc > 0.01, (
        f"DIRECTIONAL weak: ΔΦ/ΔSOC = {dphi_dsoc:.5f} too close to 0; "
        f"agent won't feel the shaping signal"
    )


def _magnitude_table(reward_fn: RL_Cost_Reward) -> None:
    """Dump Φ at 3 reference timestamps per design §量级验算 table for ground-truth
    comparison. Expected (±10%):
      02:00 trough  : SOC=0.3 → -0.002   SOC=0.7 → +0.002
      15:00 shoulder: SOC=0.3 → -0.041   SOC=0.7 → +0.041
      17:00 near-peak: SOC=0.3 → -0.068   SOC=0.7 → +0.068
    """
    cases = [
        ("02:00 trough  (distance 17h)", 7, 15, 2),
        ("15:00 shoulder (distance 4h)", 7, 15, 15),
        ("17:00 near-peak (distance 2h)", 7, 15, 17),
    ]
    print("[magnitude] Ground-truth comparison vs design §量级验算:")
    for label, m, d, h in cases:
        phi_lo = reward_fn._phi({'month': m, 'day_of_month': d, 'hour': h,
                                  reward_fn.soc_variable: 0.3})
        phi_hi = reward_fn._phi({'month': m, 'day_of_month': d, 'hour': h,
                                  reward_fn.soc_variable: 0.7})
        p_norm = reward_fn._signal_norm(
            {'month': m, 'day_of_month': d, 'hour': h})
        h_hrs = reward_fn._hours_to_next_peak(
            {'month': m, 'day_of_month': d, 'hour': h})
        print(f"  {label}")
        print(f"    price_norm={p_norm:.3f}  h={h_hrs:.1f}h  "
              f"Φ(SOC=0.3)={phi_lo:+.5f}  Φ(SOC=0.7)={phi_hi:+.5f}")


def main() -> int:
    assert "Eplus-DC-Cooling-TES" in get_ids()

    stamp = datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
    env = gym.make(
        "Eplus-DC-Cooling-TES",
        env_name=f"{stamp}_smoke_pbrs",
        building_file=["DRL_DC_training.epJSON"],
        weather_files=["CHN_JS_Nanjing.582380_TMYx.2009-2023.epw"],
        config_params={"runperiod": (1, 1, 2025, 31, 12, 2025), "timesteps_per_hour": 4},
    )
    env = TESTargetValveWrapper(env, valve_idx=4, rate_limit=0.25)
    env = FixedActionInsertWrapper(
        env,
        fixed_actions={0: M2_FIXED_FAN_VALUE},
        fixed_action_names={0: "CRAH_Fan_DRL"},
    )
    env = TimeEncodingWrapper(env)
    env = TempTrendWrapper(
        env,
        epw_path="Data/weather/CHN_JS_Nanjing.582380_TMYx.2009-2023.epw",
        lookahead_hours=6,
    )
    env = PriceSignalWrapper(env, price_csv_path="Data/prices/Jiangsu_TOU_2025_hourly.csv")
    env = PVSignalWrapper(env, pv_csv_path="Data/pv/CHN_Nanjing_PV_6MWp_hourly.csv")

    # --- RL_Cost_Reward WITH PBRS v2 (DPBA) ------------------------------
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
        kappa_shape=0.8,      # v2 default
        gamma_pbrs=0.99,
        tau_decay=4.0,        # DPBA exp-decay hours
        p_peak_ref=0.80,      # Jiangsu TOU peak price_norm reference
    )
    env.unwrapped.reward_fn = reward_fn
    assert isinstance(env.unwrapped.reward_fn, RL_Cost_Reward)

    # Verify PBRS state initialized correctly
    assert reward_fn._first_step is True, "first_step should start True before reset"
    assert reward_fn._prev_phi == 0.0

    # --- Pre-env directional + magnitude tests (use mock obs_dict) -------
    _directional_test(reward_fn)
    _magnitude_table(reward_fn)

    # --- Reset ----------------------------------------------------------
    obs, info = env.reset()
    print(f"reset: obs.shape={obs.shape}, first_step={reward_fn._first_step}, prev_phi={reward_fn._prev_phi}")
    assert reward_fn._first_step is True, "reset_episode should re-arm first_step"
    assert reward_fn._prev_phi == 0.0

    # --- Step loop ------------------------------------------------------
    env.action_space.seed(42)
    results = []

    for i in range(3):
        a = env.action_space.sample().astype(np.float32)
        obs, r, term, trunc, info = env.step(a)

        shaping = info.get('shaping_term', None)
        phi = info.get('phi_value', None)
        soc = info.get('soc_value', None)
        lmp = info.get('lmp_usd_per_mwh', None)

        print(f"step {i+1}: soc={soc:.4f}, lmp={lmp:.2f}, "
              f"phi={phi:+.6f}, shaping={shaping:+.6f}, reward={r:.4f}")

        results.append({
            'step': i + 1, 'soc': float(soc), 'lmp': float(lmp),
            'phi': float(phi), 'shaping': float(shaping), 'reward': float(r),
        })

        # Assertions
        assert shaping is not None, "shaping_term missing from info"
        assert phi is not None, "phi_value missing from info"
        # |Φ| ≤ 0.40 under DPBA with κ=0.8
        assert -ASSERT_PHI_MAX - 1e-6 <= phi <= ASSERT_PHI_MAX + 1e-6, (
            f"phi={phi} outside [-{ASSERT_PHI_MAX}, {ASSERT_PHI_MAX}]"
        )
        # |F| < 1.0 bound (κ=0.8 × γ=0.99 × ΔΦ)
        assert abs(shaping) < 1.0, f"|shaping_term|={abs(shaping)} >= 1.0"

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
    print("PBRS v2 (DPBA) SMOKE PASSED")
    print(f"  directional: Φ(SOC=0.7) > Φ(SOC=0.3) at 15:00 OK")
    print(f"  step1 shaping=0.0 (first_step) OK")
    print(f"  step2 shaping={results[1]['shaping']:+.6f} = γ·Φ(s2) - Φ(s1) OK")
    print(f"  step3 shaping={results[2]['shaping']:+.6f} = γ·Φ(s3) - Φ(s2) OK")
    print(f"  |Φ| ≤ {ASSERT_PHI_MAX} across all steps OK")
    print(f"  |F| < 1.0 across all steps OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
