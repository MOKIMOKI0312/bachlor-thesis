"""
E0 Baseline Evaluation - 评估 4 seed 的 best checkpoint 在南京全年的表现。

输出：
  - results/e0_evaluation_summary.json  (4 seed + 中位数汇总)
  - results/e0_evaluation_detail.csv    (逐 seed 详细指标)
  - 每 seed 的全年逐时数据在各自 run 目录的 monitor.csv 中

用法:
    python tools/evaluate_e0.py
"""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gymnasium as gym
import numpy as np
from stable_baselines3 import SAC

from sinergym.utils.common import get_ids
from sinergym.utils.logger import CSVLogger
from sinergym.utils.wrappers import LoggerWrapper, NormalizeObservation


class EvalCSVLogger(CSVLogger):
    def __init__(self, monitor_header, progress_header, log_progress_file, log_file=None, flag=True):
        super().__init__(monitor_header, progress_header, log_progress_file, log_file, flag)

    def _create_row_content(self, obs, action, terminated, truncated, info):
        return [
            info.get('timestep', 0)] + list(obs) + list(action) + [
            info.get('time_elapsed(hours)', 0),
            info.get('reward', None),
            info.get('energy_term', 0),
            info.get('ITE_term', 0),
            info.get('comfort_term', 0),
            terminated,
            truncated]


# Seed → run directory mapping
SEED_RUN_MAP = {
    'seed01': {'run': 'run-042', 'best_ep': 33, 'best_step': 262770},
    'seed02': {'run': 'run-044', 'best_ep': 85, 'best_step': 788310},
    'seed03': {'run': 'run-045', 'best_ep': 48, 'best_step': 437950},
    'seed04': {'run': 'run-043', 'best_ep': 77, 'best_step': 700720},
}

# Also evaluate late checkpoints (post-convergence, closest to ep120)
LATE_STEP = 1051080  # ~ep120


def evaluate_checkpoint(model_path, mean_path, var_path, label, weather_file, trace_path=None):
    """Run full-year deterministic evaluation."""

    if 'Eplus-DC-Cooling' not in get_ids():
        raise RuntimeError('Eplus-DC-Cooling not registered')

    mean = np.loadtxt(mean_path, dtype='float')
    var = np.loadtxt(var_path, dtype='float')
    model = SAC.load(str(model_path))

    config = {'runperiod': (1, 1, 2025, 31, 12, 2025), 'timesteps_per_hour': 1}
    experiment_name = f'eval-{label}'

    env = gym.make(
        'Eplus-DC-Cooling',
        env_name=experiment_name,
        building_file='DRL_DC_evaluation.epJSON',
        weather_files=weather_file,
        config_params=config,
        evaluation_flag=1,
    )
    env = NormalizeObservation(env, mean=mean, var=var, automatic_update=False)
    env = LoggerWrapper(
        env,
        logger_class=EvalCSVLogger,
        monitor_header=['timestep']
        + env.get_wrapper_attr('observation_variables')
        + env.get_wrapper_attr('action_variables')
        + ['time (hours)', 'reward', 'energy_term', 'ITE_term', 'comfort_term', 'terminated', 'truncated'],
    )

    # Load workload trace if provided
    util_rate = None
    if trace_path and Path(trace_path).exists():
        util_rate = np.loadtxt(trace_path, dtype='float')

    started = time.perf_counter()
    obs, info = env.reset()
    terminated = truncated = False
    rewards = []
    energy_terms = []
    comfort_terms = []
    temperatures = []
    steps = 0

    while not (terminated or truncated):
        action, _ = model.predict(obs, deterministic=True)
        if util_rate is not None and steps < len(util_rate):
            action[4] = np.clip(util_rate[steps], 0.0, 1.0)
        obs, reward, terminated, truncated, info = env.step(action)
        rewards.append(float(reward))
        energy_terms.append(float(info.get('energy_term', 0)))
        comfort_terms.append(float(info.get('comfort_term', 0)))

        # Extract air temperature from obs (index depends on observation order)
        # time(3) + outdoor_temp(0) + outdoor_wet(1) + air_temp(2) → index 5
        if len(obs) >= 6:
            temperatures.append(float(obs[4]))  # air_temperature is 3rd variable, index=2+3=5... let me check

        steps += 1

    elapsed = time.perf_counter() - started
    workspace = env.get_wrapper_attr('workspace_path')
    env.close()

    # Calculate metrics
    total_reward = float(np.sum(rewards))
    mean_reward = float(np.mean(rewards))
    total_energy_term = float(np.sum(energy_terms))
    total_comfort_term = float(np.sum(comfort_terms))
    comfort_violations = sum(1 for c in comfort_terms if c < -0.01)
    comfort_violation_pct = comfort_violations / max(steps, 1) * 100

    # Temperature stats
    if temperatures:
        temp_mean = float(np.mean(temperatures))
        temp_max = float(np.max(temperatures))
        temp_min = float(np.min(temperatures))
    else:
        temp_mean = temp_max = temp_min = 0

    result = {
        'label': label,
        'model_path': str(model_path),
        'weather': weather_file,
        'steps': steps,
        'total_reward': total_reward,
        'mean_reward': mean_reward,
        'total_energy_term': total_energy_term,
        'total_comfort_term': total_comfort_term,
        'comfort_violation_pct': comfort_violation_pct,
        'temp_mean': temp_mean,
        'temp_max': temp_max,
        'temp_min': temp_min,
        'elapsed_seconds': elapsed,
        'workspace_path': workspace,
    }

    return result


