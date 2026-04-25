"""Price signal wrapper (tech route §5.2) — TOU-aware 3-dim signal.

Reads a precomputed hourly electricity price CSV (e.g. Jiangsu 2025 TOU or
CAISO NP15 LMP) and injects 3 ORTHOGONAL dims into obs:

  - current_price_norm      : z-score of current LMP, clipped to [-1, 2]
  - price_delta_next_1h     : (p[t+1] - p[t]) / std, clipped to [-2, 2]
  - hours_to_next_peak_norm : hours until next peak-tier period / max_gap, ∈ [0, 1]

M2-E3b-v4 rewrite (2026-04-23, Issue P1):
  The previous design used ``tanh((p - median) / (2σ))`` for all 3 dims
  (current, slope over K hours, mean over K hours). That is a reasonable
  encoding for CAISO NP15-style *continuous* LMPs with heavy tails, but it
  is ill-suited to Jiangsu TOU 2025 which is a piecewise-constant 8-level
  schedule (29 / 83 / 150 / 158 / 165 / 180 / 190 / 200 USD/MWh):
    1) `slope` over K=6 h: mostly 0 in piecewise-constant regions, so tanh
       maps most steps to ~0 (no info); only the tier-switch hour is
       informative, but the K-window averaging smears that single spike.
    2) `price_mean` over K=6 h: highly correlated with `current_price`
       under TOU (slow-varying step function), ~redundant dim.
    3) `current_price` tanh: wastes non-linear region on 8 discrete values.

  New design:
    - dim 1 (current_price_norm): z-score with upper clip at +2σ, lower
      at -1σ — preserves monotonic ordering across all 8 TOU levels.
    - dim 2 (price_delta_next_1h): signed 1-step forward delta / σ — a
      SHARP, sparse signal that fires exactly at tier-switch hours (e.g.
      08→09 shoulder→peak, 18→19 peak→super-peak).
    - dim 3 (hours_to_next_peak_norm): PLANNING horizon — tells the agent
      how long it has to charge TES / shift IT before the next peak tier.

The wrapper maintains its own step counter (hour_of_year ∈ [0, 8759]) that
loops each episode. It does NOT rely on the base env's time_variables, so
ordering vs TimeEncodingWrapper is flexible.

Also exposes `info['current_price_usd_per_mwh']` each step so reward
functions can read it (RL-Cost / RL-Green need the raw USD/MWh, not the
normalised value).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np
import pandas as pd


class PriceSignalWrapper(gym.Wrapper):

    def __init__(
        self,
        env: gym.Env,
        price_csv_path: str | Path,
        price_column: str = "price_usd_per_mwh",
        lookahead_hours: int = 6,
        peak_percentile: float = 75.0,
    ):
        super().__init__(env)

        df = pd.read_csv(price_csv_path)
        if price_column not in df.columns:
            raise ValueError(
                f"Column '{price_column}' not in {price_csv_path}; "
                f"have {list(df.columns)}"
            )
        prices = df[price_column].to_numpy(dtype=np.float32)
        if len(prices) != 8760:
            raise ValueError(
                f"Price CSV must have 8760 rows, got {len(prices)} from {price_csv_path}"
            )
        self._price_raw = prices

        # Distribution statistics (used by dims 1 + 2).
        mean = float(np.mean(prices))
        std = float(np.std(prices))
        median = float(np.median(prices))
        self._price_mean = mean
        self._price_std = max(std, 1e-6)
        self._price_median = median  # retained for legacy diagnostics only
        self._price_min = float(prices.min())
        self._price_max = float(prices.max())

        # Dim 3: Pre-compute hours_to_next_peak for every hour-of-year.
        # "Peak" = LMP >= `peak_percentile`-th percentile (default 75 pct).
        # Under Jiangsu TOU 2025 this picks out peak + super-peak tiers.
        peak_threshold = float(np.percentile(prices, peak_percentile))
        self._peak_threshold = peak_threshold
        peak_mask = prices >= peak_threshold
        hours_to_peak = np.zeros(8760, dtype=np.float32)
        if not peak_mask.any():
            # Edge case: flat price series, no peaks — leave zeros.
            max_gap = 1.0
        else:
            for h in range(8760):
                if peak_mask[h]:
                    hours_to_peak[h] = 0.0
                    continue
                for k in range(1, 8761):
                    if peak_mask[(h + k) % 8760]:
                        hours_to_peak[h] = float(k)
                        break
            max_gap = float(hours_to_peak.max())
            if max_gap < 1e-6:
                max_gap = 1.0
        self._hours_to_peak = (hours_to_peak / max_gap).astype(np.float32)
        self._max_gap_hours = max_gap

        self.lookahead = int(lookahead_hours)  # retained for backward compat (accessors)
        self._hour_idx = 0

        # New dim ranges (M2-E3b-v4):
        #   dim 1 current_price_norm   ∈ [-1, 2]
        #   dim 2 price_delta_next_1h  ∈ [-2, 2]
        #   dim 3 hours_to_next_peak_norm ∈ [0, 1]
        low = np.append(self.env.observation_space.low, [-1.0, -2.0, 0.0])
        high = np.append(self.env.observation_space.high, [2.0, 2.0, 1.0])
        self.observation_space = gym.spaces.Box(
            low=low.astype(np.float32),
            high=high.astype(np.float32),
            dtype=np.float32,
        )

    def _signals(self) -> Tuple[np.ndarray, float]:
        idx = self._hour_idx
        p = float(self._price_raw[idx])
        # Dim 1: z-score of current price, clipped to [-1, 2].
        current_norm = float(
            np.clip((p - self._price_mean) / self._price_std, -1.0, 2.0)
        )
        # Dim 2: 1-step forward delta / σ, clipped to [-2, 2].
        next_idx = (idx + 1) % 8760
        delta = (float(self._price_raw[next_idx]) - p) / self._price_std
        price_delta = float(np.clip(delta, -2.0, 2.0))
        # Dim 3: precomputed hours_to_next_peak_norm.
        htp = float(self._hours_to_peak[idx])
        return np.array([current_norm, price_delta, htp], dtype=np.float32), p

    def reset(self, *, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> Tuple[np.ndarray, Dict]:
        self._hour_idx = 0
        obs, info = self.env.reset(seed=seed, options=options)
        sig, raw = self._signals()
        info["current_price_usd_per_mwh"] = raw
        return np.append(obs, sig).astype(np.float32), info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        obs, reward, terminated, truncated, info = self.env.step(action)
        self._hour_idx = (self._hour_idx + 1) % 8760
        sig, raw = self._signals()
        info["current_price_usd_per_mwh"] = raw
        return np.append(obs, sig).astype(np.float32), reward, terminated, truncated, info

    @property
    def observation_variables(self):
        base = self.env.get_wrapper_attr('observation_variables')
        return list(base) + [
            'price_current_norm',
            'price_delta_next_1h',
            'price_hours_to_next_peak_norm',
        ]

    # Public accessors — RL-Cost / RL-Green rewards read these
    @property
    def price_series_raw(self) -> np.ndarray:
        return self._price_raw

    @property
    def current_hour_idx(self) -> int:
        return self._hour_idx
