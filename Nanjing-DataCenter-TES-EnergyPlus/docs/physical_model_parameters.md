# Physical Model Parameters

This file records EnergyPlus parameters used by the MPC coupling layer.

## EnergyPlus Timing

- Timesteps per hour: `4`
- MPC timestep: `0.25 h`

## TES Object

- Object: `Chilled Water Tank`
- Tank volume: `1400.0 m3`
- Nominal cooling capacity: `9767442.0 W`
- Proxy thermal capacity: `39069.768 kWh_th`
- EMS maximum TES flow: `389.0 kg/s`
- SOC cold temperature: `6.67 C`
- SOC hot temperature: `12.0 C`
- SOC formula: `SOC = (soc_hot_temp_c - tank_avg_temp_c) / (soc_hot_temp_c - soc_cold_temp_c)`

## Control Interface

- Primary actuator: `TES_Set` as `Schedule:Constant / Schedule Value`.
- Identification actuators: `ITE_Set` and `Chiller_T_Set` as `Schedule:Constant / Schedule Value`.
- `TES_Set > 0` enables TES use side discharge.
- `TES_Set < 0` enables TES source side charge.
- MPC signed action mapping: `TES_Set = -clip(q_tes_net / q_tes_abs_max_kw_th, -1, 1)`.

## Required Runtime Variables

- `tes_set_echo`: `TES_Set` / `Schedule Value`
- `ite_set_echo`: `ITE_Set` / `Schedule Value`
- `chiller_t_set_echo`: `Chiller_T_Set` / `Schedule Value`
- `tes_soc`: `TES_SOC_Obs` / `Schedule Value`
- `tes_avg_temp`: `TES_Avg_Temp_Obs` / `Schedule Value`
- `tes_use_avail_echo`: `TES_Use_Avail_Sch` / `Schedule Value`
- `tes_source_avail_echo`: `TES_Source_Avail_Sch` / `Schedule Value`
- `chiller_avail_echo`: `Chiller_Avail_Sch` / `Schedule Value`
- `tes_use_heat_transfer_w`: `Chilled Water Tank` / `Chilled Water Thermal Storage Use Side Heat Transfer Rate`
- `tes_source_heat_transfer_w`: `Chilled Water Tank` / `Chilled Water Thermal Storage Source Side Heat Transfer Rate`
- `tes_tank_temp_c`: `Chilled Water Tank` / `Chilled Water Thermal Storage Final Tank Temperature`
- `zone_temp_c`: `DataCenter ZN` / `Zone Air Temperature`
- `outdoor_drybulb_c`: `Environment` / `Site Outdoor Air DryBulb Temperature`
- `outdoor_wetbulb_c`: `Environment` / `Site Outdoor Air WetBulb Temperature`
- `chiller_electricity_w`: `90.1-2019 WaterCooled  Centrifugal Chiller 0 1230tons 0.6kW/ton` / `Chiller Electricity Rate`
- `chiller_cooling_w`: `90.1-2019 WaterCooled  Centrifugal Chiller 0 1230tons 0.6kW/ton` / `Chiller Evaporator Cooling Rate`

## Required Meters

- `facility_electricity_j`: `Electricity:Facility`
- `purchased_electricity_j`: `ElectricityPurchased:Facility`

## Baseline Identification

Source file: `Nanjing-DataCenter-TES-EnergyPlus/out/energyplus_nanjing/timeseries_15min.csv`

- Rows: `35040`
- Facility base load median: `9968.43 kW`
- Non-plant electric load median: `7850.90 kW`
- Cooling proxy median: `6839.67 kW_th`
- Cooling proxy p95: `6865.18 kW_th`
- Outdoor wet-bulb mean: `13.68 C`
- Outdoor wet-bulb amplitude proxy: `13.23 C`
- Chiller fit active points: `32458`
- Chiller fit: `P_chiller = 0.323318 * Q_cooling - 69.97`
- Plant proxy clips the negative intercept to `0.0 kW` for MPC feasibility.
- Baseline TES use/source heat transfer maxima are `0.0 kW`, because the baseline run does not actuate TES.
- Baseline initial SOC from tank temperature is `1.0`.

## Identification Sampling Interface

The sampling layer may actuate the following schedules for parameter identification only:

- `TES_Set`: sampled over `[-1, 1]`.
- `ITE_Set`: sampled over `{0.35, 0.45, 0.55}` to excite IT load.
- `Chiller_T_Set`: sampled over `{0.0, 0.5, 1.0}` to excite chilled-water setpoint behavior.

These identification perturbations are not normal operating conclusions and must be labeled as `identification_only=true` in sampling manifests.

## Modification History

- 2026-05-07: added identification sampling actuators and echo variables. No epJSON file was modified.