def main():
    results_dir = ROOT / 'results'
    results_dir.mkdir(exist_ok=True)

    weather = 'CHN_JS_Nanjing.582380_TMYx.2009-2023.epw'
    trace = str(ROOT / 'Data' / 'AI Trace Data' / 'Earth_hourly.csv')

    all_results = []

    for seed_name, info in SEED_RUN_MAP.items():
        run_dir = ROOT / 'runs' / 'train' / info['run']
        mean_path = run_dir / 'mean.txt'
        var_path = run_dir / 'var.txt'

        # Evaluate best checkpoint
        best_step = info['best_step']
        ckpt_name = f"e0_nanjing_{seed_name}_{best_step}_steps"
        ckpt_path = run_dir / 'checkpoints' / f'{ckpt_name}.zip'

        if not ckpt_path.exists():
            print(f'WARNING: {ckpt_path} not found, skipping')
            continue

        print(f'\n{"="*60}')
        print(f'Evaluating {seed_name} best checkpoint (ep~{info["best_ep"]}, step {best_step})')
        print(f'{"="*60}')

        result = evaluate_checkpoint(
            model_path=ckpt_path,
            mean_path=mean_path,
            var_path=var_path,
            label=f'{seed_name}-best-ep{info["best_ep"]}',
            weather_file=weather,
            trace_path=trace,
        )
        result['seed'] = seed_name
        result['checkpoint_type'] = 'best'
        result['checkpoint_episode'] = info['best_ep']
        all_results.append(result)

        print(f'  reward={result["total_reward"]:.1f}, comfort_viol={result["comfort_violation_pct"]:.1f}%')

        # Also evaluate latest checkpoint
        late_ckpt = run_dir / 'checkpoints' / f'e0_nanjing_{seed_name}_{LATE_STEP}_steps.zip'
        if late_ckpt.exists():
            print(f'\nEvaluating {seed_name} latest checkpoint (ep~120, step {LATE_STEP})')
            late_result = evaluate_checkpoint(
                model_path=late_ckpt,
                mean_path=mean_path,
                var_path=var_path,
                label=f'{seed_name}-latest-ep120',
                weather_file=weather,
                trace_path=trace,
            )
            late_result['seed'] = seed_name
            late_result['checkpoint_type'] = 'latest'
            late_result['checkpoint_episode'] = 120
            all_results.append(late_result)
            print(f'  reward={late_result["total_reward"]:.1f}, comfort_viol={late_result["comfort_violation_pct"]:.1f}%')

    # Summary
    print(f'\n{"="*60}')
    print('SUMMARY')
    print(f'{"="*60}')

    best_results = [r for r in all_results if r['checkpoint_type'] == 'best']
    latest_results = [r for r in all_results if r['checkpoint_type'] == 'latest']

    if best_results:
        best_rewards = [r['total_reward'] for r in best_results]
        median_idx = int(np.argsort(best_rewards)[len(best_rewards) // 2])
        median_seed = best_results[median_idx]['seed']

        summary = {
            'experiment': 'E0-Nanjing-baseline',
            'weather': weather,
            'trace': 'Earth_hourly',
            'num_seeds': len(best_results),
            'best_checkpoints': {
                'rewards': {r['seed']: r['total_reward'] for r in best_results},
                'median_reward': float(np.median(best_rewards)),
                'mean_reward': float(np.mean(best_rewards)),
                'std_reward': float(np.std(best_rewards)),
                'best_seed': best_results[int(np.argmax(best_rewards))]['seed'],
                'median_seed': median_seed,
                'comfort_violations': {r['seed']: r['comfort_violation_pct'] for r in best_results},
            },
        }

        if latest_results:
            late_rewards = [r['total_reward'] for r in latest_results]
            summary['latest_checkpoints'] = {
                'rewards': {r['seed']: r['total_reward'] for r in latest_results},
                'median_reward': float(np.median(late_rewards)),
                'mean_reward': float(np.mean(late_rewards)),
            }

        summary['all_results'] = all_results

        # Save
        summary_path = results_dir / 'e0_evaluation_summary.json'
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'\nSaved: {summary_path}')

        # Print table
        print(f'\n{"Seed":<10} {"Type":<8} {"Reward":<12} {"Comfort%":<10} {"TempMax":<10}')
        print('-' * 50)
        for r in all_results:
            print(f'{r["seed"]:<10} {r["checkpoint_type"]:<8} {r["total_reward"]:<12.1f} {r["comfort_violation_pct"]:<10.1f} {r["temp_max"]:<10.1f}')

    print('\nDone.')


if __name__ == '__main__':
    main()
