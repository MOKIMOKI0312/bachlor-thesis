"""Gymnasium wrappers for TES valve control, fixed actions, and TOU shaping.

The original ``TESIncrementalWrapper`` is kept for backward compatibility.
M2-F1 uses ``TESTargetValveWrapper`` to avoid deterministic policies drifting
to saturated TES valve positions through an integrator action.
"""
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import gymnasium as gym
import numpy as np


class FixedActionInsertWrapper(gym.ActionWrapper):
    """Expose a reduced action vector while inserting fixed full-env actions.

    The wrapped EnergyPlus environment keeps its original full action space and
    actuator list.  The agent sees only the non-fixed dimensions; before
    stepping the inner environment, this wrapper inserts the fixed values back
    into their original indices.
    """

    def __init__(
        self,
        env: gym.Env,
        fixed_actions: Optional[Mapping[int, float]] = None,
        fixed_action_names: Optional[Mapping[int, str] | Sequence[str]] = None,
    ):
        super().__init__(env)
        if not isinstance(env.action_space, gym.spaces.Box):
            raise TypeError(
                "FixedActionInsertWrapper requires a Box action_space, "
                f"got {type(env.action_space).__name__}"
            )

        self.fixed_actions = {
            int(idx): float(value)
            for idx, value in (fixed_actions or {0: 1.0}).items()
        }
        full_dim = int(env.action_space.shape[0])
        invalid = [idx for idx in self.fixed_actions if idx < 0 or idx >= full_dim]
        if invalid:
            raise ValueError(
                f"Fixed action indices {invalid} outside full action dimension {full_dim}"
            )

        self.fixed_indices = tuple(sorted(self.fixed_actions))
        self.agent_indices = tuple(idx for idx in range(full_dim) if idx not in self.fixed_actions)
        self.full_action_dim = full_dim
        self.agent_action_dim = len(self.agent_indices)

        low = np.asarray(env.action_space.low, dtype=np.float32)
        high = np.asarray(env.action_space.high, dtype=np.float32)
        for idx, value in self.fixed_actions.items():
            if value < float(low[idx]) or value > float(high[idx]):
                raise ValueError(
                    f"Fixed action {idx}={value} outside [{low[idx]}, {high[idx]}]"
                )
        self.action_space = gym.spaces.Box(
            low=low[list(self.agent_indices)].astype(np.float32),
            high=high[list(self.agent_indices)].astype(np.float32),
            dtype=np.float32,
        )

        full_names = list(self.env.get_wrapper_attr("action_variables"))
        if len(full_names) != full_dim:
            raise ValueError(
                f"action_variables length {len(full_names)} does not match "
                f"full action dim {full_dim}: {full_names}"
            )
        self.full_action_variables = full_names
        self.action_variables = [full_names[idx] for idx in self.agent_indices]

        if fixed_action_names is None:
            names = {idx: full_names[idx] for idx in self.fixed_indices}
        elif isinstance(fixed_action_names, Mapping):
            names = {int(idx): str(name) for idx, name in fixed_action_names.items()}
        else:
            seq = list(fixed_action_names)
            if len(seq) != len(self.fixed_indices):
                raise ValueError(
                    "fixed_action_names sequence length must match fixed_actions"
                )
            names = {idx: str(name) for idx, name in zip(self.fixed_indices, seq)}
        self.fixed_action_names = names
        self.fixed_action_variables = [names[idx] for idx in self.fixed_indices]
        self.last_agent_action: Optional[np.ndarray] = None
        self.last_full_action: Optional[np.ndarray] = None

    def action(self, action: np.ndarray) -> np.ndarray:
        agent_action = np.asarray(action, dtype=np.float32)
        if agent_action.shape != (self.agent_action_dim,):
            raise ValueError(
                f"Expected reduced action shape {(self.agent_action_dim,)}, "
                f"got {agent_action.shape}"
            )

        full_action = np.empty(self.full_action_dim, dtype=np.float32)
        full_action[list(self.agent_indices)] = agent_action
        for idx, value in self.fixed_actions.items():
            full_action[idx] = np.float32(value)
        full_action = np.clip(
            full_action,
            np.asarray(self.env.action_space.low, dtype=np.float32),
            np.asarray(self.env.action_space.high, dtype=np.float32),
        ).astype(np.float32)
        return full_action

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        agent_action = np.asarray(action, dtype=np.float32)
        full_action = self.action(agent_action)
        obs, reward, terminated, truncated, info = self.env.step(full_action)

        self.last_agent_action = agent_action.copy()
        self.last_full_action = full_action.copy()
        info["agent_action"] = agent_action.copy()
        info["full_action"] = full_action.copy()
        info["action_mapping"] = {
            "agent_indices": self.agent_indices,
            "fixed_indices": self.fixed_indices,
            "full_action_variables": self.full_action_variables,
            "agent_action_variables": self.action_variables,
        }
        for idx, value in self.fixed_actions.items():
            name = self.fixed_action_names.get(idx, self.full_action_variables[idx])
            info[f"fixed_{name}"] = float(value)

        # LoggerWrapper aligns action values by action_variables.  Expose the
        # reduced agent action here and keep the full vector separately above.
        info["action"] = agent_action.copy()
        return obs, reward, terminated, truncated, info

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict]:
        obs, info = self.env.reset(seed=seed, options=options)
        self.last_agent_action = None
        self.last_full_action = None
        for idx, value in self.fixed_actions.items():
            name = self.fixed_action_names.get(idx, self.full_action_variables[idx])
            info[f"fixed_{name}"] = float(value)
        info["action_mapping"] = {
            "agent_indices": self.agent_indices,
            "fixed_indices": self.fixed_indices,
            "full_action_variables": self.full_action_variables,
            "agent_action_variables": self.action_variables,
        }
        return obs, info


