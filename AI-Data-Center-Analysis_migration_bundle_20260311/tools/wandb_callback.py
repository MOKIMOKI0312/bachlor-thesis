"""
WandB Callback for SAC + Sinergym training.

记录以下指标到 wandb:
- 每 episode: cumulative_reward, mean_reward, energy_term, comfort_term, comfort_violation%, PUE
- 每 N 步: SAC 训练指标 (actor_loss, critic_loss, ent_coef)
- 系统信息: GPU 利用率, 显存

用法:
    在训练脚本中:
    from tools.wandb_callback import WandbCallback
    callbacks.append(WandbCallback(
        project="dc-cooling-optimization",
        name=f"E0-nanjing-seed{seed}",
        config={...},
    ))
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from stable_baselines3.common.callbacks import BaseCallback

try:
    import wandb
except ImportError:
    wandb = None


class WandbCallback(BaseCallback):
    """SB3 callback that logs training metrics to Weights & Biases."""

    def __init__(
        self,
        project: str = "dc-cooling-optimization",
        name: Optional[str] = None,
        group: Optional[str] = None,
        tags: Optional[list] = None,
        config: Optional[Dict[str, Any]] = None,
        log_interval: int = 1000,
        save_model_every_episodes: int = 50,
        verbose: int = 0,
    ):
        super().__init__(verbose)
        self.project = project
        self.run_name = name
        self.group = group
        self.tags = tags or []
        self.wandb_config = config or {}
        self.log_interval = log_interval
        self.save_model_every_episodes = save_model_every_episodes

        # Episode tracking
        self._episode_rewards = []
        self._episode_energy = []
        self._episode_comfort = []
        self._current_episode_reward = 0.0
        self._current_episode_energy = 0.0
        self._current_episode_comfort = 0.0
        self._current_episode_steps = 0
        self._episode_count = 0
        self._best_reward = -float("inf")

    def _init_callback(self) -> None:
        if wandb is None:
            raise ImportError("wandb is not installed. Run: pip install wandb")

        wandb.init(
            project=self.project,
            name=self.run_name,
            group=self.group,
            tags=self.tags,
            config={
                "algorithm": "SAC",
                "policy": "MlpPolicy",
                "total_timesteps": self.locals.get("total_timesteps", 0),
                **self.wandb_config,
            },
            reinit=True,
        )

        # Log model architecture
        if hasattr(self.model, "policy"):
            wandb.config.update({
                "net_arch": str(self.model.policy_kwargs.get("net_arch", "default")),
                "learning_rate": self.model.learning_rate,
                "batch_size": self.model.batch_size,
                "gamma": self.model.gamma,
                "buffer_size": self.model.buffer_size,
                "learning_starts": self.model.learning_starts,
                "observation_dim": self.model.observation_space.shape[0],
                "action_dim": self.model.action_space.shape[0],
            })

    def _on_step(self) -> bool:
        # Accumulate episode metrics from info
        infos = self.locals.get("infos", [])
        if infos:
            info = infos[0] if isinstance(infos, list) else infos
            reward = info.get("reward", 0)
            energy = info.get("energy_term", 0)
            comfort = info.get("comfort_term", 0)

            self._current_episode_reward += reward if reward else 0
            self._current_episode_energy += energy if energy else 0
            self._current_episode_comfort += comfort if comfort else 0
            self._current_episode_steps += 1

        # Check for episode end
        dones = self.locals.get("dones", [False])
        if any(dones) or any(self.locals.get("infos", [{}])[0].get(k, False) for k in ["TimeLimit.truncated"]):
            if self._current_episode_steps > 100:  # Skip very short episodes
                self._episode_count += 1
                ep_reward = self._current_episode_reward
                ep_energy = self._current_episode_energy
                ep_comfort = self._current_episode_comfort
                ep_steps = self._current_episode_steps

                # Calculate PUE approximation from reward terms
                # PUE = Electricity:Facility / ITE-CPU:Electricity
                # energy_term is already the PUE-based penalty

                log_dict = {
                    "episode/reward": ep_reward,
                    "episode/mean_reward": ep_reward / max(ep_steps, 1),
                    "episode/energy_term": ep_energy,
                    "episode/comfort_term": ep_comfort,
                    "episode/length": ep_steps,
                    "episode/number": self._episode_count,
                    "episode/total_timesteps": self.num_timesteps,
                }

                # Track best
                if ep_reward > self._best_reward:
                    self._best_reward = ep_reward
                    log_dict["episode/best_reward"] = self._best_reward
                    log_dict["episode/is_best"] = 1
                else:
                    log_dict["episode/is_best"] = 0

                wandb.log(log_dict, step=self.num_timesteps)

                # Reset
                self._current_episode_reward = 0.0
                self._current_episode_energy = 0.0
                self._current_episode_comfort = 0.0
                self._current_episode_steps = 0

        # Log SAC training metrics periodically
        if self.num_timesteps % self.log_interval == 0 and self.num_timesteps > 0:
            logger = self.model.logger
            if hasattr(logger, "name_to_value"):
                train_metrics = {}
                for key, value in logger.name_to_value.items():
                    if key.startswith("train/"):
                        train_metrics[key] = value
                if train_metrics:
                    train_metrics["global_step"] = self.num_timesteps
                    wandb.log(train_metrics, step=self.num_timesteps)

        return True

    def _on_training_end(self) -> None:
        if wandb.run is not None:
            # Log final summary
            wandb.summary["total_episodes"] = self._episode_count
            wandb.summary["total_timesteps"] = self.num_timesteps
            wandb.summary["best_reward"] = self._best_reward

            # Save final model as artifact
            model_path = Path(self.model.logger.dir) / "final_model.zip" if hasattr(self.model.logger, "dir") else None
            if model_path:
                self.model.save(str(model_path))
                artifact = wandb.Artifact(
                    name=f"model-{wandb.run.id}",
                    type="model",
                    description=f"SAC final model, best_reward={self._best_reward:.1f}",
                )
                artifact.add_file(str(model_path))
                wandb.log_artifact(artifact)

            wandb.finish()
