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
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--episodes', type=int, required=True)
    parser.add_argument('--timesteps', type=int)
    parser.add_argument('--seeds', nargs='+', type=int, required=True)
    parser.add_argument('--device', default='auto')
    parser.add_argument('--model-prefix', default='multiseed_sac_dc')
    parser.add_argument('--checkpoint-episodes', type=int, default=10)
    parser.add_argument('--status-every-steps', type=int, default=500)
    parser.add_argument('--conda-exe', type=Path, required=True)
    parser.add_argument('--conda-env', default='aidc-py310')
    args = parser.parse_args()

    repo = args.repo.resolve()
    eplus_path = resolve_eplus_path(repo)
    env = os.environ.copy()
    env['EPLUS_PATH'] = str(eplus_path)
    env['PYTHONPATH'] = str(repo) + os.pathsep + str(eplus_path)

    jobs_dir = repo / 'training_jobs'
    jobs_dir.mkdir(exist_ok=True)

    batch_id = time.strftime('%Y%m%d-%H%M%S', time.localtime())
    batch_dir = jobs_dir / f'multiseed-{batch_id}'
    batch_dir.mkdir(exist_ok=True)

    batch_summary = {
        'batch_id': batch_id,
        'repo': str(repo),
        'device': args.device,
        'episodes': args.episodes,
        'timesteps': args.timesteps,
        'seeds': args.seeds,
        'jobs': [],
        'started_epoch': time.time(),
    }

    for seed in args.seeds:
        job_name = f'{args.model_prefix}-seed{seed:02d}'
        job_dir = jobs_dir / job_name
        job_dir.mkdir(exist_ok=True)
        status_path = job_dir / 'status.json'
        stdout_path = job_dir / 'stdout.log'
        stderr_path = job_dir / 'stderr.log'
        manifest_path = job_dir / 'manifest.json'

        command = [
            str(args.conda_exe),
            'run',
            '-n',
            args.conda_env,
            'python',
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
            '--status-every-steps',
            str(args.status_every_steps),
            '--status-file',
            str(status_path),
        ]
        if args.timesteps is not None:
            command.extend(['--timesteps', str(args.timesteps)])

        started = time.time()
        manifest = {
            'job_name': job_name,
            'pid': None,
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
            'started_epoch': started,
            'finished_epoch': None,
            'returncode': None,
            'command': command,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        with stdout_path.open('w', encoding='utf-8') as stdout_file, stderr_path.open('w', encoding='utf-8') as stderr_file:
            process = subprocess.run(
                command,
                cwd=repo,
                env=env,
                stdout=stdout_file,
                stderr=stderr_file,
                check=False,
            )

        manifest['finished_epoch'] = time.time()
        manifest['returncode'] = process.returncode
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        batch_summary['jobs'].append(
            {
                'job_name': job_name,
                'seed': seed,
                'returncode': process.returncode,
                'manifest_path': str(manifest_path),
                'status_file': str(status_path),
            }
        )

    batch_summary['finished_epoch'] = time.time()
    batch_summary_path = batch_dir / 'batch_summary.json'
    batch_summary_path.write_text(json.dumps(batch_summary, indent=2), encoding='utf-8')
    print(json.dumps(batch_summary, indent=2))


if __name__ == '__main__':
    main()
