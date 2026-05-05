# MPC v2 Closed-Loop Simulation Summary

## Result Folder

This folder freezes the current MPC v2 implementation results:

- `smoke/smoke_no_tes/`: 96-step no-TES smoke run.
- `smoke/smoke_tes_mpc/`: 96-step TES-MPC smoke run.
- `final_mpc_validation/`: 10-scenario `thesis_core` validation matrix.

Each run directory contains:

- `monitor.csv`
- `solver_log.csv`
- `episode_summary.json`

## Smoke Comparison

| Metric | no-TES | TES-MPC | Interpretation |
|---|---:|---:|---|
| Total cost | 46221.61 | 45641.42 | MPC reduced electricity cost by about 1.26%. |
| Grid import kWh | 496328.40 | 496357.23 | Electricity use did not decrease; it increased slightly. |
| Facility energy kWh | 516672.00 | 516700.83 | No physical energy-saving result in this run. |
| PV spill kWh | 0.00 | 0.00 | PV was already fully consumed, so TES did not improve PV self-consumption. |
| PUE avg | 1.1960 | 1.1961 | Average PUE was effectively unchanged and slightly higher under MPC. |
| Temp violation degree-hours | 10.38 | 5.68 | MPC reduced thermal violations but did not eliminate them. |
| Max room temp C | 29.48 | 28.74 | MPC improved the maximum temperature but still exceeded 27 C. |
| TES discharge kWh_th | 0.00 | 51173.66 | MPC actively used TES. |
| TES equivalent cycles | 0.00 | 2.84 | TES was materially cycled. |
| Fallback count | 0 | 0 | No solver fallback was needed. |

## Validation Matrix

The full `thesis_core` matrix completed 10 scenarios. Every scenario ran 96 closed-loop steps with:

- `fallback_count = 0`
- `optimal_rate = 1.0`
- `feasible_rate = 1.0`

Key scenario-level observations:

- `baseline_no_tes` cost was `46221.61`.
- `tes_mpc_perfect`, `tes_mpc_pv_g05`, `tes_mpc_pv_g10`, and `tes_mpc_pv_g20` all produced the same cost, `45641.42`, in this synthetic 96-step setup.
- `hot_week` raised cost and thermal violation degree-hours.
- `mild_week` lowered cost and almost eliminated thermal violations.
- tariff sensitivity changed total cost as expected, but grid energy changed only slightly.

## Conclusion

This simulation reached the TES operation objective: the MPC solved reliably, executed TES charge/discharge actions, respected charge/discharge exclusivity, and kept SOC inside physical bounds.

It partially reached the control objective: it reduced cost and improved temperature violations compared with no-TES.

It did not demonstrate energy saving. Grid import and facility energy were slightly higher under TES-MPC, so the current result should be described as load shifting and cost reduction under TOU pricing, not as physical energy saving.

It also did not demonstrate improved PV utilization, because PV spill was already zero in the no-TES baseline.

## Thesis-Use Recommendation

Use these results as preliminary validation that the MPC framework is operational and can shift TES usage for cost and temperature benefits. Do not claim significant energy saving or PV self-consumption improvement from this run. Stronger thesis claims require scenario tuning or additional experiments where PV surplus, tariff spread, or temperature constraints create clearer differences.
