# W2 Scenario Comparison (20260503_232820)

## Section 4.1 TES energy contribution

| algorithm        |   total_steps |   cost_usd_total |   total_load_mwh |   pue_avg |   comfort_violation_pct |   cost_saving_vs_baseline_usd |   cost_saving_vs_baseline_pct |   pue_improvement_vs_baseline |
|:-----------------|--------------:|-----------------:|-----------------:|----------:|------------------------:|------------------------------:|------------------------------:|------------------------------:|
| baseline_neutral |         35041 |     6993059.4375 |       78260.4194 |    1.3237 |                  0.2911 |                        0.0000 |                        0.0000 |                        0.0000 |
| heuristic        |         35040 |     7371878.6806 |       83535.6946 |    1.4121 |                  4.5377 |                  -378819.2430 |                       -5.4171 |                       -0.0884 |
| mpc_milp         |         35040 |     7375161.6760 |       83711.5960 |    1.4147 |                  7.1005 |                  -382102.2385 |                       -5.4640 |                       -0.0910 |

## Section 4.2 PV self-consumption comparison

| algorithm        |   pv_total_gen_mwh |   pv_consumed_mwh |   self_consumption_rate_pct |   pv_load_coverage_pct |   grid_import_mwh |   grid_export_mwh |   self_consumption_uplift_vs_baseline_pp |
|:-----------------|-------------------:|------------------:|----------------------------:|-----------------------:|------------------:|------------------:|-----------------------------------------:|
| baseline_neutral |          7143.3519 |         7143.3519 |                    100.0000 |                 9.1277 |        71117.0675 |            0.0000 |                                   0.0000 |
| heuristic        |          7143.3519 |         7143.3519 |                    100.0000 |                 8.5513 |        76392.3427 |            0.0000 |                                   0.0000 |
| mpc_milp         |          7143.3519 |         7143.3519 |                    100.0000 |                 8.5333 |        76568.2441 |            0.0000 |                                   0.0000 |

## MPC mechanism diagnostics (MPC cells only)

| algorithm        | sign_rate          | dsoc_prepeak        | dsoc_peak           | mode_switches   | mechanism_gate_pass   |
|:-----------------|:-------------------|:--------------------|:--------------------|:----------------|:----------------------|
| baseline_neutral | N/A                | N/A                 | N/A                 | N/A             | N/A                   |
| heuristic        | 1.0                | 0.24109745000799496 | -0.4977936384008646 | 3231            | False                 |
| mpc_milp         | 0.9721056529252037 | 0.21190882164440797 | -0.5910972940784266 | 5309            | False                 |
