# Final MPC Implementation Spec

## Summary

The implemented mainline is a deterministic closed-loop MPC package for:

```text
data center cooling proxy
+ chilled-water TES
+ PV generation
+ TOU electricity price
+ deterministic MILP-MPC
+ no-TES baseline
+ closed-loop validation matrix
```

It does not implement RL training, stochastic MPC, new EnergyPlus deep coupling, or a new algorithmic route. EnergyPlus remains the validated physical model/input package; `mpc_v2/` is the controller and replay validation package.

## System Boundary And Variables

- State variables:
  `soc [-]`, `room_temp_c [degC]`, `prev_q_ch_tes_kw_th [kW_th]`, `prev_q_dis_tes_kw_th [kW_th]`.
- Current observed disturbances:
  `timestamp`, `outdoor_temp_c [degC]`, `it_load_kw [kW_e]`, `pv_actual_kw [kW_e]`, `price_currency_per_mwh [currency/MWh]`.
- Forecast variables over `i = 0 ... N-1`:
  `outdoor_temp_forecast_c[i]`, `it_load_forecast_kw[i]`, `pv_forecast_kw[i]`, `price_forecast[i]`, `base_facility_kw[i]`, `base_cooling_kw_th[i]`.
- Executed physical control outputs:
  `q_ch_tes_kw_th [kW_th]`, `q_dis_tes_kw_th [kW_th]`.
- Logged optimization outputs:
  `grid_import_kw`, `pv_spill_kw`, `predicted_room_temp_c`, `predicted_soc`, `solve_status`, `objective_value`, `solve_time_s`.

## Models And MILP

- TES dynamics:

```text
soc[k+1] = (1 - lambda_loss_per_h * dt) * soc[k]
           + eta_ch * q_ch_tes_kw_th[k] * dt / capacity_kwh_th
           - q_dis_tes_kw_th[k] * dt / (eta_dis * capacity_kwh_th)
```

- TES bounds and mutually exclusive charge/discharge are enforced with binary variables:

```text
0 <= q_ch_tes_kw_th[k] <= q_ch_max_kw_th
0 <= q_dis_tes_kw_th[k] <= q_dis_max_kw_th
q_ch_tes_kw_th[k] <= z_ch[k] * q_ch_max_kw_th
q_dis_tes_kw_th[k] <= z_dis[k] * q_dis_max_kw_th
z_ch[k] + z_dis[k] <= 1
```

- Room temperature proxy:

```text
room_temp_c[k+1] = a * room_temp_c[k]
                   + b * outdoor_temp_forecast_c[k]
                   + c * it_load_forecast_kw[k]
                   - d * (base_cooling_kw_th[k] + q_dis_tes_kw_th[k])
```

- Base cooling proxy:

```text
base_cooling_kw_th[k] = alpha_it_to_cooling * it_load_forecast_kw[k]
```

- Facility and grid/PV balance:

```text
base_facility_kw[k] = it_load_forecast_kw[k] * pue_hat(outdoor_temp_forecast_c[k])

grid_import_kw[k] - pv_spill_kw[k]
= base_facility_kw[k]
  + q_ch_tes_kw_th[k] / cop_charge
  - q_dis_tes_kw_th[k] / cop_discharge_equiv
  - pv_forecast_kw[k]
```

- Objective is linear:

```text
sum_k [
    price_forecast[k] * grid_import_kw[k] * dt / 1000
  + w_spill * pv_spill_kw[k] * dt
  + w_cycle * (q_ch_tes_kw_th[k] + q_dis_tes_kw_th[k]) * dt
  + w_temp * (s_temp_low[k] + s_temp_high[k]) * dt
  + w_soc * (s_soc_low[k] + s_soc_high[k])
  + w_switch * (du_ch[k] + du_dis[k])
]
+ w_terminal * (s_terminal_low + s_terminal_high)
```

Temperature, planning SOC, terminal SOC, and action-change absolute values are all linearized with non-negative slack or auxiliary variables. Physical SOC bounds are hard variable bounds.

## Closed-Loop Execution

Each time step:

1. Read current `soc`, `room_temp_c`, and previous TES action.
2. Build an `N`-step forecast from南京 PV/TOU inputs plus synthetic outdoor/IT profiles.
3. Solve the MILP for `controller_type = mpc`, or set zero TES action for `controller_type = no_tes`.
4. Execute only the first action.
5. Update plant state using actual PV/weather/IT/price, not perturbed forecast PV.
6. Write `monitor.csv`, `solver_log.csv`, and `episode_summary.json`.

If the solver returns no usable solution, the fallback action is zero charge and zero discharge. Fallback events are logged and counted.

## Scenarios And Metrics

`mpc_v2/config/scenario_sets.yaml` defines `thesis_core`:

```text
baseline_no_tes
tes_mpc_perfect
tes_mpc_pv_g05
tes_mpc_pv_g10
tes_mpc_pv_g20
hot_week
mild_week
tariff_low
tariff_base
tariff_high
```

PV forecast error uses:

```text
pv_forecast_kw[t] = max(0, pv_actual_kw[t] * (1 + epsilon[t]))
epsilon[t] ~ Normal(0, sigma)
sigma in {0.05, 0.10, 0.20}
```

`episode_summary.json` includes cost, grid energy, PV actual/used/spill energy, PV ratios, IT/facility energy, PUE, temperature violations, SOC bounds, TES charge/discharge/cycles, solver timing, optimal/feasible rates, and fallback count.

## Assumptions

- Price input is treated as `currency/MWh` because the current CSV column is `price_usd_per_mwh`; the implementation does not relabel it as CNY.
- The default horizon is 192 steps at 15 minutes, equal to 48 hours.
- The implemented baseline is no-TES. Rule-based TES is intentionally not included because it was optional and not needed for the minimum deliverable.
- The closed loop is synthetic/replay validation, not EnergyPlus co-simulation.
