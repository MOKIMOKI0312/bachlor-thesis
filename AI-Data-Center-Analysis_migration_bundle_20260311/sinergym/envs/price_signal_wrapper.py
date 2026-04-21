"""Price signal wrapper (tech route §5.2).

Reads a precomputed hourly electricity price CSV (e.g. CAISO NP15 2023 DAM LMP)
and injects 3 dims into obs:
  - current_price          : tanh-squashed LMP at the current simulation hour
  - price_future_slope     : linear-regression slope over the next K hours
  - price_mean             : mean tanh-squashed LMP over the next K hours

Normalisation (M2-E3b fix, Issue C, 2026-04-21): tanh squash centred on the
*median* with a 2σ scale, i.e. ``tanh((price - median) / (2σ))``.
  - median (rather than mean) is robust to scarcity spikes / negative-price
    outliers that would otherwise pull the centre off.
  - 2σ scale keeps ±2σ of samples in tanh's near-linear region while smoothly
    compressing the 120-kurtosis tails that triggered DSAC-T critic variance
    collapse under the previous 5/95 percentile min-max normalisation.
  - Output is in the open interval (-1, 1) (tanh range), NOT [0, 1].

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
        # M2-E3b fix (Issue C, 2026-04-21): replaced 5/95-percentile min-max
        # clip with a tanh squash anchored on the MEDIAN with a 2σ scale. The
        # old min-max output (a) saturated hard at the clip boundaries (no
        # gradient past ~$40 / ~$90), and (b) bounded the 3 price dims to
        # [0, 1] which — together with CAISO NP15's kurtosis≈120 — produced
        # reward targets with heavy tails that violated DSAC-T's Gaussian
        # critic assumption, causing ep30-50 variance explosion.  tanh gives
        # a smooth, bounded, (-1, 1) output that preserves local gradient
        # around the median band while softly compressing scarcity tails.
        # Raw series stays in `_price_raw` for reward functions.
        self._price_min = float(prices.min())
        self._price_max = float(prices.max())
        median = float(np.median(prices))
        std = float(np.std(prices))
        self._price_median = median
        self._price_std = std
        self._price_scale = max(2.0 * std, 1e-6)
        self._price_norm = np.tanh((prices - median) / self._price_scale).astype(np.float32)

        self.lookahead = int(lookahead_hours)
        self._hour_idx = 0

        # tanh output ∈ (-1, 1); slope stays in [-1, 1].
        low = np.append(self.env.observation_space.low, [-1.0, -1.0, -1.0])
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
            # Scale to [-1, 1]: tanh-normalised y ∈ (-1, 1), so the maximum
            # possible |slope| over K steps is 2/(K-1). Multiply by (K-1)/2
            # and clip to bound to [-1, 1].
            slope = float(np.clip(slope_raw * (self.lookahead - 1) / 2.0, -1.0, 1.0))
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
