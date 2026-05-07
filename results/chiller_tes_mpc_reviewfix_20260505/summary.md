# Chiller TES MPC Review-Fix Summary - 2026-05-05

## Verification

- `pytest -q`: passed, 21 tests.
- Stable 7-day no-TES / RBC / MPC runs completed with `steps=672`.
- Review-fix MPC uses `horizon_steps=48` for reproducible 7-day runtime; this is a 12 h receding horizon.
- All included runs have `fallback_count = 0`, `physical_consistency_violation_count = 0`, `signed_valve_violation_count = 0`, and `temp_violation_degree_hours = 0`.
- Signed valve is now flow-consistent: `u_signed = q_ch_tes/q_ch_max - q_dis_tes/q_dis_max`.

## 7-Day Baseline Matrix

### `7day_baselines/reviewfix_7day_no_tes_direct`
- controller: no_tes; steps: 672; total_cost: 24213.078; peak_grid_kw: 2633.250
- fallback/temp/physical/signed violations: 0 / 0.000000 degree-h / 0 / 0
- TES charge/discharge: 0.000 / 0.000 kWh_th; final SOC: 0.5000; SOC delta: 0.0000
- charge/discharge weighted price: nan / nan; arbitrage spread: nan

### `7day_baselines/reviewfix_7day_rbc_smooth`
- controller: rbc; steps: 672; total_cost: 23954.473; peak_grid_kw: 2576.550
- fallback/temp/physical/signed violations: 0 / 0.000000 degree-h / 0 / 0
- TES charge/discharge: 37012.500 / 27562.500 kWh_th; final SOC: 0.5552; SOC delta: 0.0552
- charge/discharge weighted price: 41.638297872340424 / 163.62857142857143; arbitrage spread: 121.99027355623102

### `7day_baselines/reviewfix_7day_mpc_h48`
- controller: mpc; steps: 672; total_cost: 12585.501; peak_grid_kw: 3090.000
- fallback/temp/physical/signed violations: 0 / 0.000000 degree-h / 0 / 0
- TES charge/discharge: 10200.302 / 13240.128 kWh_th; final SOC: 0.1500; SOC delta: -0.3500
- charge/discharge weighted price: 30.622810349657662 / 186.07828496161812; arbitrage spread: 155.45547461196045

## 24 h Smoke Interpretation

### `24h_smoke/reviewfix_24h_no_tes`
- controller: no_tes; steps: 96; total_cost: 2955.927; peak_grid_kw: 2633.250
- fallback/temp/physical/signed violations: 0 / 0.000000 degree-h / 0 / 0
- TES charge/discharge: 0.000 / 0.000 kWh_th; final SOC: 0.5000; SOC delta: 0.0000
- charge/discharge weighted price: nan / nan; arbitrage spread: nan

### `24h_smoke/reviewfix_24h_rbc`
- controller: rbc; steps: 96; total_cost: 3002.303; peak_grid_kw: 2576.550
- fallback/temp/physical/signed violations: 0 / 0.000000 degree-h / 0 / 0
- TES charge/discharge: 5287.500 / 3937.500 kWh_th; final SOC: 0.5091; SOC delta: 0.0091
- charge/discharge weighted price: 41.638297872340424 / 163.62857142857143; arbitrage spread: 121.99027355623102

### `24h_smoke/reviewfix_24h_mpc`
- controller: mpc; steps: 96; total_cost: 1178.017; peak_grid_kw: 2567.404
- fallback/temp/physical/signed violations: 0 / 0.000000 degree-h / 0 / 0
- TES charge/discharge: 11.489 / 5456.143 kWh_th; final SOC: 0.1500; SOC delta: -0.3500
- charge/discharge weighted price: 82.99999999999999 / 191.72354096414665; arbitrage spread: 108.72354096414666

- 24 h MPC is no longer a charge-only case under the review-fix default config, but it remains a smoke check; thesis claims should use the 7-day baseline matrix.

## PV-Rich Contribution

| case       | controller   |   pv_scale |   pv_spill_kwh |   pv_spill_reduction_vs_no_tes_kwh |   tes_charge_during_no_tes_surplus_kwh_th |   tes_discharge_during_no_tes_surplus_kwh_th |   total_cost |
|:-----------|:-------------|-----------:|---------------:|-----------------------------------:|------------------------------------------:|---------------------------------------------:|-------------:|
| pv3_no_tes | no_tes       |          3 |        41206.8 |                              0     |                                         0 |                                          0   |     2543.57  |
| pv3_rbc    | rbc          |          3 |        41070.6 |                            136.231 |                                      2250 |                                       1237.5 |     2590.75  |
| pv3_mpc    | mpc          |          3 |        29337.8 |                          11869     |                                         0 |                                          0   |      278.603 |
| pv5_no_tes | no_tes       |          5 |        80458.6 |                              0     |                                         0 |                                          0   |     2382.34  |
| pv5_rbc    | rbc          |          5 |        80302   |                            156.631 |                                      2250 |                                       1237.5 |     2428.92  |
| pv5_mpc    | mpc          |          5 |        67178.4 |                          13280.2   |                                         0 |                                          0   |      119.205 |

