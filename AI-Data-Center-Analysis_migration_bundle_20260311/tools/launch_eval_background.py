"""Detached launcher for evaluation scripts (Windows-safe via CREATE_NEW_PROCESS_GROUP)."""
import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--script', required=True, help='Python eval script path')
    parser.add_argument('--log', required=True, help='stdout+stderr log path')
    parser.add_argument('--args', nargs=argparse.REMAINDER, default=[],
                        help='Arguments to pass to the eval script')
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    eplus = repo / 'vendor' / 'EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64'

    env = os.environ.copy()
    env['EPLUS_PATH'] = str(eplus)
    env['PYTHONPATH'] = str(repo) + os.pathsep + str(eplus)

    log_path = Path(args.log).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, args.script, *args.args]

    with open(log_path, 'w', encoding='utf-8') as f:
        proc = subprocess.Popen(
            cmd,
            cwd=repo,
            env=env,
            stdout=f,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
            | getattr(subprocess, 'DETACHED_PROCESS', 0),
        )
    print(f'pid={proc.pid} log={log_path}')


if __name__ == '__main__':
    main()
