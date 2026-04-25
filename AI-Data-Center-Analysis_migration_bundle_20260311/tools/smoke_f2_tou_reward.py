"""F2a TOU Arbitrage Bonus smoke test (2026-04-25).

Verifies RL_Cost_Reward F2a hard shaping via two phases:

Phase 1 — Direct reward_fn manual cases (no env required):
  Construct a fresh RL_Cost_Reward, manually seed `_prev_soc`, then call
  reward_fn(obs_dict) at synthesised (price, ΔSOC) combinations.
  Expected sign + approximate magnitude:
    1. trough ($29) + ΔSOC=+0.10 (charging) → tou_bonus > 0 (~+0.5)
    2. peak  ($200) + ΔSOC=-0.10 (discharging) → tou_bonus > 0 (~+0.5)
    3. peak  ($200) + ΔSOC=+0.10 (charging at peak) → tou_bonus < 0 (~-0.5)
    4. trough ($29) + ΔSOC=-0.10 (discharging at trough) → tou_bonus < 0 (~-0.5)

Phase 2 — 3 real env steps:
  Build the full 41-dim wrapper stack, attach RL_Cost_Reward, run 3 steps.
  Verify:
    * step1: tou_bonus == 0 (no _prev_soc on first call after reset)
    * info dict contains 'tou_bonus', 'tou_bonus_raw', 'delta_soc'
    * No crash, all reward terms finite

Phase 3 — reset hook contract:
  After env.reset(), `_prev_soc` should be None — proves
  reset_episode() correctly clears state, so next first-step yields 0.

Run:
  EPLUS_PATH=... PYTHONPATH="$PWD;$EPLUS_PATH" python tools/smoke_f2_tou_reward.py
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
from sinergym.envs.energy_scale_wrapper import EnergyScaleWrapper
from sinergym.utils.rewards import RL_Cost_Reward


def _make_reward_fn(price_series: np.ndarray) -> RL_Cost_Reward:
    """Build a fresh RL_Cost_Reward with F2a defaults."""
    return RL_Cost_Reward(
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
        price_series=price_series,
        alpha=5e-3, beta=0.7,             # F2b defaults
        kappa_shape=0.8, gamma_pbrs=0.99,
        tau_decay=4.0, p_peak_ref=0.80,
        kappa_tou=5.0, tou_bonus_clip=1.0,  # F2a defaults
    )


def _phase1_manual_cases(price: np.ndarray) -> int:
    """Phase 1 — synthesise (price, ΔSOC) combos and verify tou_bonus sign."""
    print("=" * 60)
    print("Phase 1: Manual (price, ΔSOC) cases")
    print("=" * 60)

    # --- Find a trough hour ($29) and a peak hour ($200) in Jiangsu TOU ----
    trough_idx = int(np.argmin(price))   # first hour with min price
    peak_idx = int(np.argmax(price))     # first hour with max price

    # Convert hour-of-year → (month, day_of_month, hour)
    DAYS_BEFORE = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)

    def idx_to_mdh(idx):
        d = idx // 24
        h = idx % 24
        m = 1
        for mi in range(12):
            if d < DAYS_BEFORE[mi] + (31 if mi == 0 else (28 if mi == 1 else 30)):
                m = mi + 1
                break
        else:
            m = 12
        # simpler: scan
        for mi in range(11, -1, -1):
            if d >= DAYS_BEFORE[mi]:
                m = mi + 1
                break
        d_local = d - DAYS_BEFORE[m - 1] + 1
        return m, d_local, h

    m_t, d_t, h_t = idx_to_mdh(trough_idx)
    m_p, d_p, h_p = idx_to_mdh(peak_idx)
    print(f"trough hour: idx={trough_idx} → month={m_t} day={d_t} hour={h_t} price=${price[trough_idx]:.0f}")
    print(f"peak   hour: idx={peak_idx} → month={m_p} day={d_p} hour={h_p} price=${price[peak_idx]:.0f}")
    assert price[trough_idx] == 29.0, f"expected trough=29, got {price[trough_idx]}"
    assert price[peak_idx] == 200.0, f"expected peak=200, got {price[peak_idx]}"

    # Mock obs_dict skeleton (only fields the reward reads).
    # Note: PUE_Reward super().__call__ also reads air_temperature / energy /
    # ITE_CPU keys, but they default to 0 if absent (numerical fields).
    def _build_obs(month, day, hour, soc):
        return {
            'month': month, 'day_of_month': day, 'hour': hour,
            'TES_SOC': soc,
            'air_temperature': 22.0,         # within comfort, no penalty
            'Electricity:Facility': 0.0,     # 0 J this step
            'ITE-CPU:InteriorEquipment:Electricity': 0.0,
        }

    cases = [
        ("1) trough + ΔSOC=+0.10 (charge at trough)", m_t, d_t, h_t, 0.50, 0.60, +1, 0.5),
        ("2) peak   + ΔSOC=-0.10 (discharge at peak)", m_p, d_p, h_p, 0.60, 0.50, +1, 0.5),
        ("3) peak   + ΔSOC=+0.10 (charge at peak  )", m_p, d_p, h_p, 0.50, 0.60, -1, 0.5),
        ("4) trough + ΔSOC=-0.10 (discharge at trough)", m_t, d_t, h_t, 0.60, 0.50, -1, 0.5),
    ]

    n_pass = 0
    for label, m, d, h, soc_prev, soc_curr, expected_sign, expected_mag in cases:
        rf = _make_reward_fn(price)
        # Seed _prev_soc; do NOT call reset_episode (which would clear it).
        rf._prev_soc = soc_prev
        # Set _first_step=False so PBRS shaping is computed (but we only check
        # tou_bonus). Both _prev_soc and _prev_phi are seeded to bypass step-1
        # guard.
        rf._first_step = False
        rf._prev_phi = 0.0

        obs = _build_obs(m, d, h, soc_curr)
        reward, terms = rf(obs)
        tou_bonus = terms['tou_bonus']
        tou_bonus_raw = terms['tou_bonus_raw']
        delta_soc = terms['delta_soc']
        lmp = terms['lmp_usd_per_mwh']

        # Compute expected manually for cross-check
        price_norm_expected = (lmp - 29.0) / (200.0 - 29.0)
        bonus_manual = 5.0 * (soc_curr - soc_prev) * (0.5 - price_norm_expected) * 2.0

        sign_ok = (np.sign(tou_bonus) == expected_sign) if abs(tou_bonus) > 1e-9 else False
        mag_ok = abs(abs(tou_bonus) - expected_mag) < 0.05  # ±0.05 tolerance

        status = "PASS" if (sign_ok and mag_ok) else "FAIL"
        if status == "PASS":
            n_pass += 1
        print(f"  {label}")
        print(f"    lmp=${lmp:.0f} delta_soc={delta_soc:+.3f} "
              f"tou_bonus={tou_bonus:+.4f} (raw={tou_bonus_raw:+.4f}, manual={bonus_manual:+.4f})")
        print(f"    expected sign={expected_sign:+d} mag≈{expected_mag:.2f} → {status}")
        assert sign_ok, f"{label}: tou_bonus sign WRONG"
        assert mag_ok, (
            f"{label}: tou_bonus magnitude {abs(tou_bonus):.4f} "
            f"differs from {expected_mag:.2f} by more than 0.05"
        )

    print(f"\nPhase 1 result: {n_pass}/4 cases PASSED")
    assert n_pass == 4
    return 0


def _phase2_real_env() -> int:
    """Phase 2 — full 41-dim env, run 3 steps, verify info dict."""
    print()
    print("=" * 60)
    print("Phase 2: Real env (3 steps)")
    print("=" * 60)

    assert "Eplus-DC-Cooling-TES" in get_ids()

    stamp = datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
    env = gym.make(
        "Eplus-DC-Cooling-TES",
        env_name=f"{stamp}_smoke_f2_tou",
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
    env = EnergyScaleWrapper(env, energy_indices=[13, 14], scale=1.0 / 3.6e9)

    price = pd.read_csv("Data/prices/Jiangsu_TOU_2025_hourly.csv")["price_usd_per_mwh"].to_numpy()
    reward_fn = _make_reward_fn(price)
    env.unwrapped.reward_fn = reward_fn
    assert isinstance(env.unwrapped.reward_fn, RL_Cost_Reward)

    # Pre-reset state inspection
    print(f"pre-reset:  _prev_soc={reward_fn._prev_soc}  _first_step={reward_fn._first_step}")

    obs, info = env.reset()
    print(f"reset done. obs.shape={obs.shape}")
    # F1 reset hook should have called reset_episode → _prev_soc=None
    assert reward_fn._prev_soc is None, (
        f"After reset, _prev_soc should be None (cleared by reset_episode), "
        f"got {reward_fn._prev_soc}"
    )
    assert reward_fn._first_step is True, "first_step should be True after reset"
    print("  _prev_soc=None  _first_step=True (reset hook OK)")

    rng = np.random.default_rng(42)
    for i in range(3):
        a = rng.uniform(-1, 1, size=(6,)).astype(np.float32)
        obs, r, term, trunc, info = env.step(a)

        tou_bonus = info.get('tou_bonus', None)
        tou_bonus_raw = info.get('tou_bonus_raw', None)
        delta_soc = info.get('delta_soc', None)
        lmp = info.get('lmp_usd_per_mwh', None)
        soc = info.get('soc_value', None)

        print(f"step {i+1}: soc={soc:.4f}  lmp=${lmp:.0f}  "
              f"delta_soc={delta_soc:+.4f}  tou_bonus={tou_bonus:+.4f}  "
              f"tou_bonus_raw={tou_bonus_raw:+.4f}  reward={r:+.4f}")

        # Hard checks
        assert tou_bonus is not None, "tou_bonus missing from info"
        assert tou_bonus_raw is not None, "tou_bonus_raw missing from info"
        assert delta_soc is not None, "delta_soc missing from info"
        assert np.isfinite(r), f"reward not finite: {r}"
        assert abs(tou_bonus) <= 1.0 + 1e-9, f"tou_bonus violates ±1.0 clip: {tou_bonus}"

        # Step 1: tou_bonus must be 0 (no _prev_soc before first call after reset)
        if i == 0:
            assert tou_bonus == 0.0, (
                f"Step 1 tou_bonus should be 0.0 (no _prev_soc), got {tou_bonus}"
            )
            print("  step1 tou_bonus=0.0 (first-step guard OK)")

    env.close()
    print("\nPhase 2 result: 3/3 steps OK, info contains tou_bonus / delta_soc")
    return 0


def main() -> int:
    price = pd.read_csv("Data/prices/Jiangsu_TOU_2025_hourly.csv")["price_usd_per_mwh"].to_numpy()
    _phase1_manual_cases(price)
    _phase2_real_env()
    print()
    print("=" * 60)
    print("F2a TOU REWARD SMOKE PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
