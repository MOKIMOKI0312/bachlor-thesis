# Phase 3 Real Input Sources

Generated target year: 2025.
PVGIS source year: 2019; timestamps are converted from UTC hourly centers to China local interval starts.

PVGIS API endpoint: https://re.jrc.ec.europa.eu/api/v5_3/seriescalc

| location | EPW | EnergyPlus baseline | PVGIS processed CSV | PVGIS radiation DB | slope | azimuth |
|---|---|---|---|---|---:|---:|
| nanjing | `Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_JS_Nanjing.582380_TMYx.2009-2023.epw` | `Nanjing-DataCenter-TES-EnergyPlus/out/energyplus_nanjing/timeseries_15min.csv` | `Nanjing-DataCenter-TES-EnergyPlus/inputs/pvgis/processed/CHN_Nanjing_PVGIS_20MWp_2025_local.csv` | PVGIS-ERA5 | 30 | -5 |
| guangzhou | `Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_GD_Guangzhou.592870_TMYx.2009-2023.epw` | `results/multicity_tempfix_guangzhou_no_control_20260513/no_control/observation.csv` | `Nanjing-DataCenter-TES-EnergyPlus/inputs/pvgis/processed/CHN_Guangzhou_PVGIS_20MWp_2025_local.csv` | PVGIS-ERA5 | 26 | -3 |
| beijing | `Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_BJ_Beijing-Capital.Intl.AP.545110_TMYx.2009-2023.epw` | `results/multicity_tempfix_beijing_no_control_20260513/no_control/observation.csv` | `Nanjing-DataCenter-TES-EnergyPlus/inputs/pvgis/processed/CHN_Beijing_PVGIS_20MWp_2025_local.csv` | PVGIS-ERA5 | 41 | -3 |

All Phase 3 matrix cases use the Jiangsu TOU 2025 hourly price curve:

`Nanjing-DataCenter-TES-EnergyPlus/inputs/Jiangsu_TOU_2025_hourly.csv`
