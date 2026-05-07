# Kim-lite Paper-like MPC Final Report - 2026-05-07

## 1. Implemented Modules

Implemented a separate Kim-style paper-like MPC path under `mpc_v2/kim_lite/`:

- `config.py`: typed config loader for time, inputs, TES, plant modes, objective, tariff, and solver settings.
- `model.py`: deterministic input builder and cold-plant/TES MILP.
- `baseline.py`: `direct_no_tes` and `storage_priority` baselines.
- `controller.py`: single-case orchestration and result writing.
- `metrics.py`: monitor, summary, and attribution metrics.
- `plotting.py`: result figure generation.

Public scripts:

- `mpc_v2/scripts/run_kim_lite_closed_loop.py`
- `mpc_v2/scripts/run_kim_lite_matrix.py`
- `mpc_v2/scripts/plot_kim_lite_results.py`

## 2. Relation To Kim et al. 2022

This implementation structurally follows a cold-plant/TES scheduling MPC style:

- Exogenous cooling load, non-plant load, PV, wet-bulb proxy, and electricity price.
- TES SOC as the storage state.
- Chiller plant production and plant electric power.
- Whole-facility grid import accounting.
- Peak epigraph and peak-cap slack extension.

This is a structural reproduction only. It does not claim numeric reproduction of Kim et al. 2022.

## 3. Thesis Context Extensions

Project-specific extensions:

- Nanjing PV replay input from `Nanjing-DataCenter-TES-EnergyPlus/inputs/CHN_Nanjing_PV_6MWp_hourly.csv`.
- Jiangsu TOU price replay input from `Nanjing-DataCenter-TES-EnergyPlus/inputs/Jiangsu_TOU_2025_hourly.csv`.
- Engineering approximation for float/nonfloat TOU split with `alpha_float = 0.8`.
- Critical peak uplift scenario and peak-cap tradeoff scenario.

## 4. Mathematical Formulation

First-version signed net TES proxy:

```text
Q_tes_net[k] = Q_chiller[k] - Q_load[k]

soc[k+1] = (1 - loss_per_h * dt_h) * soc[k]
           + Q_tes_net[k] * dt_h / E_tes_kwh_th
```

Plant mode constraints:

```text
sum_j s[j,k] <= 1
Q_chiller[k] = sum_j nu[j,k]
Q_min[j] * s[j,k] <= nu[j,k] <= Q_max[j] * s[j,k]
```

Grid accounting:

```text
P_grid_pos[k] >= P_nonplant[k] + P_plant[k] - P_pv[k]
P_spill[k] >= P_pv[k] - P_nonplant[k] - P_plant[k]
P_grid_pos[k] <= d_peak
```

Base objective:

```text
min sum_k price[k] * P_grid_pos[k] * dt_h
    + w_peak * d_peak
    + w_soc * SOC_slacks
    + w_terminal * |soc[N] - soc_target|
```

Peak-cap extension:

```text
P_grid_pos[k] <= P_cap + s_peak[k]
s_peak[k] >= 0
```

## 5. Baseline Definitions

- `direct_no_tes`: direct chiller tracking of `Q_load`, TES disabled, SOC constant.
- `mpc_no_tes`: same paper-like optimization path with `Q_chiller = Q_load`, TES disabled.
- `storage_priority_tes`: rule baseline that charges during low-price periods and discharges during high-price periods.
- `paper_like_mpc_tes`: paper-like MPC with signed net TES.

Attribution formulas:

```text
MPC_value = cost(direct_no_tes) - cost(mpc_no_tes)
TES_value = cost(mpc_no_tes) - cost(paper_like_mpc_tes)
RBC_gap   = cost(storage_priority_tes) - cost(paper_like_mpc_tes)
```

## 6. Scenario Matrix

Generated results under `results/kim_lite_repro_20260507/`:

- Phase A: storage-priority vs paper-like MPC.
- Phase B: direct no-TES, MPC no-TES, storage-priority TES, paper-like MPC TES.
- Phase C: flat, base, base+CP20, high-spread, high-spread+CP20 TOU scenarios.
- Phase D: peak-cap ratios `1.00`, `0.99`, `0.97`, `0.95`.
- Phase E: signed valve ramp extension.

## 7. Main Results

Phase A:

- `paper_like_mpc`: cost `19162.4750`, final SOC `0.5000`, SOC range `[0.1500, 0.5000]`.
- `storage_priority`: cost `19219.3182`, final SOC `0.8496`.

Phase B attribution:

```text
MPC_value = 0.0000
TES_value = 182.0938
RBC_gap   = 56.8432
```

Phase C:

- TOU scenarios completed for `mpc_no_tes` and `paper_like_mpc_tes`.
- Representative base+CP20 scenario also ran all four attribution controllers.

Phase D:

- Peak-cap scenarios completed for cap ratios `1.00`, `0.99`, `0.97`, `0.95`.
- Peak-cap runs use `solver_status = optimal_relaxed_modes`; plant mode binaries are relaxed in this phase to prevent solver time-limit stalls while preserving grid/TES/peak-cap accounting.

Phase E:

- Signed valve run completed with `max_signed_du = 0.25` and `signed_valve_violation_count = 0`.

## 8. Does TES Produce Marginal Value?

Under this Kim-lite proxy and Jiangsu/Nanjing replay inputs, TES shows positive marginal value in Phase B:

- `cost(mpc_no_tes) - cost(paper_like_mpc_tes) = 182.0938`
- Paper-like MPC charges at lower weighted price and discharges at higher weighted price.

This conclusion is bounded by the signed-net TES proxy and simplified plant model. It should not be treated as EnergyPlus-coupled proof.

## 9. Negative Results And Limits

- `direct_no_tes` and `mpc_no_tes` have equal cost in Phase B, so no independent MPC value appears without TES under the current simplified plant setup.
- `storage_priority_tes` ends with high final SOC, so comparisons against SOC-neutral MPC need caution.
- Phase D peak-cap uses relaxed mode binaries for robustness; this is acceptable for tradeoff screening, not final plant-mode integer proof.
- The TES model is a Kim-like LTI proxy and does not yet include split charge/discharge efficiencies.
- No PPTX was modified because `PPT_PATH` was not provided.

## 10. PPT Update Statement

Generated storyboard:

```text
docs/ppt_storyboard_kim_lite_20260507.md
```

Generated figure directory:

```text
results/kim_lite_repro_20260507/figures/
```

No local PPT file was edited.
