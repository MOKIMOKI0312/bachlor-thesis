"""Unit smoke test for TimeEncoding / PriceSignal / PVSignal wrappers.

Runs against a mock env (no EnergyPlus) to verify:
  - Observation dim increments: +4 / +3 / +3
  - Returned values are in their declared ranges
  - info dict contains raw USD/MWh and PV kW
  - After 24 steps the hour index wraps correctly for daily signals

Run: D:/Anaconda/python.exe tools/smoke_signal_wrappers.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gymnasium as gym
import numpy as np

from sinergym.envs.time_encoding_wrapper import TimeEncodingWrapper
from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
from sinergym.envs.pv_signal_wrapper import PVSignalWrapper


class MockEplusLikeEnv(gym.Env):
    """Minimal Eplus-like env: 5-dim obs [month, day, hour, outdoor_T, air_T],
    6-dim action box. Increments hour on each step."""

    def __init__(self):
        self.observation_space = gym.spaces.Box(
            low=np.array([1, 1, 0, -50, 10], dtype=np.float32),
            high=np.array([12, 31, 23, 50, 40], dtype=np.float32),
            shape=(5,), dtype=np.float32,
        )
        self.action_space = gym.spaces.Box(low=-1, high=1, shape=(6,), dtype=np.float32)
        self._month = 1
        self._day = 1
        self._hour = 0

    @property
    def observation_variables(self):
        return ['month', 'day_of_month', 'hour', 'outdoor_temperature', 'air_temperature']

    @property
    def action_variables(self):
        return ['CRAH_Fan', 'CT_Pump', 'CRAH_T', 'Chiller_T', 'ITE', 'TES']

    def _obs(self):
        return np.array([self._month, self._day, self._hour, 20.0, 22.0], dtype=np.float32)

    def reset(self, *, seed=None, options=None):
        self._month = 1
        self._day = 1
        self._hour = 0
        return self._obs(), {}

    def step(self, action):
        self._hour += 1
        if self._hour >= 24:
            self._hour = 0
            self._day += 1
            if self._day > 28:
                self._day = 1
                self._month = min(12, self._month + 1)
        return self._obs(), 0.0, False, False, {}


def main() -> None:
    data_root = ROOT / "Data"
    price_csv = data_root / "prices" / "CAISO_NP15_2023_hourly.csv"
    pv_csv = data_root / "pv" / "CAISO_PaloAlto_PV_6MWp_hourly.csv"

    env = MockEplusLikeEnv()
    env = TimeEncodingWrapper(env)
    env = PriceSignalWrapper(env, price_csv_path=price_csv, lookahead_hours=6)
    env = PVSignalWrapper(env, pv_csv_path=pv_csv, dc_peak_load_kw=6000.0, lookahead_hours=6)

    expected_dim = 5 + 4 + 3 + 3  # 15
    assert env.observation_space.shape == (expected_dim,), (
        f"Expected dim {expected_dim}, got {env.observation_space.shape}"
    )
    print(f"Wrapped obs_dim = {expected_dim} ✓")

    obs, info = env.reset()
    assert obs.shape == (expected_dim,)
    assert np.all(np.isfinite(obs))
    assert "current_price_usd_per_mwh" in info
    assert "current_pv_kw" in info
    print(f"reset obs shape OK; price@hour0={info['current_price_usd_per_mwh']:.2f}, pv@hour0={info['current_pv_kw']:.1f}")

    # Verify time encoding at hour 0: hour_sin=0, hour_cos=1
    time_enc = obs[5:9]
    assert abs(time_enc[0]) < 1e-5, f"hour_sin at hour 0 should be 0, got {time_enc[0]}"
    assert abs(time_enc[1] - 1.0) < 1e-5, f"hour_cos at hour 0 should be 1, got {time_enc[1]}"
    # Month Jan (=1): month_sin=sin(0)=0, month_cos=cos(0)=1
    assert abs(time_enc[2]) < 1e-5
    assert abs(time_enc[3] - 1.0) < 1e-5
    print(f"time encoding at hour 0 month 1: {time_enc.round(3)} ✓")

    # Run 24 steps and track PV signal — PV should be ~0 at night, peak at noon
    pv_ratios = []
    for i in range(24):
        obs, _, _, _, info = env.step(np.zeros(6, dtype=np.float32))
        assert obs.shape == (expected_dim,)
        assert np.all(np.isfinite(obs))
        pv_ratios.append(info["current_pv_kw"])
    pv_ratios = np.array(pv_ratios)
    print(f"24h PV kW: min={pv_ratios.min():.1f}, max={pv_ratios.max():.1f}, argmax={int(np.argmax(pv_ratios))}")
    assert pv_ratios[0:5].max() < 100, "Night PV should be near 0"
    assert 9 <= int(np.argmax(pv_ratios)) <= 15, (
        f"PV peak should be within 9-15h, got {int(np.argmax(pv_ratios))}"
    )
    print("PV daily shape sane ✓")

    # Verify last obs has signal dims in range
    current_price_norm = obs[9]
    price_slope = obs[10]
    price_mean = obs[11]
    pv_ratio_obs = obs[12]
    pv_slope = obs[13]
    ttp = obs[14]
    assert 0 <= current_price_norm <= 1
    assert -1 <= price_slope <= 1
    assert 0 <= price_mean <= 1
    assert 0 <= pv_ratio_obs <= 1
    assert -1 <= pv_slope <= 1
    assert 0 <= ttp <= 1
    print(f"Final obs signals: price=({current_price_norm:.3f},{price_slope:+.3f},{price_mean:.3f}) "
          f"pv=({pv_ratio_obs:.3f},{pv_slope:+.3f},ttp={ttp:.3f}) ✓")

    # observation_variables chain
    obs_vars = env.get_wrapper_attr("observation_variables")
    expected_vars = [
        'month', 'day_of_month', 'hour', 'outdoor_temperature', 'air_temperature',
        'hour_sin', 'hour_cos', 'month_sin', 'month_cos',
        'price_current_norm', 'price_future_slope', 'price_future_mean',
        'pv_current_ratio', 'pv_future_slope', 'time_to_pv_peak',
    ]
    assert obs_vars == expected_vars, f"obs_vars mismatch:\n got {obs_vars}\n want {expected_vars}"
    print(f"observation_variables chain OK: {len(obs_vars)} names")

    print("=" * 60)
    print("SIGNAL WRAPPERS SMOKE PASSED")


if __name__ == "__main__":
    main()
