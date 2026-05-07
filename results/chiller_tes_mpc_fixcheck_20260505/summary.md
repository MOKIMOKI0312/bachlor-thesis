# Chiller TES MPC Fixcheck Summary - 2026-05-05

## Verification Status

- `pytest -q`: passed, 20 tests.
- 24 h smoke runs completed for no-TES, RBC, and MPC.
- 7-day MPC candidate completed with `steps=672` and `horizon_steps=96`.
- Peak-cap sensitivity completed all 4 scenario runs and saved aggregate files. PV-priority sensitivity completed 14 of 16 runs before the 20 minute command timeout.
- Full terminal/SOC Cartesian matrix is declared in config but not fully executed here because it contains 108 closed-loop cases including 672-step runs. Two representative endpoint cases were executed.

## Core Smoke Results

### `smoke/fixcheck_no_tes`
- steps: 96
- total_cost: 4073.021
- peak_grid_kw: 3090.000
- final_soc_after_last_update: 0.5000; soc_delta: 0.0000
- TES charge/discharge kWh_th: 0.000 / 0.000
- charge/discharge/idle steps: 0 / 0 / 96
- fallback_count: 0; physical_consistency_violation_count: 0; signed_valve_violation_count: 0
- weighted TES charge/discharge price: nan / nan

### `smoke/fixcheck_rbc`
- steps: 96
- total_cost: 4037.145
- peak_grid_kw: 3090.000
- final_soc_after_last_update: 0.1483; soc_delta: -0.3517
- TES charge/discharge kWh_th: 6929.702 / 11434.444
- charge/discharge/idle steps: 32 / 19 / 45
- fallback_count: 0; physical_consistency_violation_count: 0; signed_valve_violation_count: 0
- weighted TES charge/discharge price: 29.0 / 165.0

### `smoke/fixcheck_mpc`
- steps: 96
- total_cost: 3627.889
- peak_grid_kw: 3090.000
- final_soc_after_last_update: 0.8500; soc_delta: 0.3500
- TES charge/discharge kWh_th: 7458.570 / 0.000
- charge/discharge/idle steps: 88 / 0 / 8
- fallback_count: 0; physical_consistency_violation_count: 0; signed_valve_violation_count: 0
- weighted TES charge/discharge price: 35.39574098145599 / nan

### `smoke/fixcheck_mpc_7day_rerun`
- steps: 672
- total_cost: 35306.686
- peak_grid_kw: 3090.000
- final_soc_after_last_update: 0.0500; soc_delta: -0.4500
- TES charge/discharge kWh_th: 50884.501 / 49555.635
- charge/discharge/idle steps: 321 / 54 / 297
- fallback_count: 6; physical_consistency_violation_count: 0; signed_valve_violation_count: 0
- weighted TES charge/discharge price: 98.88933777993704 / 136.04966372661983

## Terminal/SOC Representative Results

- `terminal_soc_representative/terminal_soc_24h_low_target`: cost 2753.372, final SOC 0.8226, TES charge/discharge 7149.296/188.666 kWh_th, arbitrage spread 51.46609585774636.
- `terminal_soc_representative/terminal_soc_7day_low_target`: cost 35275.251, final SOC 0.0500, TES charge/discharge 51790.171/50396.034 kWh_th, arbitrage spread 41.11576247159984.

## Partial Sensitivity Coverage

- Peak-cap completed cases: 4 -> peak_cap_partial/peak_cap_peak_cap_kw-, peak_cap_partial/peak_cap_peak_cap_kw-2600, peak_cap_partial/peak_cap_peak_cap_kw-2800, peak_cap_partial/peak_cap_peak_cap_kw-3000.
- Peak-cap completed all 4 scenario runs; `validation_summary.csv` and `validation_summary.json` are saved under `peak_cap_partial/`.
- PV-priority completed cases: 14 -> pv_priority_partial/pv_priority_pv_scale-1_w_spill-0p02, pv_priority_partial/pv_priority_pv_scale-1_w_spill-0p2, pv_priority_partial/pv_priority_pv_scale-1_w_spill-1p0, pv_priority_partial/pv_priority_pv_scale-1_w_spill-5p0, pv_priority_partial/pv_priority_pv_scale-2_w_spill-0p02, pv_priority_partial/pv_priority_pv_scale-2_w_spill-0p2, pv_priority_partial/pv_priority_pv_scale-2_w_spill-1p0, pv_priority_partial/pv_priority_pv_scale-2_w_spill-5p0, pv_priority_partial/pv_priority_pv_scale-3_w_spill-0p02, pv_priority_partial/pv_priority_pv_scale-3_w_spill-0p2, pv_priority_partial/pv_priority_pv_scale-3_w_spill-1p0, pv_priority_partial/pv_priority_pv_scale-3_w_spill-5p0, pv_priority_partial/pv_priority_pv_scale-5_w_spill-0p02, pv_priority_partial/pv_priority_pv_scale-5_w_spill-0p2.
- PV-priority completed 14 of 16 scenario runs; missing completed summaries for `pv_scale=5, w_spill=1.0` and `pv_scale=5, w_spill=5.0` due command timeout before the matrix finished.

## Interpretation

- Physical consistency is now enforced and measured: completed runs report zero supply-deficit violations.
- The 24 h nominal MPC still charges TES but does not discharge, ending at SOC 0.85; this should not be used alone to claim TES arbitrage.
- The 7-day MPC candidate does charge and discharge TES, with discharge weighted average price higher than charge weighted average price; this is the stronger candidate for a TES arbitrage statement.
- Peak-cap sensitivity shows the soft cap can enforce 3000/2800/2600 kW peaks in completed 24 h runs, with higher cost as the cap tightens; this is stronger evidence than demand-charge-only tuning.
- PV-priority results remain exploratory: 14/16 cases completed, but large PV-scale cases still show high PV spill and only limited TES charging during surplus periods.

## Output Files

- `completed_run_summary.csv`: one row per completed run copied into this result folder.
- `smoke/`: 24 h smoke outputs and 7-day candidate outputs copied from `runs/fixcheck`.
- `terminal_soc_representative/`: representative endpoint terminal/SOC runs.
- `peak_cap_partial/` and `pv_priority_partial/`: partial sensitivity outputs from timed commands.
