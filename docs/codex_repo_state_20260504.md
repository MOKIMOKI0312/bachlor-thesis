# Codex Repository State - 2026-05-04

## Anchors

```text
REPO_ROOT = C:\Users\18430\Desktop\毕业设计代码
MPC_ROOT = C:\Users\18430\Desktop\毕业设计代码\mpc_v2
CONFIG_DIR = C:\Users\18430\Desktop\毕业设计代码\mpc_v2\config
CORE_DIR = C:\Users\18430\Desktop\毕业设计代码\mpc_v2\core
SCRIPTS_DIR = C:\Users\18430\Desktop\毕业设计代码\mpc_v2\scripts
TESTS_DIR = C:\Users\18430\Desktop\毕业设计代码\tests
DATA_DIR = C:\Users\18430\Desktop\毕业设计代码\Nanjing-DataCenter-TES-EnergyPlus\inputs
RUNS_DIR = C:\Users\18430\Desktop\毕业设计代码\runs
ANALYSIS_DIR = C:\Users\18430\Desktop\毕业设计代码\docs
```

## Branch And Source Facts

- Current branch during implementation: `codex/folder-cleanup-20260504`.
- Effective mainline baseline: current `HEAD`, equivalent to local `master` / `origin/master` at inspection time.
- There is no local `main` branch in this repository, so implementation did not run `git checkout main`.
- Historical source material was located by Git history at:
  `codex/rebuild-source-backup-20260504:AI-Data-Center-Analysis_migration_bundle_20260311/mpc_v2/`.
- The active MPC root is now the top-level `mpc_v2/` directory, not the historical migration-bundle path.

## Current Input Sources

- PV input:
  `Nanjing-DataCenter-TES-EnergyPlus/inputs/CHN_Nanjing_PV_6MWp_hourly.csv`
  with columns `timestamp,power_kw`.
- TOU price input:
  `Nanjing-DataCenter-TES-EnergyPlus/inputs/Jiangsu_TOU_2025_hourly.csv`
  with columns `timestamp,price_usd_per_mwh`.

## Dirty Worktree Note

The repository already had unrelated deleted and untracked literature/project-management files before MPC implementation. They were not reverted or incorporated into the MPC changes.
