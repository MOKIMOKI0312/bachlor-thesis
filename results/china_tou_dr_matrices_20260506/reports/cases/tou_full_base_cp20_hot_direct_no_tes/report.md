# tou_full_base_cp20_hot_direct_no_tes

- Category: `TOU full compare`
- Raw run directory: `results\china_tou_dr_matrices_20260506\raw\tou_full_base_cp20_hot_direct_no_tes`

## Key Metrics

| Metric | Value |
|---|---:|
| Controller | no_tes |
| Steps | 2880 |
| Total cost CNY | 1,352,855.33 |
| Grid import kWh | 14,327,130.06 |
| Peak grid kW | 21,011.25 |
| Temp violation degree-hours | 0.0000 |
| Fallback count | 0 |
| Solve time p95 s | 0.0000 |
| Final SOC | 0.5000 |
| TES charge kWh_th | 0.00 |
| TES discharge kWh_th | 0.00 |
| DR event count | 0 |

## Analysis

- 该 case 的月总成本为 1,352,855.33 CNY，峰值购电为 21,011.25 kW。
- 温度违约为 0，当前代理模型下满足温度约束。
- 求解过程中未触发 fallback。

## Figures

### Grid/PV/power trace

![Grid/PV/power trace](01_power_grid_pv.png)

### TES charge/discharge and SOC

![TES charge/discharge and SOC](02_tes_soc_operation.png)

### Temperature constraints

![Temperature constraints](03_temperature_constraints.png)

### Tariff, critical-peak/fallback flags, and solver time

![Tariff, critical-peak/fallback flags, and solver time](04_tariff_solver_flags.png)
