# Phase 3 PV-TES Sizing Assumptions

Version: 2026-05-13

This document freezes the assumptions for Phase 3 PV-TES technical capacity
recommendation. The recommendation is a technical recommended capacity range
for operation-level sensitivity analysis, not CAPEX sizing, LCOE sizing, NPV
optimization, or an economic optimum.

## Research Scope

Phase 3 answers how PV capacity and TES capacity affect:

- critical peak price impact suppression;
- grid-import reduction during explicit critical-peak windows;
- PV self-consumption;
- peak-grid reduction;
- TES marginal-return decline;
- operation-level PV-TES technical recommended capacity range.

The controller boundary is:

```text
Kim-lite relaxed proxy
+ PV capacity sensitivity
+ TES capacity sensitivity
+ explicit critical peak price impact
+ peak / self-consumption / CP suppression metrics
```

For the corrected online MPC+EnergyPlus path, the plant-response boundary is:

```text
MPC forecast inputs:
  EnergyPlus no-control annual boundary + PVGIS + Jiangsu TOU
Plant response:
  EnergyPlus Runtime API co-simulation
  MPC writes TES_Set every 15 min
  EnergyPlus returns zone temperature, TES heat transfer, chiller power, and facility power
```

The EnergyPlus-derived annual boundary is therefore a forecast/baseline input
for the controller. It must not be described as the plant response for the
corrected online MPC+EP sizing matrix.

The phase does not include CAPEX, LCOE, NPV, workload scheduling, RL,
data-driven thermal models, carbon trading, green certificates, EnergyPlus
online economic validation, or strict binary chiller sequencing.

The previous `full_matrix_real_ep_pvgis` result is an EnergyPlus-derived
profile replay matrix. It is useful as a technical screening baseline, but it
is not the final online MPC+EnergyPlus co-simulation matrix.

## PV Capacity Basis

The main PV capacity scan is:

```text
PV = 0, 10, 20, 40, 60 MWp
```

The reference capacity is:

```text
20 MWp
```

The 20 MWp reference is based on public data-center precedent, not a rooftop
area estimate. Apple has publicly reported 20 MW-scale solar photovoltaic
arrays associated with its Maiden, North Carolina data-center energy supply.
Therefore, this study describes the PV resource as:

```text
onsite or nearby behind-the-meter / dedicated PV resource
```

It must not be described as:

```text
rooftop PV
```

Evidence used for this assumption:

