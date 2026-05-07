# robust_base_cp20_h6_mpc_tes

- Category: `Robustness`
- Raw run directory: `results\china_tou_dr_matrices_20260506\raw\robust_base_cp20_h6_mpc_tes`

## Key Metrics

| Metric | Value |
|---|---:|
| Controller | mpc |
| Steps | 2880 |
| Total cost CNY | 1,311,164.40 |
| Grid import kWh | 14,272,150.99 |
| Peak grid kW | 21,090.00 |
| Temp violation degree-hours | 0.0000 |
| Fallback count | 0 |
| Solve time p95 s | 0.2339 |
| Final SOC | 0.1500 |
| TES charge kWh_th | 87,243.37 |
| TES discharge kWh_th | 75,564.21 |
| DR event count | 0 |

## Analysis

- 该 case 的月总成本为 1,311,164.40 CNY，峰值购电为 21,090.00 kW。
- 温度违约为 0，当前代理模型下满足温度约束。
- 求解过程中未触发 fallback。
- 与配对场景 `robust_base_cp20_h6_mpc_no_tes` 相比，`mpc_no_tes -> mpc` 的 TES 增量为 节省 3,158.81 CNY/月。

## Figures

### Grid/PV/power trace

![Grid/PV/power trace](01_power_grid_pv.png)

### TES charge/discharge and SOC

![TES charge/discharge and SOC](02_tes_soc_operation.png)

### Temperature constraints

![Temperature constraints](03_temperature_constraints.png)

### Tariff, critical-peak/fallback flags, and solver time

![Tariff, critical-peak/fallback flags, and solver time](04_tariff_solver_flags.png)
