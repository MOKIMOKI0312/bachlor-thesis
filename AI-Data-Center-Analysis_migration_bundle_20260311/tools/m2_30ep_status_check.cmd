@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_DIR=%%~fI"
cd /d "%REPO_DIR%"

"C:\Users\18430\.conda\envs\aidc-py310\python.exe" tools\check_m2_training_status.py ^
  --label m2e3b_30ep_cpu4_parallel ^
  --status-files training_jobs\m2e3b_30ep_cpu4_seed1\status.json training_jobs\m2e3b_30ep_cpu4_seed2\status.json training_jobs\m2e3b_30ep_cpu4_seed3\status.json training_jobs\m2e3b_30ep_cpu4_seed4\status.json ^
  --pid-file runs\m2e3b_30ep_cpu4_pids.json ^
  --workspace-dirs runs\run\run-023 runs\run\run-024 runs\run\run-025 runs\run\run-026 ^
  --output runs\m2e3b_30ep_cpu4_status.md ^
  --json-output runs\m2e3b_30ep_cpu4_status_summary.json

"C:\Users\18430\.conda\envs\aidc-py310\python.exe" tools\check_m2_tes_learning.py ^
  --job-dirs training_jobs\m2e3b_30ep_cpu4_seed1 training_jobs\m2e3b_30ep_cpu4_seed2 training_jobs\m2e3b_30ep_cpu4_seed3 training_jobs\m2e3b_30ep_cpu4_seed4 ^
  --output runs\m2e3b_30ep_cpu4_tes_learning.md ^
  --json-output runs\m2e3b_30ep_cpu4_tes_learning.json ^
  --last-episodes 3 ^
  --min-episodes 5 ^
  --strong-episodes 10
