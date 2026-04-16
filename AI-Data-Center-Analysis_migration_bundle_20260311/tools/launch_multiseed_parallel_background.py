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


def resolve_env_python(conda_env: str) -> Path:
    candidate = Path.home() / '.conda' / 'envs' / conda_env / 'python.exe'
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f'Python executable for conda env not found: {candidate}')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--episodes', type=int, required=True)
    parser.add_argument('--timesteps', type=int)
    parser.add_argument('--seeds', nargs='+', type=int, required=True)
    parser.add_argument('--device', default='auto')
    parser.add_argument('--model-prefix', default='multiseed_sac_dc')
    parser.add_argument('--checkpoint-episodes', type=int, default=10)
    parser.add_argument('--job-name', required=True)
    parser.add_argument('--conda-exe', type=Path, required=True)
    parser.add_argument('--conda-env', default='aidc-py310')
    parser.add_argument('--python-exe', type=Path)
    args = parser.parse_args()

    repo = args.repo.resolve()
    jobs_dir = repo / 'training_jobs'
    jobs_dir.mkdir(exist_ok=True)
    batch_dir = jobs_dir / args.job_name
    batch_dir.mkdir(exist_ok=True)

    eplus_path = resolve_eplus_path(repo)
    python_exe = args.python_exe.resolve() if args.python_exe else resolve_env_python(args.conda_env)
    env = os.environ.copy()
    env['EPLUS_PATH'] = str(eplus_path)
    env['PYTHONPATH'] = str(repo) + os.pathsep + str(eplus_path)

    children = []
    for seed in args.seeds:
        child_job_name = f'{args.model_prefix}-seed{seed:02d}'
        child_dir = jobs_dir / child_job_name
        child_dir.mkdir(exist_ok=True)
        stdout_path = child_dir / 'stdout.log'
        stderr_path = child_dir / 'stderr.log'
        status_path = child_dir / 'status.json'
        manifest_path = child_dir / 'manifest.json'

        command = [
            str(python_exe),
            'tools/run_short_training.py',
            '--episodes',
            str(args.episodes),
            '--seed',
            str(seed),
            '--device',
            args.device,
            '--model-name',
            f'{args.model_prefix}_seed{seed:02d}',
            '--checkpoint-episodes',
            str(args.checkpoint_episodes),
            '--status-file',
            str(status_path),
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

        child_manifest = {
            'job_name': child_job_name,
            'pid': process.pid,
            'repo': str(repo),
            'episodes': args.episodes,
            'timesteps': args.timesteps,
            'seed': seed,
            'device': args.device,
            'model_name': f'{args.model_prefix}_seed{seed:02d}',
            'checkpoint_episodes': args.checkpoint_episodes,
            'stdout_log': str(stdout_path),
            'stderr_log': str(stderr_path),
            'status_file': str(status_path),
            'manifest_file': str(manifest_path),
            'started_epoch': time.time(),
            'command': command,
            'dashboard_url_hint': f'http://127.0.0.1:8765/?job={child_job_name}',
        }
        manifest_path.write_text(json.dumps(child_manifest, indent=2), encoding='utf-8')
        children.append(child_manifest)

    batch_manifest = {
        'job_name': args.job_name,
        'repo': str(repo),
        'episodes': args.episodes,
        'timesteps': args.timesteps,
        'seeds': args.seeds,
        'device': args.device,
        'model_prefix': args.model_prefix,
        'checkpoint_episodes': args.checkpoint_episodes,
        'python_exe': str(python_exe),
        'started_epoch': time.time(),
        'children': children,
    }
    batch_manifest_path = batch_dir / 'manifest.json'
    batch_manifest_path.write_text(json.dumps(batch_manifest, indent=2), encoding='utf-8')
    print(json.dumps(batch_manifest, indent=2))


if __name__ == '__main__':
    main()