class TESIncrementalWrapper(gym.Wrapper):

    def __init__(
        self,
        env: gym.Env,
        valve_idx: int = 5,
        delta_max: float = 0.25,
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
        # Randomizing the valve here would not randomize TES SOC: SOC is the
        # tank's physical thermal state, while this wrapper only controls the
        # external flow command. Keep the valve neutral at episode start.
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


class TESTargetValveWrapper(gym.Wrapper):
    """Rate-limited target TES valve control.

    The agent action at ``valve_idx`` is interpreted as a target valve
    position in [-1, 1].  The physical command sent to EnergyPlus is
    rate-limited toward that target, preventing small actor biases from
    integrating into permanent +/-1 saturation.

    Sign convention follows the EnergyPlus EMS model:
      valve > 0: discharge/use TES
      valve < 0: charge/source TES
    """

    def __init__(
        self,
        env: gym.Env,
        valve_idx: int = 5,
        rate_limit: float = 0.25,
        soc_low_guard: float = 0.10,
        soc_high_guard: float = 0.90,
        soc_variable: str = "TES_SOC",
    ):
        super().__init__(env)
        self.valve_idx = int(valve_idx)
        self.rate_limit = float(rate_limit)
        self.soc_low_guard = float(soc_low_guard)
        self.soc_high_guard = float(soc_high_guard)
        self.soc_variable = soc_variable
        self._valve: float = 0.0
        self._last_soc: Optional[float] = None

        obs_names = list(self.env.get_wrapper_attr("observation_variables"))
        if soc_variable not in obs_names:
            raise ValueError(
                f"{soc_variable!r} not found in observation_variables: {obs_names}"
            )
        self._soc_idx = obs_names.index(soc_variable)

        low = np.append(self.env.observation_space.low, -1.0)
        high = np.append(self.env.observation_space.high, 1.0)
        self.observation_space = gym.spaces.Box(
            low=low.astype(np.float32),
            high=high.astype(np.float32),
            dtype=np.float32,
        )

    def _update_soc(self, obs: np.ndarray) -> None:
        try:
            soc = float(obs[self._soc_idx])
        except (IndexError, TypeError, ValueError):
            soc = float("nan")
        self._last_soc = soc if np.isfinite(soc) else None

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict]:
        self._valve = 0.0
        obs, info = self.env.reset(seed=seed, options=options)
        self._update_soc(obs)
        obs = np.append(obs, np.float32(self._valve))
        info["tes_valve_target"] = 0.0
        info["tes_valve_position"] = self._valve
        info["tes_guard_clipped"] = False
        info["tes_action_mode"] = "target_rate_limited"
        return obs, info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        action = np.array(action, dtype=np.float32, copy=True)
        raw_target = float(np.clip(action[self.valve_idx], -1.0, 1.0))
        target = raw_target
        guard_clipped = False

        if self._last_soc is not None:
            if self._last_soc >= self.soc_high_guard and target < 0.0:
                target = 0.0
                guard_clipped = True
            elif self._last_soc <= self.soc_low_guard and target > 0.0:
                target = 0.0
                guard_clipped = True

        delta = float(np.clip(target - self._valve, -self.rate_limit, self.rate_limit))
        self._valve = float(np.clip(self._valve + delta, -1.0, 1.0))
        action[self.valve_idx] = self._valve

        obs, reward, terminated, truncated, info = self.env.step(action)
        self._update_soc(obs)
        obs = np.append(obs, np.float32(self._valve))

        info["tes_valve_target"] = raw_target
        info["tes_valve_position"] = self._valve
        info["tes_guard_clipped"] = guard_clipped
        info["tes_action_mode"] = "target_rate_limited"
        return obs, reward, terminated, truncated, info

    @property
    def observation_variables(self):
        base = self.env.get_wrapper_attr("observation_variables")
        return list(base) + ["TES_valve_wrapper_position"]


