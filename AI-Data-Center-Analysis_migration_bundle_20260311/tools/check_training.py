"""检查 12 seed 训练状态"""
import json
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

header = f"{'Seed':<8} {'Ep':<5} {'Last Reward':<14} {'Best Reward':<14} {'Best@Ep':<8} {'Comfort%':<10} {'Trend(10ep)':<14}"
print(header)
print('-' * 80)

all_rewards = {}
for seed in range(1, 13):
    sp = f'{seed:02d}'
    status_path = ROOT / 'training_jobs' / f'e01_nanjing-seed{sp}' / 'status.json'
    if not status_path.exists():
        print(f'seed{sp:<4} NO DATA')
        continue
    status = json.loads(status_path.read_text(encoding='utf-8-sig'))
    run_dir = Path(status.get('workspace_path', ''))
    probe_path = run_dir / 'probe' / 'episode_samples.jsonl'
    if not probe_path.exists():
        print(f'seed{sp:<4} no probe data')
        continue
    episodes = []
    for line in probe_path.read_text(encoding='utf-8').strip().split('\n'):
        if line.strip():
            try:
                episodes.append(json.loads(line))
            except Exception:
                pass
    if not episodes:
        print(f'seed{sp:<4} empty probe')
        continue
    rewards = [e['cumulative_reward'] for e in episodes]
    all_rewards[sp] = rewards
    best_idx = int(np.argmax(rewards))
    best_r = rewards[best_idx]
    best_ep = episodes[best_idx]['episode_num']
    last_r = rewards[-1]
    last_ep = episodes[-1]['episode_num']
    comfort = episodes[-1].get('comfort_violation_time_pct', 0)

    if len(rewards) >= 10:
        r10 = rewards[-10:]
        first5 = np.mean(r10[:5])
        last5 = np.mean(r10[5:])
        trend = f'{first5:.0f}->{last5:.0f}'
    else:
        trend = 'N/A'

    print(f'seed{sp:<4} {last_ep:<5} {last_r:<14.1f} {best_r:<14.1f} {best_ep:<8} {comfort:<10.1f} {trend:<14}')

# Summary
print('\n' + '=' * 80)
print('Summary')
print('-' * 80)
if all_rewards:
    all_best = {k: max(v) for k, v in all_rewards.items()}
    best_seed = max(all_best, key=all_best.get)
    median_best = np.median(list(all_best.values()))
    print(f'Best seed: seed{best_seed} (reward={all_best[best_seed]:.1f})')
    print(f'Median best reward: {median_best:.1f}')
    print(f'All best rewards: {", ".join(f"seed{k}={v:.0f}" for k,v in sorted(all_best.items()))}')

# Anomaly check
print('\nAnomalies:')
any_anomaly = False
for sp, rewards in all_rewards.items():
    status_path = ROOT / 'training_jobs' / f'e01_nanjing-seed{sp}' / 'status.json'
    status = json.loads(status_path.read_text(encoding='utf-8-sig'))
    metrics = status.get('training_metrics', {})
    critic = metrics.get('train/critic_loss', 0)
    ent = metrics.get('train/ent_coef', 0)
    actor = metrics.get('train/actor_loss', 0)

    issues = []
    if critic > 1000:
        issues.append(f'critic_loss={critic:.0f} (very high)')
    if ent > 0.1:
        issues.append(f'ent_coef={ent:.3f} (high exploration)')
    if actor < -100:
        issues.append(f'actor_loss={actor:.0f} (negative, possible divergence)')
    if len(rewards) >= 10:
        recent = rewards[-5:]
        best_ever = max(rewards)
        if np.mean(recent) < best_ever * 1.5:  # rewards are negative
            drop = (np.mean(recent) - best_ever) / abs(best_ever) * 100
            if drop < -30:
                issues.append(f'reward dropped {drop:.0f}% from best')

    if issues:
        print(f'  seed{sp}: {"; ".join(issues)}')
        any_anomaly = True

if not any_anomaly:
    print('  All seeds nominal.')