- PV spill reduction is now reported relative to no-TES surplus windows. TES contribution is credible only where TES charging occurs during those no-TES surplus windows.
- In the current PV-rich MPC cases, spill is reduced but TES charging during no-TES surplus windows is still zero. Therefore these runs do not yet prove that TES is absorbing surplus PV; this remains a limitation or follow-up experiment.

## Peak-Cap Contribution

| case            | controller   |   peak_cap_kw |   peak_grid_kw |   peak_reduction_vs_no_tes_kw |   no_tes_violation_window_hours |   tes_discharge_during_no_tes_peak_window_kwh_th |   tes_charge_during_no_tes_peak_window_kwh_th |   peak_slack_max_kw |   total_cost |
|:----------------|:-------------|--------------:|---------------:|------------------------------:|--------------------------------:|-------------------------------------------------:|----------------------------------------------:|--------------------:|-------------:|
| peak3000_no_tes | no_tes       |          3000 |        2633.25 |                        0      |                            0    |                                             0    |                                       0       |                0    |      2955.93 |
| peak3000_rbc    | rbc          |          3000 |        2576.55 |                       56.7    |                            0    |                                             0    |                                       0       |                0    |      3002.3  |
| peak3000_mpc    | mpc          |          3000 |        2567.4  |                       65.8462 |                            0    |                                             0    |                                       0       |                0    |      1178.02 |
| peak2800_no_tes | no_tes       |          2800 |        2633.25 |                        0      |                            0    |                                             0    |                                       0       |                0    |      2955.93 |
| peak2800_rbc    | rbc          |          2800 |        2576.55 |                       56.7    |                            0    |                                             0    |                                       0       |                0    |      3002.3  |
| peak2800_mpc    | mpc          |          2800 |        2567.4  |                       65.8462 |                            0    |                                             0    |                                       0       |                0    |      1178.02 |
| peak2600_no_tes | no_tes       |          2600 |        2633.25 |                        0      |                            2.75 |                                             0    |                                       0       |               33.25 |      2955.93 |
| peak2600_rbc    | rbc          |          2600 |        2576.55 |                       56.7    |                            2.75 |                                          1237.5  |                                       0       |                0    |      3002.3  |
| peak2600_mpc    | mpc          |          2600 |        2567.4  |                       65.8462 |                            2.75 |                                          4352.52 |                                       2.87234 |                0    |      1178.02 |

- Peak-cap TES contribution is reported against no-TES violation windows for each cap. This separates actual TES discharge timing from mere cost differences.
- The clearest peak-cap evidence is `peak2600_*`, where no-TES violates the cap for 2.75 h and both RBC/MPC remove the slack with TES discharge during that no-TES peak window. At 2800/3000 kW the no-TES case is already below the cap, so those rows are weaker peak-cap evidence.

## Thesis-Ready Interpretation

- The strongest current thesis candidate is the 7-day matrix: all three controllers run stably with no fallback and no temperature violations.
- MPC uses TES in both directions over 7 days, and the reported SOC inventory explains the net storage drawdown.
- Peak-cap and PV-rich claims must be limited to the explicit comparison tables above; do not generalize beyond these scenarios.
- Because the 7-day MPC horizon was reduced to 48 steps for reproducibility, this should be reported as an implementation/runtime tradeoff.

## Review Comment Resolution

- Test package independent reproducibility: addressed by exporting a self-contained review package with current code, tests, input CSVs, result files, diff metadata, and reproduction commands.
- Signed valve and flow consistency: addressed in code and verified in all included runs with `signed_valve_violation_count = 0` and `u_signed = q_ch_tes/q_ch_max - q_dis_tes/q_dis_max`.
- 7-day fallback: addressed for no-TES, RBC, and MPC; all three 672-step runs have `fallback_count = 0`.
- 7-day temperature violations: addressed in the current proxy calibration; all included 7-day runs have `temp_violation_degree_hours = 0`.
- 7-day missing baseline: addressed with no-TES, RBC, and MPC runs in `7day_baselines/`.
- 24 h charge-only behavior: addressed under the review-fix default config; the 24 h MPC smoke run discharges TES, but it also draws down SOC inventory and should remain a smoke check rather than the main thesis result.
- PV and peak-cap TES contribution: peak-cap contribution is supported for the 2600 kW cap case; PV-rich TES contribution is not yet proven because MPC spill reduction occurs without TES charging during no-TES surplus windows.
