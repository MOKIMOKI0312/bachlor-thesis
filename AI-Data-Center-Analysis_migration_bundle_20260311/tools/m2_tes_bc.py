"""Training-only TES-head behavioral warm-start helpers for M2-F1.

This module intentionally does not implement reward shaping and does not alter
runtime evaluation.  It provides rule-derived TES labels and an actor-head loss
that supervises only TES action dimensions during training.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Mapping, Optional

import gymnasium as gym
import numpy as np
import torch as th
from torch.nn import functional as F


TES_BC_MODE_NONE = "none"
TES_BC_MODE_CHARGE = "charge"
TES_BC_MODE_IDLE = "idle"
TES_BC_MODE_DISCHARGE = "discharge"


@dataclass
class TESBCConfig:
    enabled: bool = False
    weight: float = 0.0
    decay_episodes: float = 2.0
    label_source: str = "rule_tou"
    window_only: bool = True
    amp_label: float = 1.0
    action_semantics: str = "signed_scalar"
    timesteps_per_episode: int = 35039
    obs_indices: Optional[Dict[str, int]] = None
    obs_mean: Optional[list[float]] = None
    obs_var: Optional[list[float]] = None
    obs_epsilon: float = 1e-8
    low_price_threshold: float = -0.50
    high_price_threshold: float = 0.75
    near_peak_threshold: float = 0.40
    soc_charge_limit: float = 0.85
    soc_discharge_limit: float = 0.20

    def to_json_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["enabled"] = bool(self.enabled and self.weight > 0.0)
        return data


def tes_bc_current_weight(config: TESBCConfig, num_timesteps: int) -> float:
    """Linear episode-based decay to exactly zero."""
    if not config.enabled or config.weight <= 0.0:
        return 0.0
    if config.decay_episodes <= 0.0:
        return 0.0
    steps_per_episode = max(int(config.timesteps_per_episode), 1)
    episode_progress = float(num_timesteps) / float(steps_per_episode)
    scale = max(0.0, 1.0 - episode_progress / float(config.decay_episodes))
    return float(config.weight) * scale


def _required_obs_indices(config: TESBCConfig) -> Dict[str, int]:
    indices = dict(config.obs_indices or {})
    required = ["TES_SOC", "price_current_norm", "price_hours_to_next_peak_norm"]
    missing = [name for name in required if name not in indices]
    if missing:
        raise ValueError(f"TES BC config missing observation indices: {missing}")
    return indices


def _unnormalize_obs(observations: th.Tensor, config: TESBCConfig) -> th.Tensor:
    if config.obs_mean is None or config.obs_var is None:
        return observations
    mean = th.as_tensor(config.obs_mean, dtype=observations.dtype, device=observations.device)
    var = th.as_tensor(config.obs_var, dtype=observations.dtype, device=observations.device)
    return observations * th.sqrt(var + float(config.obs_epsilon)) + mean


def rule_tou_label_tensors(
    observations: th.Tensor,
    config: TESBCConfig,
) -> Dict[str, th.Tensor]:
    """Build rule_tou labels from raw or unnormalized batch observations."""
    if config.label_source != "rule_tou":
        raise ValueError(f"Unsupported TES BC label_source={config.label_source!r}")
    indices = _required_obs_indices(config)
    raw_obs = _unnormalize_obs(observations, config)
    soc = raw_obs[:, indices["TES_SOC"]]
    price = raw_obs[:, indices["price_current_norm"]]
    hours_to_peak = raw_obs[:, indices["price_hours_to_next_peak_norm"]]

    charge_mask = (
        (price <= float(config.low_price_threshold))
        & (hours_to_peak <= float(config.near_peak_threshold))
        & (soc < float(config.soc_charge_limit))
    )
    discharge_mask = (
        (price >= float(config.high_price_threshold))
        & (soc > float(config.soc_discharge_limit))
    )
    active_mask = charge_mask | discharge_mask
    if not config.window_only:
        active_mask = th.ones_like(active_mask, dtype=th.bool)

    amp = float(np.clip(config.amp_label, 0.0, 1.0))
    amp_raw = float(np.clip(2.0 * amp - 1.0, -1.0, 1.0))

    signed_target = th.zeros_like(soc)
    signed_target = th.where(charge_mask, th.full_like(signed_target, -amp), signed_target)
    signed_target = th.where(discharge_mask, th.full_like(signed_target, amp), signed_target)

    direction_target = th.zeros_like(soc)
    direction_target = th.where(charge_mask, th.full_like(direction_target, -1.0), direction_target)
    direction_target = th.where(discharge_mask, th.full_like(direction_target, 1.0), direction_target)

    amplitude_raw_target = th.full_like(soc, -1.0)
    amplitude_raw_target = th.where(active_mask, th.full_like(amplitude_raw_target, amp_raw), amplitude_raw_target)

    mode_id = th.zeros_like(soc)
    mode_id = th.where(charge_mask, th.full_like(mode_id, -1.0), mode_id)
    mode_id = th.where(discharge_mask, th.full_like(mode_id, 1.0), mode_id)

    return {
        "active_mask": active_mask,
        "charge_mask": charge_mask,
        "discharge_mask": discharge_mask,
        "signed_target": signed_target,
        "direction_target": direction_target,
        "amplitude_raw_target": amplitude_raw_target,
        "mode_id": mode_id,
    }


def compute_tes_bc_loss(
    actions_pi: th.Tensor,
    observations: th.Tensor,
    config: TESBCConfig,
) -> tuple[th.Tensor, Dict[str, float]]:
    """TES-head-only loss. HVAC dimensions are never indexed."""
    zero = actions_pi.sum() * 0.0
    current_enabled = bool(config.enabled and config.weight > 0.0)
    if not current_enabled:
        return zero, {
            "tes_bc_loss": 0.0,
            "tes_bc_active_fraction": 0.0,
            "tes_bc_charge_fraction": 0.0,
            "tes_bc_discharge_fraction": 0.0,
            "tes_bc_batch_size": float(actions_pi.shape[0]),
        }

    labels = rule_tou_label_tensors(observations, config)
    mask = labels["active_mask"]
    batch_size = int(actions_pi.shape[0])
    active_count = int(mask.detach().sum().item())
    if active_count <= 0:
        return zero, {
            "tes_bc_loss": 0.0,
            "tes_bc_active_fraction": 0.0,
            "tes_bc_charge_fraction": float(labels["charge_mask"].float().mean().item()),
            "tes_bc_discharge_fraction": float(labels["discharge_mask"].float().mean().item()),
            "tes_bc_batch_size": float(batch_size),
        }

    if config.action_semantics == "signed_scalar":
        if actions_pi.shape[1] < 4:
            raise ValueError("signed_scalar TES BC requires action_dim >= 4")
        loss = F.mse_loss(actions_pi[:, 3][mask], labels["signed_target"][mask])
    elif config.action_semantics in {"direction_amp", "direction_amp_hold"}:
        if actions_pi.shape[1] < 5:
            raise ValueError(f"{config.action_semantics} TES BC requires action_dim >= 5")
        direction_loss = F.mse_loss(actions_pi[:, 3][mask], labels["direction_target"][mask])
        amplitude_loss = F.mse_loss(actions_pi[:, 4][mask], labels["amplitude_raw_target"][mask])
        loss = direction_loss + amplitude_loss
    else:
        raise ValueError(f"Unsupported TES BC action_semantics={config.action_semantics!r}")

    return loss, {
        "tes_bc_loss": float(loss.detach().item()),
        "tes_bc_active_fraction": float(mask.float().mean().item()),
        "tes_bc_charge_fraction": float(labels["charge_mask"].float().mean().item()),
        "tes_bc_discharge_fraction": float(labels["discharge_mask"].float().mean().item()),
        "tes_bc_batch_size": float(batch_size),
    }


def rule_tou_label_np(obs: np.ndarray, config: TESBCConfig) -> Dict[str, Any]:
    """Single-step rule_tou label for training monitor metadata."""
    indices = _required_obs_indices(config)
    soc = float(obs[indices["TES_SOC"]])
    price = float(obs[indices["price_current_norm"]])
    hours_to_peak = float(obs[indices["price_hours_to_next_peak_norm"]])
    amp = float(np.clip(config.amp_label, 0.0, 1.0))
    amp_raw = float(np.clip(2.0 * amp - 1.0, -1.0, 1.0))

    charge = (
        price <= float(config.low_price_threshold)
        and hours_to_peak <= float(config.near_peak_threshold)
        and soc < float(config.soc_charge_limit)
    )
    discharge = price >= float(config.high_price_threshold) and soc > float(config.soc_discharge_limit)
    active = charge or discharge

    if charge:
        mode = TES_BC_MODE_CHARGE
        signed = -amp
        direction = -1.0
    elif discharge:
        mode = TES_BC_MODE_DISCHARGE
        signed = amp
        direction = 1.0
    elif config.window_only:
        mode = TES_BC_MODE_NONE
        signed = None
        direction = None
        amp_raw_out = None
        return {
            "active": False,
            "mode": mode,
            "signed_target": signed,
            "direction_target": direction,
            "amplitude_raw_target": amp_raw_out,
            "amp_label": None,
        }
    else:
        mode = TES_BC_MODE_IDLE
        signed = 0.0
        direction = 0.0
        active = True

    return {
        "active": bool(active),
        "mode": mode,
        "signed_target": signed,
        "direction_target": direction,
        "amplitude_raw_target": amp_raw if active else -1.0,
        "amp_label": amp if active else 0.0,
    }


class TESBCTrainingInfoWrapper(gym.Wrapper):
    """Add training-only BC provenance and labels to monitor info.

    The wrapper does not modify observations, actions, or rewards.  It is used
    only by the training launcher when TES BC is enabled.
    """

    def __init__(self, env: gym.Env, config: TESBCConfig):
        super().__init__(env)
        self.config = config
        self._global_steps = 0

    def reset(self, **kwargs):
        obs, info = self.env.reset(**kwargs)
        self._add_info(info, obs)
        return obs, info

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        self._global_steps += 1
        self._add_info(info, obs)
        return obs, reward, terminated, truncated, info

    def _add_info(self, info: Dict[str, Any], obs: np.ndarray) -> None:
        current_weight = tes_bc_current_weight(self.config, self._global_steps)
        label = rule_tou_label_np(np.asarray(obs, dtype=np.float32), self.config)
        # tes_bc_enabled reflects static configuration (was BC ever turned on
        # for this run?). tes_bc_active reflects whether BC is *applied at
        # this step* — false once the linear decay drives current_weight to 0
        # even though enabled / static weight are still nonzero. Downstream
        # monitor parsing should use tes_bc_active when asking "is BC
        # influencing the actor at step k?".
        info["tes_bc_enabled"] = bool(self.config.enabled and self.config.weight > 0.0)
        info["tes_bc_active"] = bool(current_weight > 0.0)
        info["tes_bc_weight"] = float(self.config.weight)
        info["tes_bc_current_weight"] = float(current_weight)
        info["tes_bc_decay_episodes"] = float(self.config.decay_episodes)
        info["tes_bc_label_source"] = self.config.label_source
        info["tes_bc_window_only"] = bool(self.config.window_only)
        info["tes_bc_amp_label"] = float(self.config.amp_label)
        info["tes_bc_loss"] = None
        info["tes_bc_label_active"] = bool(label["active"])
        info["tes_bc_mode_label"] = label["mode"]
        info["tes_bc_signed_target_label"] = label["signed_target"]
        info["tes_bc_direction_target_label"] = label["direction_target"]
        info["tes_bc_amplitude_raw_label"] = label["amplitude_raw_target"]


def tes_bc_status_from_model(model: Any) -> Dict[str, Any]:
    if hasattr(model, "get_tes_bc_status"):
        return dict(model.get_tes_bc_status())
    return {
        "tes_bc_enabled": False,
        "tes_bc_weight": 0.0,
        "tes_bc_current_weight": 0.0,
        "tes_bc_final_weight_zero": True,
    }
