"""Gymnasium wrappers for TES valve control, fixed actions, and TOU shaping.

The original ``TESIncrementalWrapper`` is kept for backward compatibility.
M2-F1 uses ``TESTargetValveWrapper`` to avoid deterministic policies drifting
to saturated TES valve positions through an integrator action.
"""
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

import gymnasium as gym
import numpy as np


def _tes_direction_mode(value: float, deadband: float = 0.0) -> str:
    if value > deadband:
        return "discharge"
    if value < -deadband:
        return "charge"
    return "idle"


class FixedActionInsertWrapper(gym.ActionWrapper):
    """Expose a reduced action vector while inserting fixed full-env actions.

    The wrapped EnergyPlus environment keeps its original full action space and
    actuator list.  The agent sees only the non-fixed dimensions; before
    stepping the inner environment, this wrapper inserts the fixed values back
    into their original indices.

    info dict semantics (C6 — by-design overload):
        - ``info["agent_action"]``: reduced agent action (shape = agent_action_dim).
        - ``info["full_action"]``: full env action including fixed dims (shape =
          full_action_dim).
        - ``info["action"]``: **reduced agent action** (same as ``agent_action``).
          Overwritten by this wrapper because Sinergym's LoggerWrapper aligns
          the persisted ``action`` columns to ``action_variables``, which under
          this wrapper is the reduced list. Downstream consumers that need the
          full vector must read ``info["full_action"]``.
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

        info["action_dim"] = self.agent_action_dim
        info.setdefault("tes_action_semantics", "signed_scalar")
        info.setdefault("tes_direction_deadband", None)
        info.setdefault("tes_option_hold_steps", None)
        info.setdefault("tes_option_hold_counter_remaining", None)
        info.setdefault("tes_option_accepted_new_mode", None)
        info.setdefault("tes_held_direction_mode", None)
        info.setdefault("tes_held_amplitude_mapped", None)

        # C6: LoggerWrapper aligns action values by action_variables, which
        # under this wrapper is the *reduced* list. Overwriting info["action"]
        # to the reduced vector is intentional — see the class docstring for
        # the explicit semantics. Use info["full_action"] when the full env
        # action is needed.
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
        info["action_dim"] = self.agent_action_dim
        info.setdefault("tes_action_semantics", "signed_scalar")
        info.setdefault("tes_direction_deadband", None)
        info.setdefault("tes_option_hold_steps", None)
        info.setdefault("tes_option_hold_counter_remaining", None)
        info.setdefault("tes_option_accepted_new_mode", None)
        info.setdefault("tes_held_direction_mode", None)
        info.setdefault("tes_held_amplitude_mapped", None)
        return obs, info


class TESDirectionAmplitudeActionWrapper(gym.ActionWrapper):
    """Expose TES direction and amplitude as separate continuous controls.

    The wrapped M2 fixed-fan environment still receives the old 4D reduced
    action ``[CT_Pump_DRL, CRAH_T_DRL, Chiller_T_DRL, TES_signed_target]``.
    This wrapper exposes a 5D agent action and maps only the last two
    dimensions into the signed TES target.  It does not read observations,
    price, SOC, or reward state.
    """

    def __init__(
        self,
        env: gym.Env,
        direction_deadband: float = 0.15,
        tes_action_idx: int = 3,
        action_semantics: str = "direction_amp",
        hold_steps: int = 1,
    ):
        super().__init__(env)
        if action_semantics not in {"direction_amp", "direction_amp_hold"}:
            raise ValueError(
                "TESDirectionAmplitudeActionWrapper action_semantics must be "
                "'direction_amp' or 'direction_amp_hold'"
            )
        if hold_steps < 1:
            raise ValueError("hold_steps must be >= 1")
        if not isinstance(env.action_space, gym.spaces.Box):
            raise TypeError(
                "TESDirectionAmplitudeActionWrapper requires a Box action_space, "
                f"got {type(env.action_space).__name__}"
            )
        inner_dim = int(env.action_space.shape[0])
        if inner_dim != 4:
            raise ValueError(
                "TESDirectionAmplitudeActionWrapper expects the fixed-fan "
                f"4D M2 action space, got {env.action_space.shape}"
            )
        self.inner_action_dim = inner_dim
        self.outer_action_dim = 5
        self.tes_action_idx = int(tes_action_idx)
        if self.tes_action_idx != inner_dim - 1:
            raise ValueError(
                f"Expected TES signed target at last inner action index {inner_dim - 1}, "
                f"got {self.tes_action_idx}"
            )
        self.direction_deadband = float(direction_deadband)
        self.action_semantics = action_semantics
        self.hold_steps = int(hold_steps) if action_semantics == "direction_amp_hold" else 1
        self._held_direction_mode = "idle"
        self._held_amplitude_mapped = 0.0
        self._option_hold_counter_remaining = 0
        self._option_accepted_new_mode = False

        inner_low = np.asarray(env.action_space.low, dtype=np.float32)
        inner_high = np.asarray(env.action_space.high, dtype=np.float32)
        low = np.asarray(
            [inner_low[0], inner_low[1], inner_low[2], -1.0, -1.0],
            dtype=np.float32,
        )
        high = np.asarray(
            [inner_high[0], inner_high[1], inner_high[2], 1.0, 1.0],
            dtype=np.float32,
        )
        self.action_space = gym.spaces.Box(low=low, high=high, dtype=np.float32)

        inner_names = list(self.env.get_wrapper_attr("action_variables"))
        if len(inner_names) != inner_dim:
            raise ValueError(
                f"action_variables length {len(inner_names)} does not match "
                f"inner action dim {inner_dim}: {inner_names}"
            )
        self.inner_action_variables = inner_names
        self.action_variables = (
            inner_names[: self.tes_action_idx]
            + ["TES_direction_DRL", "TES_amplitude_DRL"]
        )
        self.last_agent_action: Optional[np.ndarray] = None
        self.last_inner_action: Optional[np.ndarray] = None
        self.last_signed_target: float = 0.0
        self.last_direction_mode: str = "idle"
        self.last_amplitude_mapped: float = 0.0

    def _map_tes(self, direction_raw: float, amplitude_raw: float) -> tuple[float, float, str]:
        amplitude = float(np.clip((amplitude_raw + 1.0) / 2.0, 0.0, 1.0))
        mode = _tes_direction_mode(direction_raw, self.direction_deadband)
        if mode == "discharge":
            signed_target = amplitude
        elif mode == "charge":
            signed_target = -amplitude
        else:
            signed_target = 0.0
        return float(signed_target), amplitude, mode

    @staticmethod
    def _signed_target_from_mode_amp(mode: str, amplitude: float) -> float:
        amplitude = float(np.clip(amplitude, 0.0, 1.0))
        if mode == "discharge":
            return amplitude
        if mode == "charge":
            return -amplitude
        return 0.0

    def _reset_hold_state(self) -> None:
        self._held_direction_mode = "idle"
        self._held_amplitude_mapped = 0.0
        self._option_hold_counter_remaining = 0
        self._option_accepted_new_mode = False

    def action(self, action: np.ndarray) -> np.ndarray:
        agent_action = np.asarray(action, dtype=np.float32)
        if agent_action.shape != (self.outer_action_dim,):
            raise ValueError(
                f"Expected direction/amplitude action shape {(self.outer_action_dim,)}, "
                f"got {agent_action.shape}"
            )
        agent_action = np.clip(
            agent_action,
            np.asarray(self.action_space.low, dtype=np.float32),
            np.asarray(self.action_space.high, dtype=np.float32),
        ).astype(np.float32)

        direction_raw = float(agent_action[3])
        amplitude_raw = float(agent_action[4])
        signed_target, amplitude, mode = self._map_tes(direction_raw, amplitude_raw)

        if self.action_semantics == "direction_amp_hold":
            if self._option_hold_counter_remaining <= 0:
                self._held_direction_mode = mode
                self._held_amplitude_mapped = amplitude
                self._option_hold_counter_remaining = max(self.hold_steps - 1, 0)
                self._option_accepted_new_mode = True
            else:
                self._option_hold_counter_remaining -= 1
                self._option_accepted_new_mode = False
            signed_target = self._signed_target_from_mode_amp(
                self._held_direction_mode,
                self._held_amplitude_mapped,
            )
        else:
            self._held_direction_mode = mode
            self._held_amplitude_mapped = amplitude
            self._option_hold_counter_remaining = 0
            self._option_accepted_new_mode = True

        inner_action = np.empty(self.inner_action_dim, dtype=np.float32)
        inner_action[: self.tes_action_idx] = agent_action[: self.tes_action_idx]
        inner_action[self.tes_action_idx] = np.float32(signed_target)
        inner_action = np.clip(
            inner_action,
            np.asarray(self.env.action_space.low, dtype=np.float32),
            np.asarray(self.env.action_space.high, dtype=np.float32),
        ).astype(np.float32)

        self.last_agent_action = agent_action.copy()
        self.last_inner_action = inner_action.copy()
        self.last_signed_target = float(inner_action[self.tes_action_idx])
        self.last_direction_mode = mode
        self.last_amplitude_mapped = amplitude
        return inner_action

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        agent_action = np.asarray(action, dtype=np.float32)
        inner_action = self.action(agent_action)
        obs, reward, terminated, truncated, info = self.env.step(inner_action)

        direction_raw = float(self.last_agent_action[3]) if self.last_agent_action is not None else None
        amplitude_raw = float(self.last_agent_action[4]) if self.last_agent_action is not None else None
        info["tes_direction_raw"] = direction_raw
        info["tes_amplitude_raw"] = amplitude_raw
        info["tes_amplitude_mapped"] = self.last_amplitude_mapped
        info["tes_direction_mode"] = self.last_direction_mode
        info["tes_action_semantics"] = self.action_semantics
        info["tes_direction_deadband"] = self.direction_deadband
        info["tes_signed_target_from_semantics"] = self.last_signed_target
        info["tes_option_hold_steps"] = self.hold_steps
        info["tes_option_hold_counter_remaining"] = self._option_hold_counter_remaining
        info["tes_option_accepted_new_mode"] = self._option_accepted_new_mode
        info["tes_held_direction_mode"] = self._held_direction_mode
        info["tes_held_amplitude_mapped"] = self._held_amplitude_mapped
        info["action_dim"] = self.outer_action_dim
        info["agent_action"] = self.last_agent_action.copy()
        info["semantics_inner_action"] = self.last_inner_action.copy()
        mapping = dict(info.get("action_mapping", {}))
        mapping.update(
            {
                "tes_action_semantics": self.action_semantics,
                "direction_deadband": self.direction_deadband,
                "option_hold_steps": self.hold_steps,
                "outer_action_variables": self.action_variables,
                "inner_action_variables": self.inner_action_variables,
            }
        )
        info["action_mapping"] = mapping
        info["action"] = self.last_agent_action.copy()
        return obs, reward, terminated, truncated, info

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict]:
        obs, info = self.env.reset(seed=seed, options=options)
        self.last_agent_action = None
        self.last_inner_action = None
        self.last_signed_target = 0.0
        self.last_direction_mode = "idle"
        self.last_amplitude_mapped = 0.0
        self._reset_hold_state()
        info["tes_action_semantics"] = self.action_semantics
        info["tes_direction_deadband"] = self.direction_deadband
        info["tes_direction_raw"] = None
        info["tes_amplitude_raw"] = None
        info["tes_amplitude_mapped"] = 0.0
        info["tes_direction_mode"] = "idle"
        info["tes_signed_target_from_semantics"] = 0.0
        info["tes_option_hold_steps"] = self.hold_steps
        info["tes_option_hold_counter_remaining"] = self._option_hold_counter_remaining
        info["tes_option_accepted_new_mode"] = self._option_accepted_new_mode
        info["tes_held_direction_mode"] = self._held_direction_mode
        info["tes_held_amplitude_mapped"] = self._held_amplitude_mapped
        info["action_dim"] = self.outer_action_dim
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
        info.setdefault("tes_action_semantics", "signed_scalar")
        info.setdefault("tes_direction_deadband", None)
        info.setdefault("tes_direction_raw", None)
        info.setdefault("tes_amplitude_raw", None)
        info.setdefault("tes_amplitude_mapped", None)
        info.setdefault("tes_direction_mode", "idle")
        info.setdefault("tes_signed_target_from_semantics", 0.0)
        info.setdefault("tes_option_hold_steps", None)
        info.setdefault("tes_option_hold_counter_remaining", None)
        info.setdefault("tes_option_accepted_new_mode", None)
        info.setdefault("tes_held_direction_mode", None)
        info.setdefault("tes_held_amplitude_mapped", None)
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
        info.setdefault("tes_action_semantics", "signed_scalar")
        info.setdefault("tes_direction_deadband", None)
        info.setdefault("tes_direction_raw", None)
        info.setdefault("tes_amplitude_raw", None)
        info.setdefault("tes_amplitude_mapped", None)
        info.setdefault("tes_direction_mode", _tes_direction_mode(raw_target, 0.05))
        info.setdefault("tes_signed_target_from_semantics", raw_target)
        info.setdefault("tes_option_hold_steps", None)
        info.setdefault("tes_option_hold_counter_remaining", None)
        info.setdefault("tes_option_accepted_new_mode", None)
        info.setdefault("tes_held_direction_mode", None)
        info.setdefault("tes_held_amplitude_mapped", None)
        return obs, reward, terminated, truncated, info

    @property
    def observation_variables(self):
        base = self.env.get_wrapper_attr("observation_variables")
        return list(base) + ["TES_valve_wrapper_position"]


class TESStateAugmentationWrapper(gym.Wrapper):
    """Append short-horizon TES state features for optional C2b experiments.

    The wrapper is observation-only: it does not change rewards, EnergyPlus
    state, or the action space.  The appended features expose the last-step SOC
    response and how long the current price/time TOU phase has persisted.
    """

    def __init__(
        self,
        env: gym.Env,
        high_price_threshold: float = 0.75,
        low_price_threshold: float = -0.50,
        near_peak_threshold: float = 0.40,
        max_window_steps: int = 96,
    ):
        super().__init__(env)
        self.high_price_threshold = float(high_price_threshold)
        self.low_price_threshold = float(low_price_threshold)
        self.near_peak_threshold = float(near_peak_threshold)
        self.max_window_steps = max(1, int(max_window_steps))

        names = list(self.env.get_wrapper_attr("observation_variables"))
        required = ["TES_SOC", "price_current_norm", "price_hours_to_next_peak_norm"]
        missing = [name for name in required if name not in names]
        if missing:
            raise ValueError(f"TESStateAugmentationWrapper missing observation columns: {missing}")
        self._idx_soc = names.index("TES_SOC")
        self._idx_price = names.index("price_current_norm")
        self._idx_hours_to_peak = names.index("price_hours_to_next_peak_norm")

        low = np.append(self.env.observation_space.low, [-1.0, 0.0])
        high = np.append(self.env.observation_space.high, [1.0, 1.0])
        self.observation_space = gym.spaces.Box(
            low=low.astype(np.float32),
            high=high.astype(np.float32),
            dtype=np.float32,
        )
        self._last_soc: Optional[float] = None
        self._last_phase: Optional[str] = None
        self._window_step_count = 0

    def _signals(self, obs: np.ndarray) -> tuple[float | None, float | None, float | None]:
        def finite_at(index: int) -> float | None:
            try:
                value = float(obs[index])
            except (IndexError, TypeError, ValueError):
                return None
            return value if np.isfinite(value) else None

        return (
            finite_at(self._idx_soc),
            finite_at(self._idx_price),
            finite_at(self._idx_hours_to_peak),
        )

    def _phase(self, price: float | None, hours_to_peak_norm: float | None) -> str:
        if price is None:
            return "neutral"
        if price >= self.high_price_threshold:
            return "discharge_window"
        if (
            hours_to_peak_norm is not None
            and price <= self.low_price_threshold
            and hours_to_peak_norm <= self.near_peak_threshold
        ):
            return "charge_window"
        return "neutral"

    def _time_norm(self) -> float:
        return float(min(self._window_step_count, self.max_window_steps) / self.max_window_steps)

    def _append(self, obs: np.ndarray, delta_soc: float) -> np.ndarray:
        return np.append(
            np.asarray(obs, dtype=np.float32),
            np.asarray([delta_soc, self._time_norm()], dtype=np.float32),
        )

    def _update_info(self, info: Dict, delta_soc: float, phase: str) -> None:
        info["delta_soc_1step"] = float(delta_soc)
        info["time_in_tou_window_norm"] = self._time_norm()
        info["tes_tou_phase_for_state"] = phase
        info["enable_tes_state_augmentation"] = True

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[np.ndarray, Dict]:
        obs, info = self.env.reset(seed=seed, options=options)
        soc, price, hours_to_peak = self._signals(obs)
        phase = self._phase(price, hours_to_peak)
        self._last_soc = soc
        self._last_phase = phase
        self._window_step_count = 0
        delta_soc = 0.0
        self._update_info(info, delta_soc, phase)
        return self._append(obs, delta_soc), info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        obs, reward, terminated, truncated, info = self.env.step(action)
        soc, price, hours_to_peak = self._signals(obs)
        phase = self._phase(price, hours_to_peak)
        if self._last_phase is None or phase != self._last_phase:
            self._window_step_count = 0
        else:
            self._window_step_count += 1

        if soc is None or self._last_soc is None:
            delta_soc = 0.0
        else:
            delta_soc = float(np.clip(soc - self._last_soc, -1.0, 1.0))

        self._last_soc = soc
        self._last_phase = phase
        self._update_info(info, delta_soc, phase)
        return self._append(obs, delta_soc), reward, terminated, truncated, info

    @property
    def observation_variables(self):
        base = self.env.get_wrapper_attr("observation_variables")
        return list(base) + ["delta_soc_1step", "time_in_tou_window_norm"]


class TESPriceShapingWrapper(gym.Wrapper):
    """TOU-aware TES reward shaping used by M2-F1 training.

    Adds target-SOC PBRS, optional short-lived teacher/alignment direction
    terms, and a small valve regularizer.  It does not change observations or
    actions.

    The teacher term is disabled by default because it is not policy-invariant
    PBRS.  Enable it explicitly for curriculum experiments only.

    The TOU alignment term is also disabled by default and is not PBRS: it is
    an action-dependent auxiliary training signal for experiments that need
    explicit low-price charge / high-price discharge guidance.
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
        neutral_pbrs_mode: str = "target",
        soc_charge_limit: float = 0.85,
        soc_discharge_limit: float = 0.20,
        invalid_action_penalty_weight: float = 0.0,
        tou_alignment_weight: float = 0.0,
    ):
        super().__init__(env)
        if neutral_pbrs_mode not in ("target", "zero"):
            raise ValueError(
                "neutral_pbrs_mode must be 'target' or 'zero', "
                f"got {neutral_pbrs_mode!r}"
            )
        self.gamma = float(gamma)
        self.kappa = float(kappa)
        self.teacher_initial_weight = float(teacher_initial_weight)
        self.teacher_decay_episodes = max(float(teacher_decay_episodes), 1.0)
        self.valve_penalty_weight = float(valve_penalty_weight)
        self.invalid_action_penalty_weight = float(invalid_action_penalty_weight)
        self.tou_alignment_weight = float(tou_alignment_weight)
        self.high_price_threshold = float(high_price_threshold)
        self.low_price_threshold = float(low_price_threshold)
        self.near_peak_threshold = float(near_peak_threshold)
        self.target_soc_high = float(target_soc_high)
        self.target_soc_low = float(target_soc_low)
        self.target_soc_neutral = float(target_soc_neutral)
        self.neutral_pbrs_mode = neutral_pbrs_mode
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
        self._last_price: Optional[float] = None
        self._last_hours_to_peak: Optional[float] = None

    def _target_soc(self, price: float, hours_to_peak_norm: float) -> float:
        if price >= self.high_price_threshold:
            return self.target_soc_low
        if price <= self.low_price_threshold and hours_to_peak_norm <= self.near_peak_threshold:
            return self.target_soc_high
        return self.target_soc_neutral

    def _phi(self, soc: float, target_soc: float) -> float:
        return -self.kappa * (soc - target_soc) ** 2

    def _pbrs_phase(self, price: float, hours_to_peak_norm: float) -> str:
        if price >= self.high_price_threshold:
            return "high_price_discharge"
        if price <= self.low_price_threshold and hours_to_peak_norm <= self.near_peak_threshold:
            return "low_price_charge"
        return "neutral_target" if self.neutral_pbrs_mode == "target" else "neutral_zero"

    def _pbrs_active(self, phase: str) -> bool:
        return phase != "neutral_zero"

    def _pbrs_potential(self, soc: float, target_soc: float, phase: str) -> float:
        if not self._pbrs_active(phase):
            return 0.0
        return self._phi(soc, target_soc)

    def _pbrs_context(self, soc: float, price: float, hours_to_peak_norm: float) -> tuple[float, str, bool, float]:
        phase = self._pbrs_phase(price, hours_to_peak_norm)
        target = self._target_soc(price, hours_to_peak_norm)
        active = self._pbrs_active(phase)
        phi = self._pbrs_potential(soc, target, phase)
        return target, phase, active, phi

    def _teacher_weight(self) -> float:
        frac = max(0.0, 1.0 - self._episode_index / self.teacher_decay_episodes)
        return self.teacher_initial_weight * frac

    def _desired_sign(self, soc: float, price: float, hours_to_peak_norm: float) -> float:
        if price >= self.high_price_threshold and soc > self.soc_discharge_limit:
            return 1.0
        if (
            price <= self.low_price_threshold
            and hours_to_peak_norm <= self.near_peak_threshold
            and soc < self.soc_charge_limit
        ):
            return -1.0
        return 0.0

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
        target, phase, active, phi = self._pbrs_context(soc, price, hours_to_peak)
        self._prev_phi = phi
        self._last_soc = soc
        self._last_price = price
        self._last_hours_to_peak = hours_to_peak
        info["tes_soc_target"] = target
        info["tes_pbrs_phase"] = phase
        info["tes_pbrs_active"] = active
        info["tes_phi_value"] = phi
        info["tes_neutral_pbrs_mode"] = self.neutral_pbrs_mode
        info["tes_pbrs_term"] = 0.0
        info["tes_teacher_term"] = 0.0
        info["tes_teacher_weight"] = self._teacher_weight()
        info["tes_tou_alignment_term"] = 0.0
        info["tes_tou_desired_sign"] = self._desired_sign(soc, price, hours_to_peak)
        info["tes_tou_alignment_weight"] = self.tou_alignment_weight
        info["tes_valve_penalty"] = 0.0
        info["tes_invalid_action_penalty"] = 0.0
        info["tes_shaping_total"] = 0.0
        return obs, info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        obs, reward, terminated, truncated, info = self.env.step(action)
        prev_soc = self._last_soc
        prev_price = self._last_price
        prev_hours_to_peak = self._last_hours_to_peak
        soc, valve, price, hours_to_peak = self._signals(obs)
        self._last_soc = soc
        self._last_price = price
        self._last_hours_to_peak = hours_to_peak
        target, phase, active, phi = self._pbrs_context(soc, price, hours_to_peak)

        pbrs = self.gamma * phi - self._prev_phi if active else 0.0
        self._prev_phi = phi

        desired = self._desired_sign(soc, price, hours_to_peak)

        teacher_weight = self._teacher_weight()
        teacher = teacher_weight * desired * valve
        valve_penalty = -self.valve_penalty_weight * valve * valve
        raw_target = self._raw_valve_target(action, info)
        invalid_action_penalty = self._invalid_action_penalty(prev_soc, raw_target)
        tou_soc = prev_soc if prev_soc is not None else soc
        tou_price = prev_price if prev_price is not None else price
        tou_hours_to_peak = (
            prev_hours_to_peak if prev_hours_to_peak is not None else hours_to_peak
        )
        tou_desired = self._desired_sign(tou_soc, tou_price, tou_hours_to_peak)
        tou_alignment = self.tou_alignment_weight * tou_desired * raw_target
        shaping_total = (
            pbrs
            + teacher
            + valve_penalty
            + invalid_action_penalty
            + tou_alignment
        )
        reward = float(reward + shaping_total)

        info["reward"] = reward
        info["tes_soc_target"] = target
        info["tes_pbrs_phase"] = phase
        info["tes_pbrs_active"] = active
        info["tes_phi_value"] = phi
        info["tes_neutral_pbrs_mode"] = self.neutral_pbrs_mode
        info["tes_pbrs_term"] = pbrs
        info["tes_teacher_term"] = teacher
        info["tes_teacher_weight"] = teacher_weight
        info["tes_tou_alignment_term"] = tou_alignment
        info["tes_tou_desired_sign"] = tou_desired
        info["tes_tou_alignment_weight"] = self.tou_alignment_weight
        info["tes_valve_penalty"] = valve_penalty
        info["tes_invalid_action_penalty"] = invalid_action_penalty
        info["tes_shaping_total"] = shaping_total
        return obs, reward, terminated, truncated, info
