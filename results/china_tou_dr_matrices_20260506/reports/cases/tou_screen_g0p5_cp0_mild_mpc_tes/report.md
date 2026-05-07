# tou_screen_g0p5_cp0_mild_mpc_tes

- Category: `TOU screening`
- Raw run directory: `results\china_tou_dr_matrices_20260506\raw\tou_screen_g0p5_cp0_mild_mpc_tes`

## Key Metrics

| Metric | Value |
|---|---:|
| Controller | mpc |
| Steps | 2880 |
| Total cost CNY | 1,224,830.68 |
| Grid import kWh | 13,700,453.01 |
| Peak grid kW | 21,090.00 |
| Temp violation degree-hours | 0.0028 |
| Fallback count | 0 |
| Solve time p95 s | 0.4272 |
| Final SOC | 0.1534 |
| TES charge kWh_th | 23,151.20 |
| TES discharge kWh_th | 21,491.36 |
| DR event count | 0 |

## Analysis

- 该 case 的月总成本为 1,224,830.68 CNY，峰值购电为 21,090.00 kW。
- 存在温度约束压力：温度违约为 0.003 degree-hours，最高温度 27.001 C。
- 求解过程中未触发 fallback。
- 与配对场景 `tou_screen_g0p5_cp0_mild_mpc_no_tes` 相比，`mpc_no_tes -> mpc` 的 TES 增量为 增加成本 741.55 CNY/月。

## Figures

### Grid/PV/power trace

![Grid/PV/power trace](01_power_grid_pv.png)

### TES charge/discharge and SOC

![TES charge/discharge and SOC](02_tes_soc_operation.png)

### Temperature constraints

![Temperature constraints](03_temperature_constraints.png)

### Tariff, critical-peak/fallback flags, and solver time

![Tariff, critical-peak/fallback flags, and solver time](04_tariff_solver_flags.png)
