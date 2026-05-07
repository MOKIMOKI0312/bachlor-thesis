# Kim-lite MPC Inventory - 2026-05-07

## Current Repository State

- current_branch: `codex/kim-lite-paper-mpc`
- current_commit: `20398c7ab3737b7588de2b26f7f159a4f4f39a96`
- upstream_start_point: `codex/mpc-rebuild`
- pre_rebuild_backup_branch: `origin/codex/mpc-before-rebuild-backup-20260507`

## Pytest Baseline

```text
python -m pytest -q
17 passed in 18.01s
```

## Current Controller Modes

From the rebuilt `mpc_v2` public closed-loop interface:

- `no_tes`
- `rbc`
- `mpc`
- `mpc_no_tes`

These modes belong to the rebuilt minimal MPC v1 path. Kim-lite work should add a separate paper-like path under `mpc_v2/kim_lite/`.

## Current Scenario Sets

Current `mpc_v2/config/scenario_sets.yaml` contains the minimal rebuilt MPC v1 validation matrix:

- `rebuild_no_tes_24h`
- `rebuild_rbc_24h`
- `rebuild_mpc_24h`

## Current Result Directories

Existing top-level result directories at inventory time:

- `results/chiller_tes_mpc_attribution_20260505`
- `results/chiller_tes_mpc_v1_20260505`
- `results/china_tou_dr_matrices_20260506`
- `results/mpc_rebuild_v0_4_0_20260507`
- `results/mpc_v2_20260505`

## Inventory Artifacts

- Repo directory snapshot: `docs/repo_tree_depth3_before_kim_lite.txt`
- MPC file snapshot: `docs/mpc_v2_files_before_kim_lite.txt`
- MPC tracked source file count in snapshot: 19

## PPT Handling Assumption

- `PPT_PATH` was not set at inventory time.
- Kim-lite execution must not modify PPT files unless `PPT_PATH` is explicitly provided and the target PPT is backed up first.
- Default Phase F output is a Markdown storyboard plus figure assets.

## Conflict Note

The source Kim-lite plan says not to delete current advanced MPC code. The active implementation branch already starts from `codex/mpc-rebuild`, where old advanced MPC paths were removed or marked unsupported. For reference to the old advanced implementation, inspect `origin/codex/mpc-before-rebuild-backup-20260507`; do not roll back this branch unless explicitly requested.