- Apple environmental responsibility materials report two 20 MW solar arrays
  associated with the Maiden data center:
  [Apple Environmental Responsibility Report 2014](https://www.apple.com.cn/environment/pdf/Apple_Environmental_Responsibility_Report_2014.pdf).
- A North Carolina Utilities Commission approval reported a 20 MW solar
  photovoltaic facility near Apple's Maiden data center:
  [MacRumors summary of NCUC approval](https://www.macrumors.com/2012/05/17/apple-receives-regulatory-approval-for-20-megawatt-solar-farm-at-north-carolina-data-center/).

The Phase 3 profiles use linear scaling from a 20 MWp reference profile:

```text
pv_target_kw = pv_reference_kw * target_capacity_mwp / 20
```

## TES Capacity Basis

The main TES capacity scan is:

```text
TES = 0, 9, 18, 36, 72 MWh_th
```

The reference capacity is:

```text
18 MWh_th
```

The water-storage conversion basis is:

```text
E_TES,kWh ~= 1.163 * V_m3 * DeltaT_K
```

The 18 MWh_th value is a literature-informed, control-oriented baseline. It is
not an exact engineering design value and should not be interpreted as a final
tank procurement size.

The main experiment keeps TES power fixed:

```text
q_tes_abs_max = 4500 kW_th
```

Therefore, increasing TES capacity primarily changes available duration and SOC
headroom rather than charge/discharge power.

## Critical Peak Price Basis

The main critical peak uplift is:

```text
critical_peak_uplift = 0.2
```

The optional stress-test uplift is:

```text
critical_peak_uplift = 0.5
```

The explicit critical-peak window is:

```text
16:00 <= hour < 20:00
```

The price model is:

```text
price_cp[t] = price_base[t] * (1 + uplift * I_cp[t])
```

where `I_cp[t]` is the explicit critical-peak flag. Phase 3 does not infer
critical-peak hours from price quantiles.

Policy evidence:

- China's National Development and Reform Commission states that localities
  should implement a critical-peak mechanism on top of peak-valley tariffs, and
  that the critical-peak price uplift should in principle be no less than 20%
  above the peak price:
  [NDRC policy interpretation, 2021-08-02](https://www.ndrc.gov.cn/xxgk/jd/jd/202108/t20210802_1292768_ext.html).
- The China Energy Storage Alliance English summary reports the same policy
  direction:
  [CNESA policy summary](https://en.cnesa.org/latest-news/2021/9/5/national-development-and-reform-commission-released-policy-on-time-of-use-power-prices-perfect-peak-valley-electricity-prices-and-establish-peak-electricity-prices).

Interpretation:

```text
delta = 0.2 is the policy anchor.
delta = 0.5 is a stress test and does not represent the default policy value.
```

## Real EPW / PVGIS / EnergyPlus Boundary

The Phase 3 runner requires every configured location to have explicit weather,
load, PV, and price profile paths. Missing profiles generate a missing-data
report and stop the run; locations are not silently skipped.

The current full-year matrix uses three real EPW weather files as the
EnergyPlus weather boundary:

```text
Nanjing:   Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_JS_Nanjing.582380_TMYx.2009-2023.epw
Guangzhou: Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_GD_Guangzhou.592870_TMYx.2009-2023.epw
Beijing:   Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_BJ_Beijing-Capital.Intl.AP.545110_TMYx.2009-2023.epw
```

Annual no-control EnergyPlus outputs are converted into location-specific
load/weather control profiles:

```text
data/locations/nanjing/load_energyplus_2025.csv
data/locations/nanjing/weather_energyplus_2025.csv
data/locations/guangzhou/load_energyplus_2025.csv
data/locations/guangzhou/weather_energyplus_2025.csv
data/locations/beijing/load_energyplus_2025.csv
data/locations/beijing/weather_energyplus_2025.csv
```

PV profiles are generated from PVGIS v5.3 `seriescalc` at the EPW station
coordinates, with:

```text
peakpower = 20000 kW
loss = 14%
optimalangles = 1
radiation database = PVGIS-ERA5
meteo database = ERA5
```

The raw PVGIS timestamps are UTC hourly centers. They are shifted to China local
interval-start time and rewritten to the 2025 tariff year. The processed PV
profiles are:

```text
Nanjing-DataCenter-TES-EnergyPlus/inputs/pvgis/processed/CHN_Nanjing_PVGIS_20MWp_2025_local.csv
Nanjing-DataCenter-TES-EnergyPlus/inputs/pvgis/processed/CHN_Guangzhou_PVGIS_20MWp_2025_local.csv
Nanjing-DataCenter-TES-EnergyPlus/inputs/pvgis/processed/CHN_Beijing_PVGIS_20MWp_2025_local.csv
```

Source manifest:

```text
Nanjing-DataCenter-TES-EnergyPlus/inputs/pvgis/phase3_real_input_manifest.csv
Nanjing-DataCenter-TES-EnergyPlus/inputs/pvgis/phase3_real_input_sources.md
```

All locations use the Jiangsu 2025 TOU price curve:

```text
Nanjing-DataCenter-TES-EnergyPlus/inputs/Jiangsu_TOU_2025_hourly.csv
```

Each weather/load profile currently spans:

```text
2025-01-01 00:00:00 to 2025-12-31 23:45:00
35040 15-minute rows
```

Each PV profile spans:

```text
2025-01-01 00:00:00 to 2025-12-31 23:00:00
8760 hourly rows
```

The annual matrix uses 15 min control steps, so each scenario contains:

```text
365 days * 24 h/day * 4 steps/h = 35040 rows
```

The completed `full_matrix_real_ep_pvgis` matrix is EnergyPlus-derived rather
than pure synthetic data: EnergyPlus supplies the annual weather/load boundary,
PVGIS supplies PV output, and the MPC-style TES dispatch is replayed over those
profiles. It is still a technical screening matrix, not the corrected online
MPC+EnergyPlus sizing matrix. The corrected online path uses the same 15 min
annual horizon, but obtains plant response from EnergyPlus Runtime API
co-simulation; the full 150-case online matrix is still pending.
