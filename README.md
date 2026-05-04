# Bachelor Thesis Workspace

This repository is organized around a minimal, validated Nanjing data center
EnergyPlus package.

## Active Entry Point

- `Nanjing-DataCenter-TES-EnergyPlus/`
  - `model/`: TES-enabled EnergyPlus epJSON model.
  - `weather/`: Nanjing EPW weather file.
  - `inputs/`: Jiangsu/Nanjing TOU price CSV and Nanjing PV forecast CSV.
  - `docs/`: model manifest and validation notes.
  - `run_energyplus_nanjing.ps1`: runner and input validator.

## Supporting Material

- `docs/literature/`: reproduction papers and other references.
- `docs/project_management/`: project management notes and implementation
  suggestions.
- `项目目标/`: route, goals, decisions, evidence, and archived task plans.
- `_archive/`: runtime communication logs and external/legacy reference
  material that is not part of the active model package.

## Local Outputs

EnergyPlus outputs are written under:

```text
Nanjing-DataCenter-TES-EnergyPlus/out/
```

The output directory is intentionally ignored by Git.
