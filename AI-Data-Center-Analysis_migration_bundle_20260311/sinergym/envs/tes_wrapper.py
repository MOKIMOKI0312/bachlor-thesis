"""Gymnasium wrapper for TES incremental valve control (tech route §3.1).

Wraps an EplusEnv that has a TES actuator at action index `valve_idx`.
Converts the agent's Δv output to a recursive valve position v(t+1) = clip(v(t) + Δv * δmax, -1, +1),
then passes the signed valve position v directly to EnergyPlus (EMS reads it and converts to flow).

Also injects `TES_valve_wrapper_position` into the observation vector.
"""
from typing import Any, Dict, Optional, Tuple

import gymnasium as gym
import numpy as np


class TESIncrementalWrapper(gym.Wrapper):

    def __init__(
        self,
        env: gym.Env,
        valve_idx: int = 5,
        delta_max: float = 0.20,
    ):
        super().__init__(env)
        self.valve_idx = valve_idx
        self.delta_max = delta_max
        self._valve: float = 0.0

        # Extend observation space by 1 dim (valve_position ∈ [-1, 1])
        low = np.append(self.env.observation_space.low, -1.0)
        high = np.append(self.env.observation_space.high, 1.0)
        self.observation_space = gym.spaces.Box(
            low=low.astype(np.float32),
            high=high.astype(np.float32),
            dtype=np.float32,
        )

    def reset(self, *, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None) -> Tuple[np.ndarray, Dict]:
        self._valve = 0.0
        # TODO(pbrs-design §4 / Liu-Henze 2006): proper initial SOC
        # randomization requires modifying the `ThermalStorage:ChilledWater`
        # `initial_tank_temperature` field in the epJSON. That is outside this
        # wrapper's scope — it belongs to eplus-modeler. Randomizing valve
        # position here does NOT directly control initial SOC (SOC is
        # determined by tank temperature, not valve). Deferring to
        # eplus-modeler pass. For now, valve starts at 0 (centred).
        obs, info = self.env.reset(seed=seed, options=options)
        obs = np.append(obs, np.float32(self._valve))
        return obs, info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        action = np.array(action, dtype=np.float32, copy=True)

        # Incremental update: action[valve_idx] is Δv ∈ [-1, 1], scaled by δmax
        delta_v = action[self.valve_idx] * self.delta_max
        self._valve = float(np.clip(self._valve + delta_v, -1.0, 1.0))

        # Replace Δv with actual valve position for EnergyPlus
        action[self.valve_idx] = self._valve

        obs, reward, terminated, truncated, info = self.env.step(action)
        obs = np.append(obs, np.float32(self._valve))

        info['tes_valve_position'] = self._valve
        return obs, reward, terminated, truncated, info

    @property
    def observation_variables(self):
        base = self.env.get_wrapper_attr('observation_variables')
        return list(base) + ['TES_valve_wrapper_position']
