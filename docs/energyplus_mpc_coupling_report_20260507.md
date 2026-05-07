# EnergyPlus-MPC Coupling Report 2026-05-07

## Summary

This report records the first online EnergyPlus-MPC co-simulation layer for the Nanjing data center TES model. The implementation runs EnergyPlus through the Python Runtime API, reads runtime state, writes the `TES_Set` schedule actuator, and stores selected auditable results under `results/energyplus_mpc_20260507/`.

This is no longer a pure replay MPC result. The selected 96-step cases are EnergyPlus runtime runs. The optimizer still uses a proxy MPC model, and EnergyPlus remains the physical response model.

## Scope

- Model: `Nanjing-DataCenter-TES-EnergyPlus/model/Nanjing_DataCenter_TES.epJSON`
- Weather: `Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_JS_Nanjing.582380_TMYx.2009-2023.epw`
- Runtime API: `C:/Users/18430/EnergyPlus-23.1.0/EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64/`
- Coupling package: `Nanjing-DataCenter-TES-EnergyPlus/controller/energyplus_mpc/`
- Parameter file: `Nanjing-DataCenter-TES-EnergyPlus/controller/energyplus_mpc/config/energyplus_mpc_params.yaml`
- Physical parameter note: `Nanjing-DataCenter-TES-EnergyPlus/docs/physical_model_parameters.md`

No epJSON file was modified. PV and price are external economic/control inputs only; they are not injected into the EnergyPlus physical model.

## Control Interface

- Runtime actuator: `Schedule:Constant / Schedule Value / TES_Set`
- Runtime observations include `TES_Set`, `TES_SOC_Obs`, `TES_Avg_Temp_Obs`, TES use/source heat transfer, chiller electricity/cooling, facility electricity, zone temperature, and weather.
- Sign convention:
  - Kim-lite `q_tes_net > 0`: charge cold storage.
  - EnergyPlus `TES_Set < 0`: TES source-side charge.
  - EnergyPlus `TES_Set > 0`: TES use-side discharge.
  - Mapping: `TES_Set = -clip(q_tes_net / q_tes_abs_max_kw_th, -1, 1)`.

## Parameter Identification

Static epJSON extraction found:

- TES object: `Chilled Water Tank`
- Tank volume: `1400 m3`
- Nominal TES cooling capacity: `9767442 W`
- EMS maximum TES flow: `389 kg/s`
- SOC temperature mapping: `(12.0 - T_tank_avg) / (12.0 - 6.67)`

Baseline output identification from `timeseries_15min.csv` found:

- Facility base load median: `9968.43 kW`
- Non-plant electric load median: `7850.90 kW`
- Cooling proxy median: `6839.67 kW_th`
- Chiller fit: `P_chiller = 0.323318 * Q_cooling - 69.97`
- Baseline TES heat transfer is zero because the baseline run does not actuate TES.

The online runner defaults to `--record-start-step auto`; for this baseline it selected simulation step `142`, timestamp `2024-01-02 11:30:00`, because the first 96 steps of January 1 had no TES response opportunity.

## Validation Commands

```powershell
python -m pytest -q
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.extract_params --model Nanjing-DataCenter-TES-EnergyPlus/model/Nanjing_DataCenter_TES.epJSON
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.identify_params --timeseries Nanjing-DataCenter-TES-EnergyPlus/out/energyplus_nanjing/timeseries_15min.csv
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller no_control --max-steps 96
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller rbc --max-steps 96
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller mpc --max-steps 96
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_perturbation_profile --max-steps 96
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.audit_results --root results/energyplus_mpc_20260507
```

## Results

Selected results are in `results/energyplus_mpc_20260507/`.

| case | facility kWh | PV-adjusted grid kWh | PV-adjusted cost | peak facility kW | SOC min | SOC final | TES use response count | TES source response count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| no_control | 184392.28 | 183993.15 | 8189.44 | 9571.20 | 1.0000 | 1.0000 | 0 | 0 |
| rbc | 181918.29 | 181519.15 | 7994.71 | 9571.23 | 0.9932 | 1.0000 | 2 | 0 |
| mpc | 171517.75 | 171118.61 | 7583.33 | 7336.20 | 0.8662 | 0.9908 | 26 | 0 |
| perturbation | 176292.98 | 175893.84 | 7838.27 | 9427.20 | 0.8679 | 1.0000 | 10 | 31 |

`TES_Set` echo mismatch count is `0` for all selected cases, so the Runtime API actuator value matches the EnergyPlus reported schedule value. The perturbation case verifies both physical directions: positive `TES_Set` produces use-side response and negative `TES_Set` produces source-side response.

The MPC 96-step case discharged TES but did not command source-side charge in the selected window, so source-side physical response evidence comes from the perturbation case rather than the MPC economic case.

## Audit Result

`python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.audit_results --root results/energyplus_mpc_20260507`

Result: passed.

Audit checks include required files, handle resolution, EnergyPlus exit code, `TES_Set` echo, SOC range, broad zone temperature sanity, MPC fallback count, nonzero TES actions, perturbation use/source response, and severe/cooling-tower warning regressions.

## Thesis Impact

`docs/project_management/毕业设计论文/thesis_draft.tex` was not updated in this version.

Reason: the coupling layer now produces EnergyPlus online closed-loop evidence, but it has not yet been accepted as a thesis conclusion. If these results are used in the thesis, the text must explicitly distinguish EnergyPlus facility electricity, PV-adjusted grid import/cost, EnergyPlus physical TES response, and MPC proxy predictions.

## Known Limits

- The MPC optimization model is still a proxy model adapted from Kim-lite; EnergyPlus provides the measured physical response.
- The current MPC case mainly discharges TES in the selected 96-step window. Charging response is validated by perturbation, not by the economic MPC case.
- The first 96 non-warmup EnergyPlus steps from January 1 are not suitable for TES response validation; the runner therefore defaults to an active chiller window.
- Only `TES_Set` is controlled. Chiller availability, pump mass flow, CRAH fan, and plant setpoints are not directly controlled by the online MPC runner.
