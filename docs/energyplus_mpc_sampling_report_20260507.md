# EnergyPlus MPC Sampling Report 2026-05-07

## Summary

- Samples root: `results\energyplus_mpc_sampling_20260507`
- Rows: `805920`
- Cases: `23`
- Adoption ready: `True`

This report treats sampling outputs as parameter-identification data. Identification-only perturbations are not normal operating conclusions.

## Matrix Completion

- Manifest rows: `23`
- EnergyPlus runtime cases required: `22`
- EnergyPlus runtime cases completed: `22`
- Identification-only rows: `22`

## Metrics

| rows | validation_cvrmse | validation_mae | score | model | target | threshold | loss_per_h |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 689880 | 0.04427757151509482 | 69.43773182053185 | 0.04427757151509482 | chiller_power | chiller_electricity_kw | 0.15 |  |
| 142090 | 1.0238613879356355 | 1196.5814716451046 | 1.0238613879356355 | tes_discharge_response | abs(tes_use_side_kw) |  |  |
| 148187 | 0.12142821803468563 | 48.84988207221243 | 0.12142821803468563 | tes_charge_response | abs(tes_source_side_kw) |  |  |
| 805897 | 0.024573773808373972 | 0.18662382999002053 | 0.024573773808373972 | zone_temperature_safety | zone_temp_next_c |  |  |
| 805897 |  | 0.010078283649732966 | 0.010078283649732966 | soc_24h_rollout | soc | 0.03 | -0.0 |
| 303680 |  | 0.016800579557428863 | 0.9831994204425711 | tes_direction | direction | 0.95 |  |

## Failure Reasons / Limits

- None

## Thesis Impact

No thesis draft update is required until these identified models are accepted as thesis methods or conclusions.
