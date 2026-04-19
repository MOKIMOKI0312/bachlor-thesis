"""Workload scheduling wrapper (tech route §2 / §6.1-F).

Adapted from SustainDC's CarbonLoadEnv.step queue logic (HewlettPackard/dc-rl,
MIT License; NeurIPS 2024). The queue-management core is copied largely
verbatim; we simply drop the SustainDC reward & framework coupling and make
it a pure observation/action wrapper over an EplusEnv.

Adds 9 dims to the observation tail (matches tech route §6.1-F):
    [current_workload,
     tasks_in_queue / queue_max_len,
     oldest_task_age / 24,
     average_task_age / 24,
     hist_0_6h, hist_6_12h, hist_12_18h, hist_18_24h, hist_24h_plus]

Intercepts `action[workload_idx]` (default 4 = ITE actuator per M1 env):
    < -0.33 → 0 (defer all shiftable)
    -0.33 ≤ x < 0.33 → 1 (do nothing)
    ≥ 0.33 → 2 (process from DTQ)
The wrapper then computes `current_utilization` from the queue dynamics and
writes it (0-1 float) back to `action[workload_idx]` for the underlying
EplusEnv's ITE actuator.

The base workload-per-hour is read from an external IT trace CSV (single
column 0-1, 8760 rows). `flexible_fraction` (default 0.3) splits this into
shiftable vs. non-shiftable tasks.
"""
from __future__ import annotations

import math
from collections import deque
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np
import pandas as pd

ACTION_DEFER = 0
ACTION_NOOP = 1
ACTION_PROCESS = 2

AGE_BINS_HOURS = [0, 6, 12, 18, 24, np.inf]


