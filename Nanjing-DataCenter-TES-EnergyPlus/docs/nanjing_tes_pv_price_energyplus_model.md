# Nanjing TES + PV + Price EnergyPlus Model

## Purpose

This model is a minimal, auditable EnergyPlus package for a Nanjing data center
scenario. It keeps one TES-enabled data center building model, one Nanjing
weather file, one Jiangsu/Nanjing TOU price input, and one Nanjing PV forecast
input.

The EnergyPlus simulation itself uses the epJSON model and EPW weather file.
The price and PV CSV files are external scenario inputs for later controllers,
MPC experiments, or post-processing. They are intentionally not embedded as
EnergyPlus physical objects.

## Files

| Path | Role |
| --- | --- |
| `model/Nanjing_DataCenter_TES.epJSON` | EnergyPlus data center model with chilled-water TES |
| `weather/CHN_JS_Nanjing.582380_TMYx.2009-2023.epw` | Nanjing weather input |
| `inputs/Jiangsu_TOU_2025_hourly.csv` | External hourly TOU electricity price input |
| `inputs/CHN_Nanjing_PV_6MWp_hourly.csv` | External hourly PV forecast input |
| `run_energyplus_nanjing.ps1` | Lightweight runner and input validator |

## Model Configuration

- EnergyPlus version used for validation: 23.1.0.
- Simulation timestep: 15 minutes, `Timestep.number_of_timesteps_per_hour = 4`.
- Run period: calendar year 2024, starting Monday.
- IT load setting: `ITE_Set = 0.45`.
- Main zone: `DATACENTER ZN`.
- TES object: `ThermalStorage:ChilledWater:Mixed`.
- TES EMS path is preserved through `TES_Set`, `TES_SOC_Obs`, and
  `TES_Avg_Temp_Obs`.

## Cooling System Logic

The cooling system is a water-cooled data center plant:

1. IT equipment and internal loads heat the data center zone.
2. The CRAH air loop removes zone heat through a chilled-water cooling coil.
3. The chilled-water loop supplies cold water to the CRAH coil.
4. The electric centrifugal chiller produces chilled water when the loop needs
   active cooling.
5. The chilled-water TES tank is connected to the chilled-water plant and keeps
   its EMS interfaces for future control.
6. The condenser-water loop removes chiller condenser heat.
7. The cooling tower rejects condenser heat to outdoor air using wet-bulb-driven
   evaporative cooling.

This package does not yet include an external MPC controller in the EnergyPlus
run. The TES and EMS interfaces are present so a future controller can write TES
actions.

## Nanjing Cooling Tower Fixes

The source model used a default cooling tower setup that produced many warnings
under Nanjing weather. The validated model applies the following targeted
changes:

- Cooling tower design range temperature is set to `3.0 C`.
- Condenser-water maximum setpoint is raised to `36.0 C`, avoiding impossible
  low condenser-water setpoints during hot and humid hours.
- Cooling tower model type is `YorkCalcUserDefined`.
- The user-defined YorkCalc object keeps the EnergyPlus YorkCalc default
  coefficients but extends the valid operating envelope for Nanjing:
  - maximum inlet air wet-bulb temperature: `32.0 C`
  - minimum range temperature: `0.5 C`
  - maximum water flow rate ratio: `4.0`
- Condenser-side design flow is fixed consistently at `2.95108 m3/s` across:
  - chiller reference condenser fluid flow rate
  - condenser-water loop maximum flow rate
  - condenser-water pump design maximum flow rate
  - cooling tower design water flow rate
- The condenser-water pump control type is `Intermittent`.

These changes remove the cooling tower boundary warnings and the condenser-loop
mass-flow oscillation warning without changing the building zone, IT load, TES
object, or weather file.

## External Inputs

Price input:

```text
inputs/Jiangsu_TOU_2025_hourly.csv
columns: timestamp,price_usd_per_mwh
```

PV input:

```text
inputs/CHN_Nanjing_PV_6MWp_hourly.csv
columns: timestamp,power_kw
```

The runner validates that both files exist and that their headers match this
schema. EnergyPlus does not consume these CSV files directly; they are preserved
for control and economic analysis layers.

## Validation Result

Validated command:

```powershell
.\run_energyplus_nanjing.ps1 -EnergyPlusExe "C:\Users\18430\EnergyPlus-23.1.0\EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64\energyplus.exe"
```

Final validation output:

```text
EnergyPlus Completed Successfully-- 1 Warning; 0 Severe Errors
Timesteps per Hour, 4, 15
```

Remaining warning:

```text
Calculated design heating load for zone=DATACENTER ZN is zero.
```

This is expected for a cooling-dominated data center model and is not a cooling
tower or plant-loop failure.

Cooling tower and plant-loop warning checks after the fix:

```text
Cooling tower air flow ratio failed: 0
Tower approach out of range: 0
Tower range out of range: 0
Wet-bulb out of range: 0
SimHVAC maximum iterations: 0
Severe errors: 0
```

## Current Scope Boundary

This is a clean EnergyPlus model package, not a complete MPC project. The
retained scope is:

- one Nanjing TES-enabled EnergyPlus model
- one Nanjing EPW file
- one Jiangsu/Nanjing TOU price CSV
- one Nanjing PV CSV
- one lightweight runner
- documentation

Future MPC work should start from this package and add a separate controller
layer that reads observations, price, and PV, then writes TES actions through
the preserved EMS interfaces.
