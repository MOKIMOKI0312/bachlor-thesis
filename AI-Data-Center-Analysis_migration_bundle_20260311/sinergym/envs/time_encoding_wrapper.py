"""Sinusoidal time encoding wrapper (tech route §6.1-A).

Appends 4 dims to the observation: [hour_sin, hour_cos, month_sin, month_cos].

Reads month (obs[0]) and hour (obs[2]) from the underlying EplusEnv's
time_variables = ['month', 'day_of_month', 'hour']. If the base env's time
layout changes, update TIME_IDX_* constants.

Insert BEFORE NormalizeObservation in the wrapper chain so that raw month/hour
integers are available.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np

TIME_IDX_MONTH = 0   # obs[0] = month ∈ [1, 12]
TIME_IDX_HOUR = 2    # obs[2] = hour ∈ [0, 23]


class TimeEncodingWrapper(gym.Wrapper):
    """Append sin/cos encodings of hour-of-day and month-of-year.

    Args:
        env: base env (must expose time_variables with 'month' at index 0 and
             'hour' at index 2; default EplusEnv layout does).
    """

    def __init__(self, env: gym.Env):
        super().__init__(env)

        low = np.append(self.env.observation_space.low, [-1.0, -1.0, -1.0, -1.0])
        high = np.append(self.env.observation_space.high, [1.0, 1.0, 1.0, 1.0])
        self.observation_space = gym.spaces.Box(
            low=low.astype(np.float32),
            high=high.astype(np.float32),
            dtype=np.float32,
        )

    @staticmethod
    def _encode(month: float, hour: float) -> np.ndarray:
        # hour ∈ [0, 23] → 2π · hour / 24
        # month ∈ [1, 12] → 2π · (month - 1) / 12
        h_ang = 2.0 * np.pi * (hour / 24.0)
        m_ang = 2.0 * np.pi * ((month - 1.0) / 12.0)
        return np.array(
            [np.sin(h_ang), np.cos(h_ang), np.sin(m_ang), np.cos(m_ang)],
            dtype=np.float32,
        )

    def _append(self, obs: np.ndarray) -> np.ndarray:
        month = float(obs[TIME_IDX_MONTH])
        hour = float(obs[TIME_IDX_HOUR])
        return np.append(obs, self._encode(month, hour)).astype(np.float32)

    def reset(self, *, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> Tuple[np.ndarray, Dict]:
        obs, info = self.env.reset(seed=seed, options=options)
        return self._append(obs), info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        obs, reward, terminated, truncated, info = self.env.step(action)
        return self._append(obs), reward, terminated, truncated, info

    @property
    def observation_variables(self):
        base = self.env.get_wrapper_attr('observation_variables')
        return list(base) + ['hour_sin', 'hour_cos', 'month_sin', 'month_cos']
