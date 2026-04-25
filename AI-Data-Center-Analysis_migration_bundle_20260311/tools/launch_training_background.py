import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def resolve_eplus_path(repo: Path) -> Path:
    candidates = [
        repo / 'vendor' / 'EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64',
        repo / 'EnergyPlus-23.1.0' / 'EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64',
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f'EnergyPlus path not found. Checked: {candidates}')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--episodes', type=int, required=True)
    parser.add_argument('--timesteps', type=int)
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--device', default='auto')
    parser.add_argument('--model-name', required=True)
    parser.add_argument('--checkpoint-episodes', type=int, default=10)
    parser.add_argument('--job-name', required=True)
    parser.add_argument('--conda-exe', type=Path, required=False, help='(deprecated, ignored)')
    parser.add_argument('--python-exe', type=Path, required=False, help='Python executable path')
    parser.add_argument('--resume', type=str, default=None, help='Checkpoint .zip path to resume from')
    parser.add_argument('--algo', default='dsac_t', choices=['sac', 'dsac_t'])
    parser.add_argument('--training-script', default='tools/run_short_training.py',
                        help='Path to training entrypoint (default: run_short_training.py; use run_tes_training.py for M1 TES)')
    parser.add_argument('--wandb', action='store_true', help='Enable wandb logging')
    parser.add_argument('--wandb-project', default='dc-cooling-optimization')
    parser.add_argument('--wandb-group', default=None)
    # Any extra args after a "--" separator are forwarded verbatim to the
    # training script (e.g. --reward-cls rl_cost for M2).
    args, extra = parser.parse_known_args()
    if extra and extra[0] == '--':
        extra = extra[1:]

    repo = args.repo.resolve()
    jobs_dir = repo / 'training_jobs'
    jobs_dir.mkdir(exist_ok=True)
    job_dir = jobs_dir / args.job_name
    job_dir.mkdir(exist_ok=True)

    stdout_path = job_dir / 'stdout.log'
    stderr_path = job_dir / 'stderr.log'
    status_path = job_dir / 'status.json'
    manifest_path = job_dir / 'manifest.json'

    eplus_path = resolve_eplus_path(repo)
    env = os.environ.copy()
    env['EPLUS_PATH'] = str(eplus_path)
    env['PYTHONPATH'] = str(repo) + os.pathsep + str(eplus_path)

    python_exe = args.python_exe or sys.executable
    command = [
        str(python_exe),
        args.training_script,
        '--episodes',
        str(args.episodes),
        '--seed',
        str(args.seed),
        '--device',
        args.device,
        '--model-name',
        args.model_name,
        '--checkpoint-episodes',
        str(args.checkpoint_episodes),
        '--status-file',
        str(status_path),
    ]
    if args.timesteps is not None:
        command.extend(['--timesteps', str(args.timesteps)])
    if args.resume:
        command.extend(['--resume', args.resume])
    command.extend(['--algo', args.algo])
    if args.wandb:
        command.append('--wandb')
        command.extend(['--wandb-project', args.wandb_project])
        if args.wandb_group:
            command.extend(['--wandb-group', args.wandb_group])
    # Forward any extra args (e.g. --reward-cls rl_cost for M2)
    if extra:
        command.extend(extra)

    # Full detachment on Windows: DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP +
    # CREATE_NO_WINDOW ensures the child survives if the launcher's parent
    # shell closes (avoids Job Object cascade termination).
    detach_flags = (
        getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        | getattr(subprocess, 'DETACHED_PROCESS', 0)
        | getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    )
    with stdout_path.open('w', encoding='utf-8') as stdout_file, stderr_path.open('w', encoding='utf-8') as stderr_file:
        process = subprocess.Popen(
            command,
            cwd=repo,
            env=env,
            stdout=stdout_file,
            stderr=stderr_file,
            creationflags=detach_flags,
        )

    manifest = {
        'job_name': args.job_name,
        'pid': process.pid,
        'repo': str(repo),
        'episodes': args.episodes,
        'timesteps': args.timesteps,
        'seed': args.seed,
        'device': args.device,
        'model_name': args.model_name,
        'checkpoint_episodes': args.checkpoint_episodes,
        'stdout_log': str(stdout_path),
        'stderr_log': str(stderr_path),
        'status_file': str(status_path),
        'manifest_file': str(manifest_path),
        'started_epoch': time.time(),
        'command': command,
        'dashboard_url_hint': f'http://127.0.0.1:8765/?job={args.job_name}',
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
