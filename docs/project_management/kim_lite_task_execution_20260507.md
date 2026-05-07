# Kim-lite paper-like MPC refactor execution

## Task Status

- Task ID: `kim_lite_paper_like_mpc_20260507`
- Status: `planned`
- Created: 2026-05-07
- Owner context: Codex local workspace
- Execution mode: local project-management task record

## Source

- Original file: `C:/Users/18430/Downloads/codex_kim_lite_mpc_refactor_plan_20260507.md`
- Local copy: `docs/project_management/codex_kim_lite_mpc_refactor_plan_20260507.md`

## Repository Baseline

- Current branch: `codex/mpc-rebuild`
- Current commit at task creation: `16521f4b`
- Current remote state: `origin/codex/mpc-rebuild` exists and is tracking the local branch.
- Pre-rebuild backup branch: `origin/codex/mpc-before-rebuild-backup-20260507`
- Important conflict recorded:
  - The source plan says not to delete current advanced MPC code.
  - The active branch already rebuilt `mpc_v2` into minimal MPC v1 and converted old advanced paths to unsupported/deferred behavior.
  - If old advanced code is needed for reference, recover or inspect it from `origin/codex/mpc-before-rebuild-backup-20260507`.

## Goal

Create a separate Kim-style `paper_like_mpc` implementation path for thesis-grade results without mixing it into the rebuilt minimal MPC v1 code path.

Default implementation direction for future work:

- Add new code under `mpc_v2/kim_lite/`.
- Add new scripts named `run_kim_lite_closed_loop.py`, `run_kim_lite_matrix.py`, and `plot_kim_lite_results.py`.
- Keep the existing rebuilt `mpc_v2` minimal controller path intact unless a later task explicitly changes it.
- Generate reproducible results under `results/kim_lite_repro_20260507/`.

## Phase Checklist

### Phase 0 - Inventory And Current State Confirmation

- Status: not started
- Required outputs:
  - `docs/codex_kim_lite_inventory_20260507.md`
  - repo tree snapshot
  - MPC file inventory snapshot
- Acceptance:
  - current branch, commit, pytest result, controller modes, scenario sets, result directories, and PPT assumption are recorded.

### Phase A - Paper-like Minimal Reproduction

- Status: not started
- Target:
  - Run `storage_priority_baseline` vs `paper_like_mpc`.
  - Implement Kim-like cold-plant/TES scheduling structure with signed net TES proxy.
- Required outputs:
  - `results/kim_lite_repro_20260507/phase_a/storage_priority/monitor.csv`
  - `results/kim_lite_repro_20260507/phase_a/paper_like_mpc/monitor.csv`
  - `results/kim_lite_repro_20260507/phase_a/summary.csv`
- Acceptance:
  - `pytest -q` passes.
  - 96-step storage-priority smoke run completes.
  - 96-step paper-like MPC smoke run completes.
  - SOC changes are visible.
  - `Q_tes_net > 0` occurs in low-price or PV-rich periods.
  - `Q_tes_net < 0` occurs in high-price or peak periods.
  - `P_grid_pos` is consistent with `P_nonplant + P_plant - P_pv`.

### Phase B - Attribution Matrix

- Status: not started
- Controllers:
  - `direct_no_tes`
  - `mpc_no_tes`
  - `storage_priority_tes`
  - `paper_like_mpc_tes`
- Required outputs:
  - `results/kim_lite_repro_20260507/phase_b_attribution/summary.csv`
  - `results/kim_lite_repro_20260507/phase_b_attribution/attribution_table.md`
- Acceptance:
  - Cost, grid import, peak, SOC, TES throughput, weighted charge/discharge prices, solver timing, and attribution formulas are reported.

### Phase C - China TOU And Critical Peak Pricing

- Status: not started
- Target:
  - Add flat/base/high-spread and critical-peak scenarios.
  - Use engineering approximation for float/nonfloat split if no explicit split exists.
