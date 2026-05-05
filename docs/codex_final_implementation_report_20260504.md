# Codex Final Implementation Report - 2026-05-04

## Changed Files

- `.gitignore`: ignored root `runs/` local replay outputs.
- `README.md`: added `mpc_v2/` as active deterministic MILP-MPC package and documented smoke commands.
- `docs/project_management/毕业设计论文/thesis_draft.tex`: synchronized thesis route text to say the local `mpc_v2` controller now exists; no numerical result tables were filled.

## Created Files

- `mpc_v2/`: deterministic TES-PV-TOU MILP-MPC package.
- `tests/`: unit and smoke tests for schemas, TES dynamics, room proxy, power balance, MILP, closed-loop outputs, and scenario-set coverage.
- `docs/codex_repo_state_20260504.md`: repository path anchors.
- `docs/final_mpc_implementation_spec.md`: implementation contract and formulas.
- `docs/codex_final_implementation_report_20260504.md`: this report.

## Exact Commands Run

```powershell
python -m pytest -q
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_no_tes --controller-mode no_tes --steps 96 --output-root runs/smoke
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_tes_mpc --controller-mode mpc --steps 96 --output-root runs/smoke
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenario-set thesis_core --output-dir runs/final_mpc_validation
python -m pytest -q
git status --short
```

## Test Results

- `python -m pytest -q`: `12 passed in 3.07s` on the final run.
- no-TES smoke:
  - output path: `runs/smoke/smoke_no_tes`
  - `monitor.csv` rows: 96
  - `solver_log.csv` rows: 96
  - `episode_summary.json closed_loop_steps`: 96
- TES-MPC smoke:
  - output path: `runs/smoke/smoke_tes_mpc`
  - `monitor.csv` rows: 96
  - `solver_log.csv` rows: 96
  - `episode_summary.json closed_loop_steps`: 96
  - max `q_ch_tes_kw_th * q_dis_tes_kw_th`: 0
  - SOC range: approximately `[0.05, 0.95]`

## Validation Matrix Results

Full `thesis_core` matrix completed at:

```text
runs/final_mpc_validation
```

The matrix produced 10 scenario summaries with 96 closed-loop steps each. All scenarios reported `fallback_count = 0`, `optimal_rate = 1.0`, and `feasible_rate = 1.0`.

## Formula Assumptions

- `price_forecast` is interpreted as `currency/MWh` from the current CSV column `price_usd_per_mwh`.
- `base_facility_kw = it_load_kw * pue_hat(outdoor_temp_c)`.
- `base_cooling_kw_th = alpha_it_to_cooling * it_load_kw`.
- TES charge/discharge powers are thermal powers in `kW_th`.
- TES charge adds electric load through `q_ch_tes_kw_th / cop_charge`.
- TES discharge offsets electric load through `q_dis_tes_kw_th / cop_discharge_equiv`.

## Unit Assumptions

- Control step: `0.25 h`.
- Default prediction horizon: `192` steps, equal to 48 h.
- PV, IT, grid import, and facility power are in `kW_e`.
- TES charge/discharge and base cooling are in `kW_th`.
- TES capacity is in `kWh_th`.

## Unresolved Issues

- The optional rule-based TES baseline was not implemented because it was not part of the minimum deliverable.
- Validation uses synthetic/replay closed-loop dynamics, not EnergyPlus co-simulation.
- The PV-error scenarios currently have identical total cost to the perfect-forecast MPC case in the 96-step synthetic run, so they are not yet sufficient for a strong thesis claim about PV forecast-error sensitivity.
- Existing unrelated deleted/untracked literature and project-management files remain in the worktree and were not touched.

## Thesis Readiness

The code path is ready for thesis methods, reproducibility, and preliminary validation sections: model boundary, units, formulas, scenarios, outputs, and smoke/matrix runs are now concrete and reproducible. The numerical results should still be treated as preliminary until the validation matrix is reviewed for scenario sensitivity and any final thesis tables/plots are regenerated from saved run outputs.

No `references.bib` update was needed because no new citations were added or removed.
