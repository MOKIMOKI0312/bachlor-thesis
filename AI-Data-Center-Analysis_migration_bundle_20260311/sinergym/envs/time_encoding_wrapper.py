"""Observation restructuring wrapper (tech route §6.1-A/D).

Does three things in one pass so we only rewrite obs once:

  [H2a] Drop raw time dims (month / day_of_month / hour at obs[0:3]) — tech
        route §6.1-A mandates sin/cos encoding only, no redundant raw time.

  [CRAH merge, H2b part 2] Collapse CRAH_temperature_1 / CRAH_temperature_2
        into a single signed CRAH_temp_diff = CRAH_2 - CRAH_1 — tech route
        §6.1-D mandates a single ΔT feature. Kept in wrapper (not in epJSON)
        so we don't have to edit Output:Variable definitions.

  [Time encoding, §6.1-A] Append [hour_sin, hour_cos, month_sin, month_cos].

Layout expected at input (base EplusEnv + TESIncrementalWrapper, post-H2b):
  [0] month
  [1] day_of_month
  [2] hour
  [3] outdoor_temperature
  [4] outdoor_wet_temperature
  [5] air_temperature
  [6] air_humidity
  [7] CT_temperature
  [8] CW_temperature
  [9] CRAH_temperature_1
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

Output layout (20 dims):
  [0..5]   outdoor_temperature, outdoor_wet_temperature, air_temperature,
           air_humidity, CT_temperature, CW_temperature
  [6]      CRAH_temp_diff (= CRAH_2 - CRAH_1)
  [7..15]  act_Fan, act_Chiller_T, act_Chiller_Pump, act_CT_Pump,
           TES_SOC, TES_avg_temp, Electricity:Facility,
           ITE-CPU:InteriorEquipment:Electricity, TES_valve_wrapper_position
  [16..19] hour_sin, hour_cos, month_sin, month_cos

NOTE: this wrapper must be applied directly after TESIncrementalWrapper
(so the base layout above holds). Downstream wrappers (PriceSignal /
PVSignal / Workload) append to the end and are unaffected.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np

# Raw-obs indices in the (base + TESIncremental) input layout described above.
TIME_IDX_MONTH = 0
TIME_IDX_HOUR = 2
CRAH1_IDX = 9
CRAH2_IDX = 10
# Indices to drop entirely (raw time + raw CRAH_1 + raw CRAH_2).
_DROP_IDX = (TIME_IDX_MONTH, 1, TIME_IDX_HOUR, CRAH1_IDX, CRAH2_IDX)


class TimeEncodingWrapper(gym.Wrapper):
    """Restructure obs: drop raw time, merge CRAH, append sin/cos time."""

    def __init__(self, env: gym.Env):
        super().__init__(env)

        base_low = self.env.observation_space.low
        base_high = self.env.observation_space.high
        # CRAH_temp_diff = CRAH_2 - CRAH_1. Assume both are roughly O(±30 °C)
        # → diff ∈ [-40, 40] °C is generous.
        keep_mask = np.ones_like(base_low, dtype=bool)
        for i in _DROP_IDX:
            keep_mask[i] = False
        kept_low = base_low[keep_mask]
        kept_high = base_high[keep_mask]
        # Append CRAH_temp_diff (will be inserted at position 6 in output, but
        # for Box bounds we just place it anywhere — the order in the Box
        # matches our _restructure() output).
        crah_low = np.array([-40.0], dtype=np.float32)
        crah_high = np.array([40.0], dtype=np.float32)
        # Sin/cos in [-1, 1]
        sc_low = np.array([-1.0, -1.0, -1.0, -1.0], dtype=np.float32)
        sc_high = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)

        # Physical-order layout: outdoor (2) + air/humid/CT/CW (4) + CRAH_diff (1)
        # + act (4) + TES_SOC/avg/elec/ITE/TES_valve (5) + sin/cos (4) = 20.
        # kept_low currently has order: [outdoor_T, outdoor_wet_T, air_T,
        # air_H, CT, CW, act_Fan, ..., TES_valve]. We need to slip CRAH_diff
        # between CW (kept_low[5]) and act_Fan (kept_low[6]).
        low = np.concatenate([kept_low[:6], crah_low, kept_low[6:], sc_low]).astype(np.float32)
        high = np.concatenate([kept_high[:6], crah_high, kept_high[6:], sc_high]).astype(np.float32)

        self.observation_space = gym.spaces.Box(
            low=low, high=high, dtype=np.float32,
        )

    @staticmethod
    def _encode(month: float, hour: float) -> np.ndarray:
        h_ang = 2.0 * np.pi * (hour / 24.0)
        m_ang = 2.0 * np.pi * ((month - 1.0) / 12.0)
        return np.array(
            [np.sin(h_ang), np.cos(h_ang), np.sin(m_ang), np.cos(m_ang)],
            dtype=np.float32,
        )

    def _restructure(self, obs: np.ndarray) -> np.ndarray:
        # Read raw time before dropping.
        month = float(obs[TIME_IDX_MONTH])
        hour = float(obs[TIME_IDX_HOUR])
        # Compute CRAH diff before dropping.
        crah_diff = float(obs[CRAH2_IDX]) - float(obs[CRAH1_IDX])

        # Keep all dims except the drop set.
        keep_mask = np.ones(obs.shape[0], dtype=bool)
        for i in _DROP_IDX:
            keep_mask[i] = False
        kept = obs[keep_mask]  # order: [outdoor_T, outdoor_wet_T, air_T, air_H, CT, CW, act_Fan, ...]

        # Insert CRAH_diff between CW (kept[5]) and act_Fan (kept[6]).
        body = np.concatenate([kept[:6], np.array([crah_diff], dtype=np.float32), kept[6:]])

        # Append sin/cos time encoding.
        sc = self._encode(month, hour)
        return np.concatenate([body, sc]).astype(np.float32)

    def reset(self, *, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> Tuple[np.ndarray, Dict]:
        obs, info = self.env.reset(seed=seed, options=options)
        return self._restructure(obs), info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        obs, reward, terminated, truncated, info = self.env.step(action)
        return self._restructure(obs), reward, terminated, truncated, info

    @property
    def observation_variables(self):
        base = list(self.env.get_wrapper_attr('observation_variables'))
        # Drop the 5 raw-obs names at indices in _DROP_IDX.
        kept = [name for i, name in enumerate(base) if i not in _DROP_IDX]
        # Insert CRAH_temp_diff between CW_temperature (kept[5]) and act_Fan (kept[6]).
        body = kept[:6] + ['CRAH_temp_diff'] + kept[6:]
        return body + ['hour_sin', 'hour_cos', 'month_sin', 'month_cos']
