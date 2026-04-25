"""
Distributional Critic for DSAC-T.

Each Q-network outputs (mean, std) instead of a single Q-value.
The return distribution is modeled as Z_θ(·|s,a) = N(Q_θ(s,a), σ_θ(s,a)²).

Reference: arXiv:2310.05858, Section 3.
"""

from typing import List, Optional, Tuple, Type

import torch as th
import torch.nn as nn
from gymnasium import spaces

from stable_baselines3.common.policies import ContinuousCritic
from stable_baselines3.common.preprocessing import get_action_dim
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor, create_mlp


class DistributionalCritic(ContinuousCritic):
    """
    Twin distributional critic for DSAC-T.

    Each Q-network outputs 2 values: mean Q_θ(s,a) and raw_sigma.
    σ_θ(s,a) = softplus(raw_sigma) + ε to ensure positivity.
    """

    def __init__(
        self,
        observation_space: spaces.Space,
        action_space: spaces.Box,
        net_arch: List[int],
        features_extractor: BaseFeaturesExtractor,
        features_dim: int,
        activation_fn: Type[nn.Module] = nn.ReLU,
        normalize_images: bool = True,
        n_critics: int = 2,
        share_features_extractor: bool = True,
        sigma_min: float = 1e-4,
        sigma_max: Optional[float] = None,
    ):
        # Skip ContinuousCritic.__init__ and call BaseModel.__init__ directly,
        # because we need output_dim=2 instead of 1.
        nn.Module.__init__(self)  # BaseModel -> nn.Module
        # Manually set required attributes from BaseModel
        self.observation_space = observation_space
        self.action_space = action_space
        self.features_extractor = features_extractor
        self.normalize_images = normalize_images
        self.share_features_extractor = share_features_extractor
        self.n_critics = n_critics
        self.sigma_min = sigma_min
        self.sigma_max = sigma_max  # VERIFY-FIX-1: if set, clamp σ to prevent runaway growth

        action_dim = get_action_dim(self.action_space)

        # Build Q-networks with output_dim=2 (mean, raw_sigma)
        self.q_networks: List[nn.Module] = []
        for idx in range(n_critics):
            q_net_list = create_mlp(features_dim + action_dim, 2, net_arch, activation_fn)
            q_net = nn.Sequential(*q_net_list)
            self.add_module(f"qf{idx}", q_net)
            self.q_networks.append(q_net)

    def forward(
        self, obs: th.Tensor, actions: th.Tensor
    ) -> Tuple[Tuple[th.Tensor, th.Tensor], ...]:
        """
        Forward pass. Returns tuple of (mean, sigma) pairs, one per critic.

        Returns:
            ((Q1_mean, Q1_sigma), (Q2_mean, Q2_sigma))
            Each mean/sigma has shape (batch_size, 1).
        """
        with th.set_grad_enabled(not self.share_features_extractor):
            features = self.extract_features(obs, self.features_extractor)
        qvalue_input = th.cat([features, actions], dim=1)

        results = []
        for q_net in self.q_networks:
            output = q_net(qvalue_input)  # (batch, 2)
            mean = output[:, 0:1]  # (batch, 1)
            raw_sigma = output[:, 1:2]  # (batch, 1)
            sigma = nn.functional.softplus(raw_sigma) + self.sigma_min  # ensure > 0
            # VERIFY-FIX-1: clamp σ to prevent runaway growth; keeps gradients
            # flowing below sigma_max but saturates at the upper bound.
            if self.sigma_max is not None:
                sigma = th.clamp(sigma, min=self.sigma_min, max=self.sigma_max)
            results.append((mean, sigma))

        return tuple(results)

    def get_means(self, obs: th.Tensor, actions: th.Tensor) -> Tuple[th.Tensor, ...]:
        """Return only the mean Q-values (for actor loss, compatible with SAC interface)."""
        dist_outputs = self.forward(obs, actions)
        return tuple(ms[0] for ms in dist_outputs)
