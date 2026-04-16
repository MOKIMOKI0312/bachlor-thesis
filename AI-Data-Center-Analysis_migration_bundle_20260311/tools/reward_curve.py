import json, sys
import numpy as np
from pathlib import Path

seeds = {'01': 'run-042', '02': 'run-044', '03': 'run-045', '04': 'run-043'}
root = Path(__file__).resolve().parents[1]

all_data = {}
for seed, run in seeds.items():
    probe = root / 'runs' / 'train' / run / 'probe' / 'episode_samples.jsonl'
    if probe.exists():
        eps = [json.loads(l) for l in probe.read_text().strip().split('\n') if l.strip()]
        all_data[seed] = {e['episode_num']: e['cumulative_reward'] for e in eps}

print(f"{'Ep':>4}  {'seed01':>9} {'seed02':>9} {'seed03':>9} {'seed04':>9}   {'Mean':>9}")
print('-' * 62)

max_ep = max(max(d.keys()) for d in all_data.values())
for ep in range(1, max_ep+1, 5):
    vals = [all_data[s].get(ep) for s in ['01','02','03','04']]
    if all(v is not None for v in vals):
        mean = np.mean(vals)
        print(f'{ep:>4}  {vals[0]:>9.1f} {vals[1]:>9.1f} {vals[2]:>9.1f} {vals[3]:>9.1f}   {mean:>9.1f}')

# Summary
print(f"\n{'=' * 62}")
print("Summary (last 10 episodes):")
for seed in ['01','02','03','04']:
    if seed in all_data:
        rewards = sorted(all_data[seed].items())
        last10 = [r for _, r in rewards[-10:]]
        best = max(all_data[seed].values())
        best_ep = max(all_data[seed], key=all_data[seed].get)
        print(f"  seed{seed}: last10 avg={np.mean(last10):.1f}, best={best:.1f} (ep{best_ep})")
