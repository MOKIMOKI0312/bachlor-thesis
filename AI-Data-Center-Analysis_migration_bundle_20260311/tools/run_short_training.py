import argparse
import json
import random
import time
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gymnasium as gym
import numpy as np
from stable_baselines3 import SAC
from stable_baselines3.common.callbacks import CallbackList, CheckpointCallback
import torch

from sinergym.utils.common import get_ids
from sinergym.utils.training_monitor import StatusCallback, make_probe_logger_factory
from sinergym.utils.wrappers import LoggerWrapper, NormalizeObservation


def set_global_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--episodes', type=int, default=2)
    parser.add_argument('--timesteps', type=int)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--device', default='auto')
    parser.add_argument('--model-name', default='codex_short_train_model')
    parser.add_argument('--checkpoint-episodes', type=int, default=10)
    parser.add_argument('--status-file')
    parser.add_argument('--status-every-steps', type=int, default=500)
    parser.add_argument('--probe-step-sample-interval', type=int, default=12)
    parser.add_argument('--probe-recent-window', type=int, default=192)
    parser.add_argument('--algo', default='dsac_t', choices=['sac', 'dsac_t'], help='Algorithm (default: dsac_t)')
    parser.add_argument('--resume', type=str, default=None, help='Path to checkpoint .zip to resume from')
    parser.add_argument('--wandb', action='store_true', help='Enable Weights & Biases logging')
    parser.add_argument('--wandb-project', default='dc-cooling-optimization')
    parser.add_argument('--wandb-group', default=None, help='W&B group name (e.g. E0-nanjing)')
    args = parser.parse_args()

    if 'Eplus-DC-Cooling' not in get_ids():
        raise RuntimeError('Eplus-DC-Cooling is not registered')

    set_global_seed(args.seed)

    environment = 'Eplus-DC-Cooling'
    building_file = ['DRL_DC_training.epJSON']
    weather_files = [
        'CHN_JS_Nanjing.582380_TMYx.2009-2023.epw',
    ]
    config_params = {'runperiod': (1, 1, 2025, 31, 12, 2025), 'timesteps_per_hour': 1}
    experiment_date = datetime.today().strftime('%Y-%m-%d_%H-%M-%S')
    experiment_name = experiment_date + f'_codex_train_{args.episodes}ep_SAC_DC_Cooling'

    env = gym.make(environment, env_name=experiment_name, building_file=building_file, weather_files=weather_files, config_params=config_params)
    env.action_space.seed(args.seed)
    env = NormalizeObservation(env)
    env = LoggerWrapper(
        env,
        logger_class=make_probe_logger_factory(
            observation_variables=env.get_wrapper_attr('observation_variables'),
            action_variables=env.get_wrapper_attr('action_variables'),
            step_sample_interval=args.probe_step_sample_interval,
            recent_step_window=args.probe_recent_window,
        ),
        monitor_header=['timestep'] + env.get_wrapper_attr('observation_variables') + env.get_wrapper_attr('action_variables') + ['time (hours)', 'reward', 'energy_term', 'ITE_term', 'comfort_term', 'terminated', 'truncated'],
    )

    policy_kwargs = dict(net_arch=[512])
    if args.algo == 'dsac_t':
        from tools.dsac_t import DSAC_T
        AlgoClass = DSAC_T
    else:
        AlgoClass = SAC

    if args.resume:
        # Resume from checkpoint
        print(f'Resuming from: {args.resume}')
        model = AlgoClass.load(
            args.resume,
            env=env,
            device=args.device,
        )
        # Restore replay buffer if exists
        replay_path = args.resume.replace('.zip', '_replay_buffer.pkl')
        import os
        if os.path.exists(replay_path):
            model.load_replay_buffer(replay_path)
            print(f'Replay buffer loaded: {replay_path}')
    else:
        model = AlgoClass(
            'MlpPolicy',
            env,
            batch_size=512,
            learning_rate=5e-5,
            learning_starts=8760,
            gamma=0.99,
            policy_kwargs=policy_kwargs,
            verbose=1,
            seed=args.seed,
            device=args.device,
        )
    episodes = args.episodes
    timesteps_per_episode = env.get_wrapper_attr('timestep_per_episode') - 1
    timesteps = int(args.timesteps) if args.timesteps is not None else episodes * timesteps_per_episode
    workspace_path = Path(env.get_wrapper_attr('workspace_path'))
    checkpoints_path = workspace_path / 'checkpoints'
    checkpoints_path.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    callbacks = [
        CheckpointCallback(
            save_freq=max(1, args.checkpoint_episodes * timesteps_per_episode),
            save_path=str(checkpoints_path),
            name_prefix=args.model_name,
            save_replay_buffer=True,
            save_vecnormalize=False,
        )
    ]
    if args.status_file:
        callbacks.append(
            StatusCallback(
                status_file=Path(args.status_file),
                workspace_path=workspace_path,
                timesteps_per_episode=timesteps_per_episode,
                started=started,
                update_every_steps=args.status_every_steps,
            )
        )
    if args.wandb:
        from tools.wandb_callback import WandbCallback
        wandb_name = f"{args.wandb_group or 'E0'}-seed{args.seed}"
        callbacks.append(
            WandbCallback(
                project=args.wandb_project,
                name=wandb_name,
                group=args.wandb_group,
                tags=['E0', 'nanjing', f'seed{args.seed}'],
                config={
                    'seed': args.seed,
                    'episodes': episodes,
                    'weather': weather_files,
                    'building': building_file,
                    'timesteps_per_episode': timesteps_per_episode,
                },
                log_interval=1000,
            )
        )
    model.learn(total_timesteps=timesteps, log_interval=1, callback=CallbackList(callbacks))
    elapsed = time.perf_counter() - started

    model_path = workspace_path / args.model_name
    model.save(str(model_path))
    model.save_replay_buffer(str(workspace_path / f'{args.model_name}_replay_buffer.pkl'))
    env.close()

    print(json.dumps({
        'episodes': episodes,
        'timesteps': timesteps,
        'timesteps_per_episode': timesteps_per_episode,
        'seed': args.seed,
        'device': args.device,
        'elapsed_seconds': elapsed,
        'workspace_path': str(workspace_path),
        'model_path': str(model_path) + '.zip',
        'checkpoints_path': str(checkpoints_path),
        'probe_dir': str(workspace_path / 'probe'),
    }, indent=2))


if __name__ == '__main__':
    main()