- Required outputs:
  - `results/kim_lite_repro_20260507/phase_c_tou/summary.csv`
  - TOU cost and arbitrage figures.
- Acceptance:
  - Each scenario runs `mpc_no_tes` and `paper_like_mpc_tes`.
  - Representative scenario runs all four Phase B controllers.
  - Approximation assumptions are documented.

### Phase D - Peak-cap

- Status: not started
- Target:
  - Add peak-cap slack formulation before adding complex DR.
- Required outputs:
  - `results/kim_lite_repro_20260507/phase_d_peakcap/summary.csv`
  - peak reduction/cost tradeoff figures.
- Acceptance:
  - Cap ratios `{1.00, 0.99, 0.97, 0.95}` are evaluated.
  - Peak slack, peak reduction, peak-window TES discharge, and cost increase are reported.

### Phase E - Signed Valve Extension

- Status: not started
- Target:
  - Add `u_signed = Q_tes_net / Q_tes_max_kw_th` after paper-like MPC is stable.
- Acceptance:
  - `u_signed`, `signed_du`, `max_signed_du`, and signed-valve violation count are reported.
  - Ramp constraints are tested.

### Phase F - PPT Storyboard Or PPT Update

- Status: not started
- Default:
  - If `PPT_PATH` is not provided, do not modify any PPT.
  - Generate `docs/ppt_storyboard_kim_lite_20260507.md`.
- If `PPT_PATH` is provided:
  - Back up the PPT before modification.
  - Add only incremental figures/slides.
  - Do not delete user-authored pages.

## Test And Acceptance Checklist

Minimum tests to add during implementation:

- `tests/test_kim_lite_tes_net.py`
- `tests/test_kim_lite_power_balance.py`
- `tests/test_kim_lite_mode_constraints.py`
- `tests/test_kim_lite_peak_epigraph.py`
- `tests/test_kim_lite_storage_priority.py`
- `tests/test_kim_lite_scenarios.py`

Required checks:

- `Q_tes_net = Q_chiller - Q_load`
- `Q_tes_net > 0` increases SOC.
- `Q_tes_net < 0` decreases SOC.
- Mode off implies `nu = 0`.
- Mode on implies `Q_min <= nu <= Q_max`.
- `P_grid_pos >= P_nonplant + P_plant - P_pv`.
- `d_peak >= all P_grid_pos`.
- Storage-priority charges in low-price periods and discharges in high-price periods.
- Peak-cap slack is non-negative.
- `u_signed` ramp stays within configured limit.

## Stop Conditions

Stop implementation and report evidence if any of these occur:

- Solver infeasible without an explicit diagnostic artifact.
- Required data-flow fields are missing from monitor or summary files.
- Final SOC is not reported.
- Plant-level and whole-facility-level cost accounting cannot both be reported.
- `PPT_PATH` is absent but a task attempts to edit PPT.
- A change affects thesis facts but `CHANGELOG.md` and thesis-sync rationale are not updated.
- The implementation starts claiming numeric reproduction of Kim et al. 2022 rather than structural reproduction.

## Final Deliverables For The Full Kim-lite Task

- `docs/kim_lite_final_report_20260507.md`
- `results/kim_lite_repro_20260507/phase_a/summary.csv`
- `results/kim_lite_repro_20260507/phase_b_attribution/summary.csv`
- `results/kim_lite_repro_20260507/phase_c_tou/summary.csv`
- `results/kim_lite_repro_20260507/phase_d_peakcap/summary.csv`
- `results/kim_lite_repro_20260507/figures/`
- `docs/ppt_storyboard_kim_lite_20260507.md`

## Notes For Future Execution

- This task record does not start Phase A.
- This task record does not update `thesis_draft.tex` or `references.bib`.
- When implementation starts, update `CHANGELOG.md` because code and validation outputs will change.
- If paper-like results are later used in the thesis, update `docs/project_management/毕业设计论文/thesis_draft.tex` and check `references.bib`.
