# Bachelor Thesis Workspace

This repository is organized around a minimal, validated Nanjing data center
EnergyPlus package plus a deterministic chiller+TES-PV-TOU MILP-MPC controller
package.

## Current Thesis Result Positioning

Main paper results should use the Kim-lite relaxed proxy model under
`mpc_v2/`, especially the controller label
`paper_like_mpc_tes_relaxed`. This is a continuous-dispatch,
control-oriented chiller+TES MPC used to analyze TES scheduling under TOU,
critical peak, signed-valve ramp, and peak-cap scenarios.

Supplementary diagnostics use EnergyPlus Runtime API I/O coupling under
`Nanjing-DataCenter-TES-EnergyPlus/controller/energyplus_mpc/`. Those results
verify `TES_Set` and `Chiller_T_Set` actuator writes, echo checks, fallback
status, and temperature risk. They are not final cost-saving evidence unless
`cost_comparison_valid=true`.

## Active Entry Point

- `Nanjing-DataCenter-TES-EnergyPlus/`
  - `model/`: TES-enabled EnergyPlus epJSON model.
  - `weather/`: Nanjing EPW weather file.
  - `inputs/`: Jiangsu/Nanjing TOU price CSV and Nanjing PV forecast CSV.
  - `docs/`: model manifest and validation notes.
  - `run_energyplus_nanjing.ps1`: runner and input validator.
- `mpc_v2/`
  - `config/`: base controller configuration and scenario matrix.
  - `core/`: typed schemas, TES dynamics, room proxy, chiller plant mode model,
    PV/grid balance, MILP construction, controller wrapper, and metrics.
  - `scripts/`: closed-loop, validation-matrix, China matrix generation, and
    result-analysis runners.
- `tests/`: unit and smoke tests for the deterministic MPC package.

## Supporting Material

- `docs/literature/`: reproduction papers and other references.
- `docs/project_management/`: project management notes and implementation
  suggestions, including active route and decision notes.
- `_archive/`: runtime communication logs and external/legacy reference
  material that is not part of the active model package.
  Historical `项目目标/` materials are archived under `_archive/project_goals/`.

## Local Outputs

EnergyPlus outputs are written under:

```text
Nanjing-DataCenter-TES-EnergyPlus/out/
```

The output directory is intentionally ignored by Git.

MPC replay outputs are written under:

```text
runs/
```

The root `runs/` directory is also ignored by Git.

## Chiller+TES MPC Smoke Runs

From the repository root:

```powershell
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_chiller_no_tes --controller-mode no_tes --steps 96 --output-root runs/chiller_tes_v1_smoke
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_chiller_mpc_no_tes --controller-mode mpc_no_tes --steps 96 --output-root runs/chiller_tes_v1_smoke
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_chiller_rbc --controller-mode rbc --steps 96 --output-root runs/chiller_tes_v1_smoke
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_chiller_tes_mpc --controller-mode mpc --steps 96 --output-root runs/chiller_tes_v1_smoke
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenario-set attribution_core --output-dir runs/attribution
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenario-set china_tou_screening_smoke --output-dir runs/china_tou_screening
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenario-set china_dr_peakcap_core --output-dir runs/china_dr_peakcap
python -m mpc_v2.scripts.analyze_results --input-dir runs/china_tou_screening --output-dir runs/china_tou_screening/analysis
python -m pytest -q
```

## China TOU/DR 1-Month Matrix

The full China TOU/DR matrix uses the synthetic/replay `mpc_v2` controller, not
EnergyPlus online co-simulation. Generate the frozen pilot/month YAML files and
run the formal 30 day matrix from the repository root:

```powershell
python -m mpc_v2.scripts.generate_china_matrix --profile pilot --output mpc_v2/config/generated_china_matrix_pilot.yaml
python -m mpc_v2.scripts.generate_china_matrix --profile month --output mpc_v2/config/generated_china_matrix_month.yaml
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenarios mpc_v2/config/generated_china_matrix_month.yaml --scenario-set china_all_full --output-dir runs/china_tou_dr_month_20260506 --max-workers 8 --resume-existing
python -m mpc_v2.scripts.analyze_results --input-dir runs/china_tou_dr_month_20260506 --output-dir runs/china_tou_dr_month_20260506/analysis
python -m mpc_v2.scripts.generate_result_reports --result-dir results/china_tou_dr_matrices_20260506
```

Frozen 138-run results are under:

```text
results/china_tou_dr_matrices_20260506/
```

The current candidate horizon is 48 steps, i.e. 12 h at 15 min resolution. A
192-step / 48 h horizon is retained only as a slow manual extension.

Main PV/grid accounting is whole-facility behind-the-meter:

```text
grid_import_kw - pv_spill_kw = it_load_kw + cold_station_power_kw - pv_actual_kw
```

Cold-station-only proxy cost/grid/PV metrics are still reported for attribution
against older results, but they are not the primary cost boundary.

China TOU/DR scenario services are available in `mpc_v2/core/tariff_service.py`
and `mpc_v2/core/dr_service.py`. Closed-loop runs now write `monitor.csv`,
`timeseries.csv`, `events.csv`, `solver_log.csv`, `episode_summary.json`, and
`summary.csv` per case.

Frozen attribution results are under:

```text
results/chiller_tes_mpc_attribution_20260505/
```
