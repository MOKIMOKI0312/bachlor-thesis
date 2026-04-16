"""
DSAC-T: Distributional Soft Actor-Critic with Three Refinements.

Strict implementation following arXiv:2310.05858.

Three refinements over standard SAC:
  R1 - Expected Value Substituting: use deterministic y_q instead of stochastic y_z
       for the mean-gradient term, reducing gradient noise.
  R2 - Twin Value Distribution Learning: two distributional critics, select the one
       with lower mean for target computation (anti-overestimation).
  R3 - Variance-Based Critic Gradient Adjustment: adaptive clipping boundary b and
       gradient scaling weight ω based on learned variance, stabilizing training.
"""

from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union

import numpy as np
import torch as th
from gymnasium import spaces
from torch.nn import functional as F

from stable_baselines3.common.buffers import ReplayBuffer
from stable_baselines3.common.noise import ActionNoise
from stable_baselines3.common.policies import BasePolicy
from stable_baselines3.common.type_aliases import GymEnv, MaybeCallback, Schedule
from stable_baselines3.common.utils import get_parameters_by_name, polyak_update
from stable_baselines3.sac.policies import Actor, MlpPolicy, SACPolicy
from stable_baselines3.sac.sac import SAC

from tools.distributional_critic import DistributionalCritic

SelfDSACT = TypeVar("SelfDSACT", bound="DSAC_T")


