# Model Manifest

## Purpose

Minimal Nanjing data center EnergyPlus model package with TES, external TOU
price input, external PV forecast input, and selected multi-weather validation
inputs.

## Files

| File | Role | Source |
| --- | --- | --- |
| `model/Nanjing_DataCenter_TES.epJSON` | TES-enabled data center EnergyPlus model | `Data/buildings/DRL_DC_training.epJSON` |
| `weather/CHN_JS_Nanjing.582380_TMYx.2009-2023.epw` | Nanjing weather input | `Data/weather/CHN_JS_Nanjing.582380_TMYx.2009-2023.epw` |
| `weather/CHN_BJ_Beijing-Capital.Intl.AP.545110_TMYx.2009-2023.epw` | Beijing multi-weather validation input | Climate.OneBuilding China TMYx 2009-2023 |
| `weather/CHN_GD_Guangzhou.592870_TMYx.2009-2023.epw` | Guangzhou multi-weather validation input | Climate.OneBuilding China TMYx 2009-2023 |
| `inputs/Jiangsu_TOU_2025_hourly.csv` | External hourly TOU price input | `Data/prices/Jiangsu_TOU_2025_hourly.csv` |
| `inputs/CHN_Nanjing_PV_6MWp_hourly.csv` | External hourly PV forecast input | `Data/pv/CHN_Nanjing_PV_6MWp_hourly.csv` |
| `run_energyplus_nanjing.ps1` | Lightweight EnergyPlus runner | new cleanup runner |

## Model Facts

- Contains `ThermalStorage:ChilledWater:Mixed`.
- Contains TES EMS actuator/sensor path through `TES_Set`, `TES_SOC_Obs`,
  and `TES_Avg_Temp_Obs`.
- Uses source training load setting `ITE_Set = 0.45`.
- Current EnergyPlus timestep is 15 minutes:
  `number_of_timesteps_per_hour = 4`.
- Condenser-water loop and cooling tower are configured for Nanjing weather using
  a user-defined YorkCalc tower performance object and fixed condenser-side
  design flow consistency across chiller, pump, loop, and tower.
- The default weather remains Nanjing. Beijing and Guangzhou EPW files are
  retained for multi-weather validation of the same data-center model, not as
  separate calibrated city-specific building models.
- The TOU price and PV files are preserved as controller/post-processing inputs,
  not embedded EnergyPlus physical inputs.

## Removed Scope

Historical RL/MPC code, Sinergym wrappers, training jobs, analysis outputs,
large run directories, extra PV files, extra price files, and backup epJSON
files are intentionally removed from this minimal package. The retained Beijing
and Guangzhou EPW files are the explicit multi-weather validation exceptions.
