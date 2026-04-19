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
from sinergym.envs.temp_trend_wrapper import TempTrendWrapper
from sinergym.envs.price_signal_wrapper import PriceSignalWrapper
from sinergym.envs.pv_signal_wrapper import PVSignalWrapper
from sinergym.envs.workload_wrapper import WorkloadWrapper


class MockEplusLikeEnv(gym.Env):
    """Minimal Eplus-like env mirroring the layout seen by TimeEncodingWrapper.

    Obs layout (20 dims, same order as real EplusEnv + TESIncrementalWrapper
    after H2b):
      [0]  month
      [1]  day_of_month
      [2]  hour
      [3]  outdoor_temperature
      [4]  outdoor_wet_temperature
      [5]  air_temperature
      [6]  air_humidity
      [7]  CT_temperature
      [8]  CW_temperature
      [9]  CRAH_temperature_1
      [10] CRAH_temperature_2
      [11] act_Fan
      [12] act_Chiller_T
      [13] act_Chiller_Pump
      [14] act_CT_Pump
      [15] TES_SOC
      [16] TES_avg_temp
      [17] Electricity:Facility
      [18] ITE-CPU:InteriorEquipment:Electricity
      [19] TES_valve_wrapper_position

    Action box mirrors Eplus-DC-Cooling-TES registration: low=[0,0,0,0,0,-1],
    high=[1,1,1,1,1,1] (see sinergym/__init__.py L126-127)."""

    OBS_NAMES = [
        'month', 'day_of_month', 'hour',
        'outdoor_temperature', 'outdoor_wet_temperature',
        'air_temperature', 'air_humidity',
        'CT_temperature', 'CW_temperature',
        'CRAH_temperature_1', 'CRAH_temperature_2',
        'act_Fan', 'act_Chiller_T', 'act_Chiller_Pump', 'act_CT_Pump',
        'TES_SOC', 'TES_avg_temp',
        'Electricity:Facility', 'ITE-CPU:InteriorEquipment:Electricity',
        'TES_valve_wrapper_position',
    ]

    def __init__(self):
        low = np.array(
            [1, 1, 0, -50, -50, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1],
            dtype=np.float32)
        high = np.array(
            [12, 31, 23, 50, 50, 40, 100, 50, 50, 50, 50, 1e6, 50, 1e6, 1e6,
             1, 40, 1e9, 1e9, 1],
            dtype=np.float32)
        self.observation_space = gym.spaces.Box(low=low, high=high, shape=(20,), dtype=np.float32)
        self.action_space = gym.spaces.Box(
            low=np.array([0, 0, 0, 0, 0, -1], dtype=np.float32),
            high=np.array([1, 1, 1, 1, 1, 1], dtype=np.float32),
            shape=(6,), dtype=np.float32,
        )
        self._month = 1
        self._day = 1
        self._hour = 0

    @property
    def observation_variables(self):
        return list(self.OBS_NAMES)

    @property
    def action_variables(self):
        return ['CRAH_Fan', 'CT_Pump', 'CRAH_T', 'Chiller_T', 'ITE', 'TES']

    def _obs(self):
        # Plug mildly realistic constants; CRAH_1/CRAH_2 differ by ~2 °C so
        # we can eyeball the merged diff in output.
        return np.array([
            self._month, self._day, self._hour,
            20.0, 18.0,           # outdoor_T, outdoor_wet_T
            22.0, 40.0,           # air_T, air_H
            25.0, 15.0,           # CT, CW
            18.5, 20.5,           # CRAH_1, CRAH_2 → diff = +2.0
            0.5, 0.5, 0.5, 0.5,   # 4 actuator vars
            0.5, 12.0,            # TES_SOC, TES_avg_temp
            1e6, 5e5,             # Electricity:Facility, ITE
            0.0,                  # TES_valve_wrapper_position
        ], dtype=np.float32)

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
    trace_csv = data_root / "AI Trace Data" / "Earth_hourly.csv"

    env = MockEplusLikeEnv()
    env = TimeEncodingWrapper(env)
    env = TempTrendWrapper(
        env,
        epw_path=ROOT / "Data/weather/USA_CA_San.Francisco.Intl.AP.724940_TMYx.2009-2023.epw",
        lookahead_hours=6,
    )
    env = PriceSignalWrapper(env, price_csv_path=price_csv, lookahead_hours=6)
    env = PVSignalWrapper(env, pv_csv_path=pv_csv, dc_peak_load_kw=6000.0, lookahead_hours=6)
    env = WorkloadWrapper(env, it_trace_csv=trace_csv, workload_idx=4, flexible_fraction=0.3)

    # Post-H2a/H2b/H2c/H2d dim math:
    #   base mock:     20
    #   TimeEncoding: -5 (drop month/day/hour/CRAH_1/CRAH_2) +1 (CRAH_diff) +4 (sin/cos) = 20
    #   TempTrend:     +6 → 26
    #   Price:         +3 → 29
    #   PV:            +3 → 32
    #   Workload:      +9 → 41
    expected_dim = 20 + 6 + 3 + 3 + 9  # 41
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

    # Verify CRAH_temp_diff at index 6 (body[6] = CRAH_2 - CRAH_1 = 20.5 - 18.5 = 2.0)
    assert abs(obs[6] - 2.0) < 1e-5, f"CRAH_temp_diff should be 2.0, got {obs[6]}"
    print(f"CRAH_temp_diff at obs[6] = {obs[6]:.3f} (expect 2.0) ✓")

    # Verify time encoding at obs[16..20] (hour 0, month 1: sin=0, cos=1)
    time_enc = obs[16:20]
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

    # Verify obs signal ranges. Layout after wrappers (41 dims):
    #   [0..15]  body (outdoor/air/CT/CW/CRAH_diff/4 act/TES SOC+avg/elec/ITE/TES_valve)
    #   [16..19] sin/cos time (hour_sin, hour_cos, month_sin, month_cos)
    #   [20..25] temp trend (slope, mean, std, percentile, ttp, ttv)
    #   [26..28] price (current, slope, mean)
    #   [29..31] pv    (current_ratio, slope, time_to_peak)
    #   [32..40] workload (9 dims)
    temp_slice = obs[20:26]
    price_slice = obs[26:29]
    pv_slice = obs[29:32]
    wl_slice = obs[32:41]
    # Temp trend bounds: slope ∈ [-1,1], mean/std/pct/ttp/ttv ∈ [0,1]
    assert -1 <= temp_slice[0] <= 1, f"temp slope out of range: {temp_slice[0]}"
    assert np.all(temp_slice[1:] >= -1e-6) and np.all(temp_slice[1:] <= 1 + 1e-6), (
        f"temp trend [1:] out of [0,1]: {temp_slice[1:]}"
    )
    assert 0 <= price_slice[0] <= 1 and -1 <= price_slice[1] <= 1 and 0 <= price_slice[2] <= 1
    assert 0 <= pv_slice[0] <= 1 and -1 <= pv_slice[1] <= 1 and 0 <= pv_slice[2] <= 1
    assert np.all(wl_slice >= 0) and np.all(wl_slice <= 1)
    print(f"Final obs slices: temp={temp_slice.round(3)} price={price_slice.round(3)} pv={pv_slice.round(3)} wl={wl_slice.round(3)} ✓")

    # Workload discretisation smoke: drive agent action[4] to each of 3 tiers
    print("Workload discretization test:")
    env.reset()
    # Defer mode
    for _ in range(3):
        a = np.zeros(6, dtype=np.float32); a[4] = 0.1
        _, _, _, _, info = env.step(a)
        assert info["workload_action"] == 0, f"expected 0, got {info['workload_action']}"
    queue_after_defer = info["workload_queue_len"]
    print(f"  after 3 defer steps, queue_len={queue_after_defer} (expect > 0)")
    assert queue_after_defer > 0, "defer should grow the queue"
    # Process mode
    for _ in range(3):
        a = np.zeros(6, dtype=np.float32); a[4] = 0.9
        _, _, _, _, info = env.step(a)
        assert info["workload_action"] == 2
    print(f"  after 3 process steps, queue_len={info['workload_queue_len']} util={info['workload_utilization']:.3f}")

    # observation_variables chain
    obs_vars = env.get_wrapper_attr("observation_variables")
    assert len(obs_vars) == expected_dim, f"got {len(obs_vars)} names, want {expected_dim}"
    print(f"observation_variables chain OK: {len(obs_vars)} names")

    print("=" * 60)
    print("SIGNAL + WORKLOAD WRAPPERS SMOKE PASSED")


if __name__ == "__main__":
    main()
