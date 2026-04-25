"""Temperature trend wrapper (tech route §6.1-C).

Reads the outdoor dry-bulb temperature series from the TMY EPW that drives
the simulation (8760 hourly values) and injects 6 lookahead-trend dims:

  - temperature_slope          : linear-regression slope of the next K hours
                                 (normalised temperature, ∈ [-1, 1])
  - temp_mean                  : mean of the next K hours (normalised ∈ [0, 1])
  - temp_std                   : stdev of the next K hours (normalised ∈ [0, 1])
  - temp_percentile            : percentile rank of the CURRENT hour's temp
                                 among the next K hours (∈ [0, 1])
  - time_to_next_temp_peak     : normalised hours until the next 24 h peak
                                 (∈ [0, 1], divisor=24)
  - time_to_next_temp_valley   : normalised hours until the next 24 h valley

Normalisation for temp values uses min-max over the entire loaded 8760-hour
series (stable across episodes).

Index tracking: the wrapper maintains its own step counter (hour_of_year ∈
[0, 8759]) that loops each episode, mirroring PriceSignalWrapper /
PVSignalWrapper. It does not rely on the base env's time_variables — this
keeps ordering vs TimeEncodingWrapper flexible.

The wrapper must be applied BEFORE NormalizeObservation. In the M2 chain it
is slotted right after TimeEncodingWrapper — see run_m2_training.py build_env.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np


def _load_epw_temperature(epw_path: str | Path) -> np.ndarray:
    """Parse the dry-bulb temperature column from an EPW file.

    EPW format: 8 header lines then 8760 CSV data rows. Dry-bulb temperature
    sits at column index 6 (0-based): year, month, day, hour, minute,
    data-source-flags, dry_bulb_temp, ...

    Falls back to pvlib.iotools.read_epw if the manual parse fails (e.g. the
    file uses an unexpected encoding or row count).
    """
    epw_path = Path(epw_path)
    try:
        temps = []
        with open(epw_path, "r", encoding="latin-1") as f:
            for _ in range(8):
                f.readline()  # skip header block
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) < 7:
                    continue
                temps.append(float(parts[6]))
        arr = np.array(temps, dtype=np.float32)
        if arr.shape[0] != 8760:
            raise ValueError(
                f"EPW manual parse: expected 8760 rows, got {arr.shape[0]} from {epw_path}"
            )
        return arr
    except Exception as exc:  # pragma: no cover — fallback
        try:
            from pvlib.iotools import read_epw

            df, _ = read_epw(str(epw_path))
            col = None
            for cand in ("temp_air", "dry_bulb_temperature", "DryBulbTemp"):
                if cand in df.columns:
                    col = cand
                    break
            if col is None:
                raise RuntimeError(
                    f"pvlib read_epw produced no temp_air column; have {list(df.columns)[:5]}..."
                )
            arr = df[col].to_numpy(dtype=np.float32)
            if arr.shape[0] != 8760:
                raise ValueError(f"pvlib parse: got {arr.shape[0]} rows")
            return arr
        except Exception as exc2:
            raise RuntimeError(
                f"Failed to parse EPW temperature from {epw_path}. "
                f"Manual error: {exc}. pvlib fallback error: {exc2}"
            )


class TempTrendWrapper(gym.Wrapper):
    """Append 6-dim outdoor temperature lookahead trend features to obs."""

    def __init__(
        self,
        env: gym.Env,
        epw_path: str | Path,
        lookahead_hours: int = 6,
    ):
        super().__init__(env)

        temps = _load_epw_temperature(epw_path)
        self._temp_raw = temps
        self._temp_min = float(temps.min())
        self._temp_max = float(temps.max())
        self._temp_span = max(self._temp_max - self._temp_min, 1e-6)
        self._temp_norm = (temps - self._temp_min) / self._temp_span  # ∈ [0, 1]

        self.lookahead = int(lookahead_hours)
        self._hour_idx = 0

        # Observation space bounds for the 6 appended dims:
        #   slope ∈ [-1, 1], mean ∈ [0, 1], std ∈ [0, 1], percentile ∈ [0, 1],
        #   time_to_peak ∈ [0, 1], time_to_valley ∈ [0, 1]
        low = np.append(
            self.env.observation_space.low,
            [-1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        )
        high = np.append(
            self.env.observation_space.high,
            [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        )
        self.observation_space = gym.spaces.Box(
            low=low.astype(np.float32),
            high=high.astype(np.float32),
            dtype=np.float32,
        )

    # ---------------- helpers ----------------

    def _future_window(self) -> np.ndarray:
        idx = (self._hour_idx + np.arange(self.lookahead)) % 8760
        return self._temp_norm[idx]

    def _time_to_extreme(self, kind: str) -> float:
        """Hours until the next 24 h peak (max) or valley (min), normalised /24."""
        window_raw = self._temp_raw[
            (self._hour_idx + np.arange(24)) % 8760
        ]
        if kind == "peak":
            offset = int(np.argmax(window_raw))
        else:
            offset = int(np.argmin(window_raw))
        # offset is hours from now (0 = current hour itself)
        return float(offset) / 24.0  # ∈ [0, 1)

    def _signals(self) -> np.ndarray:
        future = self._future_window()
        t = np.arange(self.lookahead, dtype=np.float32)
        if future.std() < 1e-8:
            slope = 0.0
        else:
            slope_raw = float(np.polyfit(t, future, 1)[0])
            # Rescale by (K-1) so slope ∈ [-1, 1] for normed y ∈ [0, 1].
            slope = float(np.clip(slope_raw * (self.lookahead - 1), -1.0, 1.0))
        mean = float(future.mean())
        std = float(future.std())
        # Percentile of current temperature within the lookahead window.
        current_norm = float(self._temp_norm[self._hour_idx])
        # Fraction of window <= current (linear rank).
        percentile = float(np.mean(future <= current_norm))
        ttp = self._time_to_extreme("peak")
        ttv = self._time_to_extreme("valley")
        return np.array([slope, mean, std, percentile, ttp, ttv], dtype=np.float32)

    # ---------------- gym API ----------------

    def reset(
        self, *, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict]:
        self._hour_idx = 0
        obs, info = self.env.reset(seed=seed, options=options)
        sig = self._signals()
        return np.append(obs, sig).astype(np.float32), info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        obs, reward, terminated, truncated, info = self.env.step(action)
        self._hour_idx = (self._hour_idx + 1) % 8760
        sig = self._signals()
        return np.append(obs, sig).astype(np.float32), reward, terminated, truncated, info

    @property
    def observation_variables(self):
        base = self.env.get_wrapper_attr("observation_variables")
        return list(base) + [
            "temperature_slope",
            "temp_mean",
            "temp_std",
            "temp_percentile",
            "time_to_next_temp_peak",
            "time_to_next_temp_valley",
        ]

    @property
    def temp_series_raw(self) -> np.ndarray:
        return self._temp_raw

    @property
    def current_hour_idx(self) -> int:
        return self._hour_idx