class DSAC_T(SAC):
    """
    DSAC-T: Distributional SAC with Three Refinements.

    Inherits from SB3 SAC and overrides:
      - _setup_model(): replace ContinuousCritic with DistributionalCritic
      - train(): implement distributional Bellman, Eq.26 gradient, b/ω EMA updates

    Additional parameters (vs SAC):
      :param xi: clipping coefficient (ξ), default 3 (three-sigma rule)
      :param eps_sigma: minimum sigma for numerical stability, default 0.1
      :param eps_omega: minimum omega for gradient scaling, default 0.1
    """

    def __init__(
        self,
        policy: Union[str, Type[SACPolicy]],
        env: Union[GymEnv, str],
        xi: float = 3.0,
        eps_sigma: float = 0.1,
        eps_omega: float = 0.1,
        **kwargs,
    ):
        self.xi = xi
        self.eps_sigma = eps_sigma
        self.eps_omega = eps_omega

        # DSAC-T specific state (initialized in _setup_model)
        self._b: Optional[List[float]] = None  # clipping boundaries per critic
        self._omega: Optional[List[float]] = None  # gradient scaling weights per critic

        super().__init__(policy, env, **kwargs)

    def _setup_model(self) -> None:
        """Setup model with DistributionalCritic instead of ContinuousCritic."""
        super()._setup_model()

        # Replace critic and critic_target with DistributionalCritic.
        # Use _update_features_extractor to add features_extractor and features_dim
        # (same way SACPolicy.make_critic does it).
        if self.policy.share_features_extractor:
            features_extractor = self.actor.features_extractor
        else:
            features_extractor = None

        critic_kwargs = self.policy._update_features_extractor(
            self.policy.critic_kwargs, features_extractor
        )

        self.critic = DistributionalCritic(**critic_kwargs).to(self.device)
        self.critic_target = DistributionalCritic(**critic_kwargs).to(self.device)
        self.critic_target.load_state_dict(self.critic.state_dict())
        self.critic_target.set_training_mode(False)

        # Update optimizer for new critic
        self.critic.optimizer = self.policy.optimizer_class(
            self.critic.parameters(),
            lr=self.lr_schedule(1),
            **self.policy.optimizer_kwargs,
        )

        # Update aliases
        self.policy.critic = self.critic
        self.policy.critic_target = self.critic_target

        # Batch norm stats
        self.batch_norm_stats = get_parameters_by_name(self.critic, ["running_"])
        self.batch_norm_stats_target = get_parameters_by_name(self.critic_target, ["running_"])

        # Initialize DSAC-T adaptive parameters
        n_critics = self.critic.n_critics
        self._b = [1.0] * n_critics  # initial clipping boundary
        self._omega = [1.0] * n_critics  # initial gradient scaling

    def train(self, gradient_steps: int, batch_size: int = 64) -> None:
        """
        DSAC-T training loop. Implements Algorithm 1 from arXiv:2310.05858.
        """
        self.policy.set_training_mode(True)

        optimizers = [self.actor.optimizer, self.critic.optimizer]
        if self.ent_coef_optimizer is not None:
            optimizers += [self.ent_coef_optimizer]
        self._update_learning_rate(optimizers)

        ent_coef_losses, ent_coefs = [], []
        actor_losses, critic_losses = [], []
        sigma_means = []

        for gradient_step in range(gradient_steps):
            replay_data = self.replay_buffer.sample(batch_size, env=self._vec_normalize_env)

            if self.use_sde:
                self.actor.reset_noise()

            # --- Entropy coefficient (same as SAC) ---
            actions_pi, log_prob = self.actor.action_log_prob(replay_data.observations)
            log_prob = log_prob.reshape(-1, 1)

            ent_coef_loss = None
            if self.ent_coef_optimizer is not None and self.log_ent_coef is not None:
                ent_coef = th.exp(self.log_ent_coef.detach())
                ent_coef_loss = -(self.log_ent_coef * (log_prob + self.target_entropy).detach()).mean()
                ent_coef_losses.append(ent_coef_loss.item())
            else:
                ent_coef = self.ent_coef_tensor

            ent_coefs.append(ent_coef.item())

            if ent_coef_loss is not None and self.ent_coef_optimizer is not None:
                self.ent_coef_optimizer.zero_grad()
                ent_coef_loss.backward()
                self.ent_coef_optimizer.step()

            # --- R1 + R2: Compute distributional target ---
            with th.no_grad():
                # Sample next actions from TARGET actor (paper uses φ̄)
                next_actions, next_log_prob = self.actor.action_log_prob(replay_data.next_observations)
                next_log_prob = next_log_prob.reshape(-1, 1)

                # Get (mean, sigma) from both target critics
                target_outputs = self.critic_target(replay_data.next_observations, next_actions)
                # target_outputs = ((Q1_mean, Q1_sigma), (Q2_mean, Q2_sigma))

                target_means = th.cat([out[0] for out in target_outputs], dim=1)  # (batch, n_critics)
                target_sigmas = th.cat([out[1] for out in target_outputs], dim=1)  # (batch, n_critics)

                # R2: select critic with lower mean (anti-overestimation)
                i_star = th.argmin(target_means, dim=1, keepdim=True)  # (batch, 1)

                # Gather selected mean and sigma
                selected_mean = th.gather(target_means, 1, i_star)  # (batch, 1)
                selected_sigma = th.gather(target_sigmas, 1, i_star)  # (batch, 1)

                # R1: deterministic target for mean gradient
                y_q_min = replay_data.rewards + (1 - replay_data.dones) * self.gamma * (
                    selected_mean - ent_coef * next_log_prob
                )

                # Stochastic target for variance gradient (sample from target distribution)
                z_sample = selected_mean + selected_sigma * th.randn_like(selected_sigma)
                y_z = replay_data.rewards + (1 - replay_data.dones) * self.gamma * (
                    z_sample - ent_coef * next_log_prob
                )

            # --- R3: Variance-based critic gradient (Eq. 26) ---
            current_outputs = self.critic(replay_data.observations, replay_data.actions)
            # current_outputs = ((Q1_mean, Q1_sigma), (Q2_mean, Q2_sigma))

            # Vectorized loss computation (avoid per-critic for loop)
            critic_losses_per_net = []
            with th.no_grad():
                batch_sigma_sum = 0.0
            for i, (q_mean, q_sigma) in enumerate(current_outputs):
                sigma_sq = q_sigma ** 2

                # Eq. 26, term 1: mean gradient (detach sigma to avoid gradient through it)
                mean_loss = ((y_q_min - q_mean) ** 2) / (sigma_sq.detach() + self.eps_sigma)

                # Eq. 26, term 2: variance gradient with clipping (detach q_mean)
                b_i = self._b[i]
                q_mean_d = q_mean.detach()
                y_z_clipped = th.clamp(y_z, q_mean_d - b_i, q_mean_d + b_i)
                var_target = (y_z_clipped - q_mean_d) ** 2
                var_loss = ((var_target - sigma_sq) ** 2) / (sigma_sq.detach() + self.eps_sigma)

                omega_i = self._omega[i]
                critic_losses_per_net.append((mean_loss + var_loss).mean() / (omega_i + self.eps_omega))

                # EMA updates (no grad)
                with th.no_grad():
                    s_mean = q_sigma.mean().item()
                    self._b[i] = self.tau * self.xi * s_mean + (1 - self.tau) * self._b[i]
                    self._omega[i] = self.tau * (q_sigma ** 2).mean().item() + (1 - self.tau) * self._omega[i]
                    batch_sigma_sum += s_mean

            total_critic_loss = critic_losses_per_net[0] + critic_losses_per_net[1]
            critic_losses.append(total_critic_loss.item())
            sigma_means.append(batch_sigma_sum / len(current_outputs))

            # Optimize critic
            self.critic.optimizer.zero_grad()
            total_critic_loss.backward()
            self.critic.optimizer.step()

            # --- Actor loss ---
            # Recompute actions_pi to decouple from critic's computation graph
            actions_pi2, log_prob2 = self.actor.action_log_prob(replay_data.observations)
            log_prob2 = log_prob2.reshape(-1, 1)
            current_outputs_pi = self.critic(replay_data.observations, actions_pi2)
            q_means_pi = th.cat([out[0] for out in current_outputs_pi], dim=1)
            min_q_pi, _ = th.min(q_means_pi, dim=1, keepdim=True)
            actor_loss = (ent_coef * log_prob2 - min_q_pi).mean()
            actor_losses.append(actor_loss.item())

            # Optimize actor
            self.actor.optimizer.zero_grad()
            actor_loss.backward()
            self.actor.optimizer.step()

            # Soft update target networks
            if gradient_step % self.target_update_interval == 0:
                polyak_update(self.critic.parameters(), self.critic_target.parameters(), self.tau)
                polyak_update(self.batch_norm_stats, self.batch_norm_stats_target, 1.0)

        self._n_updates += gradient_steps

        # Logging
        self.logger.record("train/n_updates", self._n_updates, exclude="tensorboard")
        self.logger.record("train/ent_coef", np.mean(ent_coefs))
        self.logger.record("train/actor_loss", np.mean(actor_losses))
        self.logger.record("train/critic_loss", np.mean(critic_losses))
        self.logger.record("train/sigma_mean", np.mean(sigma_means))
        self.logger.record("train/clip_b", np.mean(self._b))
        self.logger.record("train/omega", np.mean(self._omega))
        if len(ent_coef_losses) > 0:
            self.logger.record("train/ent_coef_loss", np.mean(ent_coef_losses))
