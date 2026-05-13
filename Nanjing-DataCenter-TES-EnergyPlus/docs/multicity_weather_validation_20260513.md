# Multi-Weather MPC Validation - 2026-05-13

## Scope

This note records the Beijing and Guangzhou annual EnergyPlus-MPC validation
run on branch `codex/fix-energyplus-mpc-temp-safety`.

The validation changes only the EPW weather file. The EnergyPlus model remains
`model/Nanjing_DataCenter_TES.epJSON`, and the external electricity price and
PV inputs remain the Jiangsu/Nanjing inputs. Therefore these runs test weather
robustness and temperature safety, not city-specific tariff/PV economics.

## Weather Inputs

| City | EPW file | Station header | Source |
| --- | --- | --- | --- |
| Beijing | `weather/CHN_BJ_Beijing-Capital.Intl.AP.545110_TMYx.2009-2023.epw` | `Beijing-Capital.Intl.AP`, WMO `545110`, `40.08000,116.5850` | Climate.OneBuilding China TMYx 2009-2023 |
| Guangzhou | `weather/CHN_GD_Guangzhou.592870_TMYx.2009-2023.epw` | `Guangzhou`, WMO `592870`, `23.20990,113.4822` | Climate.OneBuilding China TMYx 2009-2023 |

Download pages:

- `https://climate.onebuilding.org/WMO_Region_2_Asia/CHN_China/BJ_Beijing/CHN_BJ_Beijing-Capital.Intl.AP.545110_TMYx.2009-2023.zip`
- `https://climate.onebuilding.org/WMO_Region_2_Asia/CHN_China/GD_Guangdong/CHN_GD_Guangzhou.592870_TMYx.2009-2023.zip`

## Method

For each city, an annual `no_control` run was executed first. Its 15-minute
monitor output was converted into a city-specific baseline forecast CSV:

- `results/multicity_tempfix_baselines_20260513/beijing_no_control_timeseries_15min.csv`
- `results/multicity_tempfix_baselines_20260513/guangzhou_no_control_timeseries_15min.csv`

The subsequent annual MPC run used the matching city weather and matching
city-specific baseline forecast. This avoids driving the MPC with Nanjing
weather/load proxy data while EnergyPlus is running under Beijing or Guangzhou
weather.

## Commands

```powershell
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller no_control --max-steps 35040 --record-start-step 0 --weather Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_BJ_Beijing-Capital.Intl.AP.545110_TMYx.2009-2023.epw --selected-output-root results/multicity_tempfix_beijing_no_control_20260513 --raw-output-dir Nanjing-DataCenter-TES-EnergyPlus/out/multicity_tempfix_beijing_no_control_20260513
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller mpc --max-steps 35040 --record-start-step 0 --weather Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_BJ_Beijing-Capital.Intl.AP.545110_TMYx.2009-2023.epw --baseline-timeseries results/multicity_tempfix_baselines_20260513/beijing_no_control_timeseries_15min.csv --selected-output-root results/multicity_tempfix_beijing_mpc_20260513 --raw-output-dir Nanjing-DataCenter-TES-EnergyPlus/out/multicity_tempfix_beijing_mpc_20260513
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller no_control --max-steps 35040 --record-start-step 0 --weather Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_GD_Guangzhou.592870_TMYx.2009-2023.epw --selected-output-root results/multicity_tempfix_guangzhou_no_control_20260513 --raw-output-dir Nanjing-DataCenter-TES-EnergyPlus/out/multicity_tempfix_guangzhou_no_control_20260513
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller mpc --max-steps 35040 --record-start-step 0 --weather Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_GD_Guangzhou.592870_TMYx.2009-2023.epw --baseline-timeseries results/multicity_tempfix_baselines_20260513/guangzhou_no_control_timeseries_15min.csv --selected-output-root results/multicity_tempfix_guangzhou_mpc_20260513 --raw-output-dir Nanjing-DataCenter-TES-EnergyPlus/out/multicity_tempfix_guangzhou_mpc_20260513
```

## Results

| City | Controller | Steps | Severe | Fallback | Facility GWh | Max zone temp C | >27C ratio | >27C hours | >30C hours | Warnings |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Beijing | no_control | 35040 | 0 | 0 | 79.513 | 29.188 | 10.705% | 937.75 | 0.00 | 4 |
| Beijing | mpc | 35040 | 0 | 0 | 79.472 | 29.643 | 0.731% | 64.00 | 0.00 | 22 |
| Guangzhou | no_control | 35040 | 0 | 0 | 87.923 | 29.152 | 8.405% | 736.25 | 0.00 | 8 |
| Guangzhou | mpc | 35040 | 0 | 0 | 88.205 | 29.470 | 1.652% | 144.75 | 0.00 | 25 |

The temperature safety result is reasonable under the current acceptance
criterion: both MPC runs remain below 5% annual timesteps above 27C, and both
have zero hours above 30C. Guangzhou annual facility energy is higher than
Beijing under both no-control and MPC cases, consistent with the hotter and
more humid weather boundary.

## Known Limits

- The building model is still the Nanjing data-center model; only EPW weather
  is varied.
- Price and PV remain Jiangsu/Nanjing inputs, so cost comparisons are not
  city-specific tariff/PV conclusions.
- The MPC temperature guard is an outer safety layer, not an internal optimizer
  temperature constraint.
- Cooling tower warnings remain in MPC runs: Beijing has `cooling_tower_air_flow_ratio_failed=3` and `tower_range_out_of_range=3`; Guangzhou has `cooling_tower_air_flow_ratio_failed=8` and `tower_range_out_of_range=3`.
