import argparse
import json
import os
import subprocess
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
    parser.add_argument('--seeds', nargs='+', type=int, required=True)
    parser.add_argument('--device', default='auto')
    parser.add_argument('--model-prefix', default='multiseed_sac_dc')
    parser.add_argument('--checkpoint-episodes', type=int, default=10)
    parser.add_argument('--status-every-steps', type=int, default=500)
    parser.add_argument('--job-name', required=True)
    parser.add_argument('--conda-exe', type=Path, required=True)
    parser.add_argument('--conda-env', default='aidc-py310')
    args = parser.parse_args()

    repo = args.repo.resolve()
    jobs_dir = repo / 'training_jobs'
    jobs_dir.mkdir(exist_ok=True)
    job_dir = jobs_dir / args.job_name
    job_dir.mkdir(exist_ok=True)

    stdout_path = job_dir / 'stdout.log'
    stderr_path = job_dir / 'stderr.log'
    manifest_path = job_dir / 'manifest.json'

    eplus_path = resolve_eplus_path(repo)
    env = os.environ.copy()
    env['EPLUS_PATH'] = str(eplus_path)
    env['PYTHONPATH'] = str(repo) + os.pathsep + str(eplus_path)

    command = [
        str(args.conda_exe),
        'run',
        '-n',
        args.conda_env,
        'python',
        'tools/run_multiseed_training.py',
        '--repo',
        str(repo),
        '--episodes',
        str(args.episodes),
        '--device',
        args.device,
        '--model-prefix',
        args.model_prefix,
        '--checkpoint-episodes',
        str(args.checkpoint_episodes),
        '--status-every-steps',
        str(args.status_every_steps),
        '--conda-exe',
        str(args.conda_exe),
        '--conda-env',
        args.conda_env,
        '--seeds',
        *[str(seed) for seed in args.seeds],
    ]
    if args.timesteps is not None:
        command.extend(['--timesteps', str(args.timesteps)])

    with stdout_path.open('w', encoding='utf-8') as stdout_file, stderr_path.open('w', encoding='utf-8') as stderr_file:
        process = subprocess.Popen(
            command,
            cwd=repo,
            env=env,
            stdout=stdout_file,
            stderr=stderr_file,
            creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0),
        )

    manifest = {
        'job_name': args.job_name,
        'pid': process.pid,
        'repo': str(repo),
        'episodes': args.episodes,
        'timesteps': args.timesteps,
        'seeds': args.seeds,
        'device': args.device,
        'model_prefix': args.model_prefix,
        'checkpoint_episodes': args.checkpoint_episodes,
        'stdout_log': str(stdout_path),
        'stderr_log': str(stderr_path),
        'manifest_file': str(manifest_path),
        'started_epoch': time.time(),
        'command': command,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
