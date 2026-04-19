"""PV signal wrapper (tech route §4.3).

Reads a precomputed hourly PV output CSV (e.g. PVGIS Palo Alto 6 MWp 2023)
and injects 3 dims into obs:
  - current_pv_ratio   : normalised PV output / DC peak load (clipped to [0, 1])
  - pv_future_slope    : linear-regression slope over next K hours
  - time_to_pv_peak    : normalised hours until next daily PV peak, ∈ [0, 1]

Also exposes `info['current_pv_kw']` each step so reward functions can read it
(RL-Green needs raw PV kW to decide whether the virtual green-price regime
applies).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np
import pandas as pd


class PVSignalWrapper(gym.Wrapper):

    def __init__(
        self,
        env: gym.Env,
        pv_csv_path: str | Path,
        pv_column: str = "power_kw",
        dc_peak_load_kw: float = 6000.0,
        lookahead_hours: int = 6,
    ):
        super().__init__(env)

        df = pd.read_csv(pv_csv_path)
        if pv_column not in df.columns:
            raise ValueError(
                f"Column '{pv_column}' not in {pv_csv_path}; have {list(df.columns)}"
            )
        pv_kw = df[pv_column].to_numpy(dtype=np.float32)
        if len(pv_kw) != 8760:
            raise ValueError(
                f"PV CSV must have 8760 rows, got {len(pv_kw)} from {pv_csv_path}"
            )
        self._pv_kw = pv_kw
        self._dc_peak = float(dc_peak_load_kw)
        self._pv_ratio = np.clip(pv_kw / self._dc_peak, 0.0, 1.0)
        self.lookahead = int(lookahead_hours)
        self._hour_idx = 0

        # Pre-compute "hours until next daily peak" for every hour of the year.
        # For each hour h, look at that day's 24-hour window and find argmax.
        self._hours_to_peak = np.zeros(8760, dtype=np.float32)
        for day in range(365):
            start = day * 24
            end = start + 24
            day_peak_h = int(np.argmax(pv_kw[start:end]))
            for hod in range(24):
                # Hours until that day's peak; if peak already passed, distance
                # to tomorrow's peak (same hod assumption — good enough).
                delta = day_peak_h - hod
                if delta < 0:
                    delta += 24
                self._hours_to_peak[start + hod] = delta / 23.0  # ∈ [0, 1]

        low = np.append(self.env.observation_space.low, [0.0, -1.0, 0.0])
        high = np.append(self.env.observation_space.high, [1.0, 1.0, 1.0])
        self.observation_space = gym.spaces.Box(
            low=low.astype(np.float32),
            high=high.astype(np.float32),
            dtype=np.float32,
        )

    def _future_window(self) -> np.ndarray:
        idx = (self._hour_idx + np.arange(self.lookahead)) % 8760
        return self._pv_ratio[idx]

    def _signals(self) -> Tuple[np.ndarray, float]:
        current = float(self._pv_ratio[self._hour_idx])
        future = self._future_window()
        t = np.arange(self.lookahead, dtype=np.float32)
        if future.std() < 1e-8:
            slope = 0.0
        else:
            slope_raw = float(np.polyfit(t, future, 1)[0])
            slope = float(np.clip(slope_raw * (self.lookahead - 1), -1.0, 1.0))
        ttp = float(self._hours_to_peak[self._hour_idx])
        raw_pv = float(self._pv_kw[self._hour_idx])
        return np.array([current, slope, ttp], dtype=np.float32), raw_pv

    def reset(self, *, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> Tuple[np.ndarray, Dict]:
        self._hour_idx = 0
        obs, info = self.env.reset(seed=seed, options=options)
        sig, raw = self._signals()
        info["current_pv_kw"] = raw
        return np.append(obs, sig).astype(np.float32), info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        obs, reward, terminated, truncated, info = self.env.step(action)
        self._hour_idx = (self._hour_idx + 1) % 8760
        sig, raw = self._signals()
        info["current_pv_kw"] = raw
        return np.append(obs, sig).astype(np.float32), reward, terminated, truncated, info

    @property
    def observation_variables(self):
        base = self.env.get_wrapper_attr('observation_variables')
        return list(base) + ['pv_current_ratio', 'pv_future_slope', 'time_to_pv_peak']

    @property
    def pv_series_raw(self) -> np.ndarray:
        return self._pv_kw

    @property
    def current_hour_idx(self) -> int:
        return self._hour_idx
