# Nanjing Data Center TES EnergyPlus Model

This repository folder is now a minimal EnergyPlus package for a Nanjing data
center scenario with TES, PV forecast input, and external TOU price input.

## Contents

- `model/Nanjing_DataCenter_TES.epJSON`
  - Source: `Data/buildings/DRL_DC_training.epJSON`
  - Contains `ThermalStorage:ChilledWater:Mixed`
  - Contains EMS schedules and actuators for `TES_Set`, `TES_SOC_Obs`, and
    `TES_Avg_Temp_Obs`
  - Uses `ITE_Set=0.45`
- `weather/CHN_JS_Nanjing.582380_TMYx.2009-2023.epw`
  - Nanjing weather file used by EnergyPlus.
- `inputs/Jiangsu_TOU_2025_hourly.csv`
  - External hourly TOU price input with columns
    `timestamp,price_usd_per_mwh`.
- `inputs/CHN_Nanjing_PV_6MWp_hourly.csv`
  - External hourly PV forecast input with columns `timestamp,power_kw`.
- `run_energyplus_nanjing.ps1`
  - Lightweight PowerShell runner for EnergyPlus.
- `docs/model_manifest.md`
  - File inventory and model assumptions.
- `docs/nanjing_tes_pv_price_energyplus_model.md`
  - Current model description, cooling-system logic, validation result, and
    warning status.

## Important Boundary

EnergyPlus consumes the epJSON model and EPW weather file directly. The TOU price
and PV CSV files are preserved as external scenario inputs for a future controller
or post-processing layer. They are not embedded into the EnergyPlus physics model
and do not change the building simulation unless a controller explicitly reads
them and writes actions.

## Run

EnergyPlus 23.1 must be installed separately. Run from this directory:

```powershell
.\run_energyplus_nanjing.ps1 -EnergyPlusExe "C:\Path\To\EnergyPlusV23-1-0\energyplus.exe"
```

The runner validates that the model, weather, price, and PV input files exist and
that the CSV headers match the expected schema. Output is written to:

```text
out/energyplus_nanjing/
```

## Timestep

The current model has been validated at 15-minute resolution:

```text
Timestep.number_of_timesteps_per_hour = 4
```

The latest validation completed successfully with 1 expected sizing warning and
0 severe errors. See `docs/nanjing_tes_pv_price_energyplus_model.md` for details.