class WorkloadWrapper(gym.Wrapper):

    def __init__(
        self,
        env: gym.Env,
        it_trace_csv: str | Path,
        workload_idx: int = 4,
        flexible_fraction: float = 0.3,
        queue_max_len: int = 500,
        discretize_thresholds: Tuple[float, float] = (-0.33, 0.33),
    ):
        super().__init__(env)

        trace = pd.read_csv(it_trace_csv, header=None).iloc[:, 0].to_numpy(dtype=np.float32)
        if len(trace) != 8760:
            raise ValueError(
                f"IT trace must have 8760 rows, got {len(trace)} from {it_trace_csv}"
            )
        self._trace = np.clip(trace, 0.0, 1.0)
        self.workload_idx = int(workload_idx)
        self.flexible_fraction = float(flexible_fraction)
        self.non_flexible_fraction = 1.0 - self.flexible_fraction
        self.queue_max_len = int(queue_max_len)
        self.defer_thresh, self.process_thresh = map(float, discretize_thresholds)

        self._tasks_queue: deque = deque(maxlen=self.queue_max_len)
        self._hour_idx: int = 0
        self._current_day: int = 0
        self._current_hour: int = 0
        self._current_utilization: float = 0.0

        # Append 9 dims with low=0 high=1 (all normalised)
        low = np.append(self.env.observation_space.low, [0.0] * 9)
        high = np.append(self.env.observation_space.high, [1.0] * 9)
        self.observation_space = gym.spaces.Box(
            low=low.astype(np.float32),
            high=high.astype(np.float32),
            dtype=np.float32,
        )

    # --- helpers copied from SustainDC CarbonLoadEnv ---------------------

    def _task_age_histogram(self) -> np.ndarray:
        if not self._tasks_queue:
            return np.zeros(5, dtype=np.float32)
        ages = np.array(
            [
                (self._current_day - t["day"]) * 24 + (self._current_hour - t["hour"])
                for t in self._tasks_queue
            ],
            dtype=np.float32,
        )
        histogram, _ = np.histogram(ages, bins=AGE_BINS_HOURS)
        normalised = histogram / max(len(self._tasks_queue), 1)
        # Overdue bucket: indicator instead of proportion
        normalised[-1] = 1.0 if normalised[-1] > 0 else 0.0
        return normalised.astype(np.float32)

    def _queue_stats(self) -> Tuple[int, float, float]:
        n = len(self._tasks_queue)
        if n == 0:
            return 0, 0.0, 0.0
        ages = [
            (self._current_day - t["day"]) * 24 + (self._current_hour - t["hour"])
            for t in self._tasks_queue
        ]
        return n, float(max(ages)), float(sum(ages) / n)

    def _apply_workload_action(self, action_code: int) -> float:
        """Run one hour of the queue simulation for the given discrete action.
        Returns the resulting current_utilization (0-1).
        """
        workload = float(self._trace[self._hour_idx])
        non_shiftable = int(math.ceil(workload * self.non_flexible_fraction * 100))
        shiftable = int(math.floor(workload * self.flexible_fraction * 100))

        # Process overdue tasks first (>24h)
        overdue = [
            t for t in self._tasks_queue
            if (self._current_day - t["day"]) * 24 + (self._current_hour - t["hour"]) > 24
        ]
        available = 90 - (non_shiftable + shiftable)
        overdue_processed = 0
        if available > 0 and overdue:
            overdue_processed = min(len(overdue), available)
            for t in overdue[:overdue_processed]:
                self._tasks_queue.remove(t)
        available = 90 - (non_shiftable + shiftable + overdue_processed)

        if action_code == ACTION_DEFER:
            tasks_to_add = min(shiftable, self.queue_max_len - len(self._tasks_queue))
            self._tasks_queue.extend(
                [{"day": self._current_day, "hour": self._current_hour, "utilization": 1}]
                * tasks_to_add
            )
            util = (overdue_processed + (shiftable - tasks_to_add)) / 100.0
        elif action_code == ACTION_PROCESS and available >= 1:
            to_process = min(shiftable, available, len(self._tasks_queue))
            if to_process == len(self._tasks_queue):
                self._tasks_queue.clear()
            else:
                for _ in range(to_process):
                    self._tasks_queue.popleft()
            util = (shiftable + to_process + overdue_processed) / 100.0
        else:  # NOOP or PROCESS with no capacity
            util = (shiftable + overdue_processed) / 100.0

        # Add non-shiftable always
        util += non_shiftable / 100.0
        return float(np.clip(util, 0.0, 1.0))

    def _signals(self) -> np.ndarray:
        n, oldest, avg = self._queue_stats()
        hist = self._task_age_histogram()
        return np.array(
            [
                self._current_utilization,
                n / self.queue_max_len,
                oldest / 24.0,
                avg / 24.0,
                *hist,
            ],
            dtype=np.float32,
        )

    # --- gym API ---------------------------------------------------------

    def reset(self, *, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> Tuple[np.ndarray, Dict]:
        self._tasks_queue.clear()
        self._hour_idx = 0
        self._current_day = 0
        self._current_hour = 0
        self._current_utilization = 0.0
        obs, info = self.env.reset(seed=seed, options=options)
        sig = self._signals()
        info.update({
            "workload_action": ACTION_NOOP,
            "workload_utilization": 0.0,
            "workload_queue_len": 0,
        })
        return np.append(obs, sig).astype(np.float32), info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        action = np.array(action, dtype=np.float32, copy=True)

        # Discretise SAC continuous output at workload_idx → {0,1,2}
        raw = float(action[self.workload_idx])
        if raw < self.defer_thresh:
            wa = ACTION_DEFER
        elif raw < self.process_thresh:
            wa = ACTION_NOOP
        else:
            wa = ACTION_PROCESS

        # Run queue simulation → utilization 0-1
        self._current_utilization = self._apply_workload_action(wa)

        # Overwrite action[workload_idx] with the resulting utilization so
        # that the ITE actuator receives the correct value.
        action[self.workload_idx] = self._current_utilization

        obs, reward, terminated, truncated, info = self.env.step(action)

        # Advance clock
        self._hour_idx = (self._hour_idx + 1) % 8760
        self._current_hour = (self._current_hour + 1) % 24
        if self._current_hour == 0:
            self._current_day += 1

        sig = self._signals()
        info["workload_action"] = wa
        info["workload_utilization"] = self._current_utilization
        info["workload_queue_len"] = len(self._tasks_queue)
        return np.append(obs, sig).astype(np.float32), reward, terminated, truncated, info

    @property
    def observation_variables(self):
        base = self.env.get_wrapper_attr('observation_variables')
        return list(base) + [
            'workload_current_utilization',
            'workload_queue_norm',
            'workload_oldest_age_norm',
            'workload_avg_age_norm',
            'workload_hist_0_6h',
            'workload_hist_6_12h',
            'workload_hist_12_18h',
            'workload_hist_18_24h',
            'workload_hist_24h_plus',
        ]