class TESPriceShapingWrapper(gym.Wrapper):
    """TOU-aware TES reward shaping used by M2-F1 training.

    Adds target-SOC PBRS, an optional short-lived teacher direction term, and
    a small valve regularizer.  It does not change observations or actions.

    The teacher term is disabled by default because it is not policy-invariant
    PBRS.  Enable it explicitly for curriculum experiments only.
    """

    def __init__(
        self,
        env: gym.Env,
        gamma: float = 0.99,
        kappa: float = 1.0,
        teacher_initial_weight: float = 0.0,
        teacher_decay_episodes: float = 15.0,
        valve_penalty_weight: float = 0.02,
        high_price_threshold: float = 0.75,
        low_price_threshold: float = -0.50,
        near_peak_threshold: float = 0.40,
        target_soc_high: float = 0.85,
        target_soc_low: float = 0.30,
        target_soc_neutral: float = 0.50,
        soc_charge_limit: float = 0.85,
        soc_discharge_limit: float = 0.20,
        invalid_action_penalty_weight: float = 0.0,
    ):
        super().__init__(env)
        self.gamma = float(gamma)
        self.kappa = float(kappa)
        self.teacher_initial_weight = float(teacher_initial_weight)
        self.teacher_decay_episodes = max(float(teacher_decay_episodes), 1.0)
        self.valve_penalty_weight = float(valve_penalty_weight)
        self.invalid_action_penalty_weight = float(invalid_action_penalty_weight)
        self.high_price_threshold = float(high_price_threshold)
        self.low_price_threshold = float(low_price_threshold)
        self.near_peak_threshold = float(near_peak_threshold)
        self.target_soc_high = float(target_soc_high)
        self.target_soc_low = float(target_soc_low)
        self.target_soc_neutral = float(target_soc_neutral)
        self.soc_charge_limit = float(soc_charge_limit)
        self.soc_discharge_limit = float(soc_discharge_limit)

        names = list(self.env.get_wrapper_attr("observation_variables"))
        required = [
            "TES_SOC",
            "TES_valve_wrapper_position",
            "price_current_norm",
            "price_hours_to_next_peak_norm",
        ]
        missing = [name for name in required if name not in names]
        if missing:
            raise ValueError(f"TESPriceShapingWrapper missing observation columns: {missing}")
        self._idx_soc = names.index("TES_SOC")
        self._idx_valve = names.index("TES_valve_wrapper_position")
        self._idx_price = names.index("price_current_norm")
        self._idx_hours_to_peak = names.index("price_hours_to_next_peak_norm")

        self._episode_index = -1
        self._prev_phi = 0.0
        self._last_soc: Optional[float] = None

    def _target_soc(self, price: float, hours_to_peak_norm: float) -> float:
        if price >= self.high_price_threshold:
            return self.target_soc_low
        if price <= self.low_price_threshold and hours_to_peak_norm <= self.near_peak_threshold:
            return self.target_soc_high
        return self.target_soc_neutral

    def _phi(self, soc: float, target_soc: float) -> float:
        return -self.kappa * (soc - target_soc) ** 2

    def _teacher_weight(self) -> float:
        frac = max(0.0, 1.0 - self._episode_index / self.teacher_decay_episodes)
        return self.teacher_initial_weight * frac

    def _signals(self, obs: np.ndarray) -> Tuple[float, float, float, float]:
        soc = float(np.clip(obs[self._idx_soc], 0.0, 1.0))
        valve = float(np.clip(obs[self._idx_valve], -1.0, 1.0))
        price = float(obs[self._idx_price])
        hours_to_peak_norm = float(obs[self._idx_hours_to_peak])
        return soc, valve, price, hours_to_peak_norm

    def _raw_valve_target(self, action: np.ndarray, info: Dict) -> float:
        if "tes_valve_target" in info:
            return float(np.clip(info["tes_valve_target"], -1.0, 1.0))
        try:
            action_arr = np.asarray(action, dtype=np.float32)
            if action_arr.size:
                return float(np.clip(action_arr[-1], -1.0, 1.0))
        except (TypeError, ValueError):
            pass
        return float(np.clip(info.get("tes_valve_position", 0.0), -1.0, 1.0))

    def _invalid_action_penalty(self, soc: Optional[float], raw_target: float) -> float:
        if soc is None or self.invalid_action_penalty_weight == 0.0:
            return 0.0
        if soc >= self.soc_charge_limit and raw_target < 0.0:
            return -self.invalid_action_penalty_weight * abs(raw_target)
        if soc <= self.soc_discharge_limit and raw_target > 0.0:
            return -self.invalid_action_penalty_weight * abs(raw_target)
        return 0.0

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict]:
        obs, info = self.env.reset(seed=seed, options=options)
        self._episode_index += 1
        soc, _, price, hours_to_peak = self._signals(obs)
        target = self._target_soc(price, hours_to_peak)
        self._prev_phi = self._phi(soc, target)
        self._last_soc = soc
        info["tes_soc_target"] = target
        info["tes_pbrs_term"] = 0.0
        info["tes_teacher_term"] = 0.0
        info["tes_teacher_weight"] = self._teacher_weight()
        info["tes_valve_penalty"] = 0.0
        info["tes_invalid_action_penalty"] = 0.0
        info["tes_shaping_total"] = 0.0
        return obs, info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        obs, reward, terminated, truncated, info = self.env.step(action)
        prev_soc = self._last_soc
        soc, valve, price, hours_to_peak = self._signals(obs)
        self._last_soc = soc
        target = self._target_soc(price, hours_to_peak)

        phi = self._phi(soc, target)
        pbrs = self.gamma * phi - self._prev_phi
        self._prev_phi = phi

        desired = 0.0
        if price >= self.high_price_threshold and soc > self.soc_discharge_limit:
            desired = 1.0
        elif (
            price <= self.low_price_threshold
            and hours_to_peak <= self.near_peak_threshold
            and soc < self.soc_charge_limit
        ):
            desired = -1.0

        teacher_weight = self._teacher_weight()
        teacher = teacher_weight * desired * valve
        valve_penalty = -self.valve_penalty_weight * valve * valve
        raw_target = self._raw_valve_target(action, info)
        invalid_action_penalty = self._invalid_action_penalty(prev_soc, raw_target)
        shaping_total = pbrs + teacher + valve_penalty + invalid_action_penalty
        reward = float(reward + shaping_total)

        info["reward"] = reward
        info["tes_soc_target"] = target
        info["tes_pbrs_term"] = pbrs
        info["tes_teacher_term"] = teacher
        info["tes_teacher_weight"] = teacher_weight
        info["tes_valve_penalty"] = valve_penalty
        info["tes_invalid_action_penalty"] = invalid_action_penalty
        info["tes_shaping_total"] = shaping_total
        return obs, reward, terminated, truncated, info
