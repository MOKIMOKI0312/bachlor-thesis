"""Price signal wrapper (tech route §5.2).

Reads a precomputed hourly electricity price CSV (e.g. CAISO NP15 2023 DAM LMP)
and injects 3 dims into obs:
  - current_price          : normalised LMP at the current simulation hour
  - price_future_slope     : linear-regression slope over the next K hours
  - price_mean             : mean LMP over the next K hours

Normalisation is min-max to [0, 1] using the global min/max of the loaded
series (preserves shape, avoids running-stats drift).

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
        # M2 fix (2026-04-19): CAISO NP15 2023 has mean=$61 but max=$1091 (rare
        # spikes), so global min-max compresses the typical $40-$80 peak-valley
        # band to near-zero variance. Use 5th/95th percentile clip instead so
        # the policy can perceive the day-to-day arbitrage signal. Raw series
        # is still preserved in `_price_raw` for reward functions.
        self._price_min = float(prices.min())
        self._price_max = float(prices.max())
        lo = float(np.percentile(prices, 5))
        hi = float(np.percentile(prices, 95))
        self._price_clip_lo = lo
        self._price_clip_hi = hi
        self._price_span = max(hi - lo, 1e-6)
        self._price_norm = np.clip((prices - lo) / self._price_span, 0.0, 1.0).astype(np.float32)

        self.lookahead = int(lookahead_hours)
        self._hour_idx = 0

        low = np.append(self.env.observation_space.low, [0.0, -1.0, 0.0])
        high = np.append(self.env.observation_space.high, [1.0, 1.0, 1.0])
        self.observation_space = gym.spaces.Box(
            low=low.astype(np.float32),
            high=high.astype(np.float32),
            dtype=np.float32,
        )

    # Helper: next K hours, wrapping year-end
    def _future_window(self) -> np.ndarray:
        idx = (self._hour_idx + np.arange(self.lookahead)) % 8760
        return self._price_norm[idx]

    def _signals(self) -> Tuple[np.ndarray, float]:
        current_norm = float(self._price_norm[self._hour_idx])
        future = self._future_window()
        # Slope: simple linear regression y = a*t + b over t=0..K-1
        t = np.arange(self.lookahead, dtype=np.float32)
        if future.std() < 1e-8:
            slope = 0.0
        else:
            slope_raw = float(np.polyfit(t, future, 1)[0])
            # Scale to [-1, 1]: max possible abs slope for normed y ∈ [0,1]
            # over K steps is 1/(K-1). Clip & rescale.
            slope = float(np.clip(slope_raw * (self.lookahead - 1), -1.0, 1.0))
        mean = float(future.mean())
        raw_price = float(self._price_raw[self._hour_idx])
        return np.array([current_norm, slope, mean], dtype=np.float32), raw_price

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
        return list(base) + ['price_current_norm', 'price_future_slope', 'price_future_mean']

    # Public accessors — RL-Cost / RL-Green rewards read these
    @property
    def price_series_raw(self) -> np.ndarray:
        return self._price_raw

    @property
    def current_hour_idx(self) -> int:
        return self._hour_idx
