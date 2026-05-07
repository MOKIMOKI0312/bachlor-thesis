# EnergyPlus-MPC Coupling Execution 2026-05-07

## Status

`validated-first-pass`

## Branch

`codex/energyplus-mpc-coupling`

## Goal

Extract MPC parameters from the current EnergyPlus model and baseline outputs, then run a first online co-simulation loop that reads EnergyPlus state, solves or selects a controller action, writes `TES_Set`, and stores auditable closed-loop artifacts.

## Checklist

- [x] Create coupling package under `Nanjing-DataCenter-TES-EnergyPlus/controller/energyplus_mpc/`.
- [x] Add static epJSON extractor.
- [x] Add baseline output identifier.
- [x] Add parameter YAML.
- [x] Add Runtime API runner for `no_control`, `rbc`, `mpc`, and `perturbation`.
- [x] Add perturbation profile for TES source/use-side response validation.
- [x] Add result audit command.
- [x] Run 96-step EnergyPlus co-sim cases.
- [x] Write coupling report.
- [x] Update changelog.
- [ ] Update thesis draft only after user confirms these results are thesis conclusions.

## Verification Commands

```powershell
python -m pytest -q
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.extract_params --model Nanjing-DataCenter-TES-EnergyPlus/model/Nanjing_DataCenter_TES.epJSON
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.identify_params --timeseries Nanjing-DataCenter-TES-EnergyPlus/out/energyplus_nanjing/timeseries_15min.csv
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller no_control --max-steps 96
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller rbc --max-steps 96
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller mpc --max-steps 96
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_perturbation_profile --max-steps 96
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.audit_results --root results/energyplus_mpc_20260507
git diff --check
```

## Result Directory

`results/energyplus_mpc_20260507/`

## Stop Conditions For Next Iteration

- Any unresolved Runtime API handle.
- Any EnergyPlus Severe Error.
- `TES_Set` echo mismatch.
- Missing `monitor.csv`, `observation.csv`, `mpc_action.csv`, `solver_log.csv`, `summary.csv`, or `run_manifest.json`.
- MPC fallback count greater than zero.
- Any thesis update that does not distinguish EnergyPlus measured values from MPC proxy predictions.
