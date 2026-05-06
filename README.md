# Bachelor Thesis Workspace

This repository is organized around a minimal, validated Nanjing data center
EnergyPlus package plus a deterministic chiller+TES-PV-TOU MILP-MPC controller
package.

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
  - `scripts/`: closed-loop and validation-matrix runners.
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
python -m pytest -q
```

The current candidate horizon is 48 steps, i.e. 12 h at 15 min resolution. A
192-step / 48 h horizon is retained only as a slow manual extension.

Main PV/grid accounting is whole-facility behind-the-meter:

```text
grid_import_kw - pv_spill_kw = it_load_kw + cold_station_power_kw - pv_actual_kw
```

Cold-station-only proxy cost/grid/PV metrics are still reported for attribution
against older results, but they are not the primary cost boundary.

Frozen attribution results are under:

```text
results/chiller_tes_mpc_attribution_20260505/
```
