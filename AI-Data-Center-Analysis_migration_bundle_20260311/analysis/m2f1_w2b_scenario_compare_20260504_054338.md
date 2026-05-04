# W2B Scenario Comparison (20260504_054338)

## Section 4.1 TES energy contribution

| algorithm        |   total_steps |   cost_usd_total |   total_load_mwh |   pue_avg |   comfort_violation_pct |   cost_saving_vs_baseline_usd |   cost_saving_vs_baseline_pct |   pue_improvement_vs_baseline |
|:-----------------|--------------:|-----------------:|-----------------:|----------:|------------------------:|------------------------------:|------------------------------:|------------------------------:|
| baseline_neutral |         35041 |    14206633.4598 |      159232.1029 |    1.2119 |                  0.0200 |                        0.0000 |                        0.0000 |                        0.0000 |
| heuristic        |         35040 |    14354248.1249 |      162010.6007 |    1.2326 |                  2.6684 |                  -147614.6651 |                       -1.0391 |                       -0.0207 |
| mpc_milp         |         35040 |    14310199.8762 |      161734.9529 |    1.2302 |                  4.6946 |                  -103566.4164 |                       -0.7290 |                       -0.0184 |

## Section 4.2 PV self-consumption comparison

| algorithm        |   pv_total_gen_mwh |   pv_consumed_mwh |   self_consumption_rate_pct |   pv_load_coverage_pct |   grid_import_mwh |   grid_export_mwh |   self_consumption_uplift_vs_baseline_pp |
|:-----------------|-------------------:|------------------:|----------------------------:|-----------------------:|------------------:|------------------:|-----------------------------------------:|
| baseline_neutral |          7143.3519 |         7143.3519 |                    100.0000 |                 4.4861 |       152088.7510 |            0.0000 |                                   0.0000 |
| heuristic        |          7143.3519 |         7143.3519 |                    100.0000 |                 4.4092 |       154867.2488 |            0.0000 |                                   0.0000 |
| mpc_milp         |          7143.3519 |         7143.3519 |                    100.0000 |                 4.4167 |       154591.6010 |            0.0000 |                                   0.0000 |

## MPC mechanism diagnostics (MPC cells only)

| algorithm        | sign_rate          | dsoc_prepeak        | dsoc_peak           | mode_switches   | mechanism_gate_pass   |
|:-----------------|:-------------------|:--------------------|:--------------------|:----------------|:----------------------|
| baseline_neutral | N/A                | N/A                 | N/A                 | N/A             | N/A                   |
| heuristic        | 1.0                | 0.23214354999363424 | -0.5059317482772647 | 3166            | True                  |
| mpc_milp         | 0.9700027270248159 | 0.20427645061294364 | -0.6438533993193561 | 5578            | False                 |
