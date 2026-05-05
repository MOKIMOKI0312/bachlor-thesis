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
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_chiller_rbc --controller-mode rbc --steps 96 --output-root runs/chiller_tes_v1_smoke
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_chiller_tes_mpc --controller-mode mpc --steps 96 --output-root runs/chiller_tes_v1_smoke
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenario-set thesis_chiller_tes --steps 96 --output-dir runs/chiller_tes_v1_validation
python -m pytest -q
```

Frozen chiller+TES v1.0 results are under:

```text
results/chiller_tes_mpc_v1_20260505/
```
