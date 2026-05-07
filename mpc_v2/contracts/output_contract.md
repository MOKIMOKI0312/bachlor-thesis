# MPC v1 Output Contract

Each `run_closed_loop.py` run writes one case directory containing:

- `monitor.csv`
- `timeseries.csv`
- `solver_log.csv`
- `events.csv`
- `episode_summary.json`
- `summary.csv`
- `config_effective.yaml`

`timeseries.csv` is currently an alias of `monitor.csv` for downstream compatibility.

## Required Monitor Columns

- Time/state: `timestamp`, `step`, `controller_mode`, `soc`, `soc_after_update`, `room_temp_c`
- Disturbances: `outdoor_temp_c`, `it_load_kw`, `pv_actual_kw`, `price_cny_per_kwh`
- Actions: `q_ch_tes_kw_th`, `q_dis_tes_kw_th`, `q_chiller_kw_th`, `q_load_kw_th`, `plant_power_kw`, `u_ch`, `u_dis`, `u_signed`, `mode_index`
- Results: `grid_import_kw`, `pv_spill_kw`, `step_cost`, `fallback`, `solver_status`

## Required Summary Fields

- `closed_loop_steps`
- `controller_mode`
- `total_cost`
- `energy_cost`
- `grid_import_kwh`
- `peak_grid_kw`
- `pv_actual_kwh`
- `pv_used_kwh`
- `pv_spill_kwh`
- `facility_energy_kwh`
- `cold_station_energy_kwh`
- `it_energy_kwh`
- `pue_avg`
- `initial_soc`
- `final_soc_after_last_update`
- `soc_delta`
- `soc_inventory_delta_kwh_th`
- `soc_min`
- `soc_max`
- `soc_violation_count`
- `tes_charge_kwh_th`
- `tes_discharge_kwh_th`
- `tes_charge_weighted_avg_price`
- `tes_discharge_weighted_avg_price`
- `tes_arbitrage_price_spread`
- `charge_steps`
- `discharge_steps`
- `idle_steps`
- `charge_discharge_switch_count`
- `simultaneous_charge_discharge_count`
- `physical_consistency_violation_count`
- `max_chiller_supply_deficit_kw_th`
- `optimal_rate`
- `feasible_rate`
- `fallback_count`
