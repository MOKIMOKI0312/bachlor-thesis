import argparse
import json
import os
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sinergym.utils.training_monitor import build_dashboard_snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()

    snapshot = build_dashboard_snapshot(args.manifest, persist=True)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    status_path = Path(manifest['status_file'])
    stdout_path = Path(manifest['stdout_log'])
    stderr_path = Path(manifest['stderr_log'])

    payload = {
        'job_name': manifest['job_name'],
        'pid': manifest['pid'],
        'pid_alive': False,
        'status_file_exists': status_path.exists(),
        'stdout_log': str(stdout_path),
        'stderr_log': str(stderr_path),
    }

    try:
        os.kill(manifest['pid'], 0)
        payload['pid_alive'] = True
    except OSError:
        payload['pid_alive'] = False

    if status_path.exists():
        payload['status'] = json.loads(status_path.read_text(encoding='utf-8'))

    workspace_path = None
    if stdout_path.exists():
        text = stdout_path.read_text(encoding='utf-8', errors='replace')
        marker = '"workspace_path": "'
        idx = text.rfind(marker)
        if idx != -1:
            start = idx + len(marker)
            end = text.find('"', start)
            workspace_path = text[start:end].encode('utf-8').decode('unicode_escape')
            payload['workspace_path'] = workspace_path

    if workspace_path:
        progress_path = Path(workspace_path) / 'progress.csv'
        checkpoint_dir = Path(workspace_path) / 'checkpoints'
        payload['progress_exists'] = progress_path.exists()
        payload['checkpoints_exists'] = checkpoint_dir.exists()
        if checkpoint_dir.exists():
            payload['checkpoint_files'] = sorted(p.name for p in checkpoint_dir.iterdir())
        if progress_path.exists():
            df = pd.read_csv(progress_path)
            payload['completed_episodes'] = int(len(df))
            if len(df) > 0:
                last = df.iloc[-1]
                payload['last_episode'] = {
                    'episode_num': int(last['episode_num']),
                    'cumulative_reward': float(last['cumulative_reward']),
                    'mean_reward': float(last['mean_reward']),
                }

    payload['dashboard_snapshot'] = {
        'latest_step': snapshot.get('latest_step'),
        'summary': snapshot.get('summary'),
        'workspace': snapshot.get('workspace'),
    }

    print(json.dumps(payload, indent=2))


if __name__ == '__main__':
    main()
