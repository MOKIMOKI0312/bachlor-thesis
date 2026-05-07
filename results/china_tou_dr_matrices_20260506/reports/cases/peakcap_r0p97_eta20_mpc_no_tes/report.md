# peakcap_r0p97_eta20_mpc_no_tes

- Category: `Peak-cap`
- Raw run directory: `results\china_tou_dr_matrices_20260506\raw\peakcap_r0p97_eta20_mpc_no_tes`

## Key Metrics

| Metric | Value |
|---|---:|
| Controller | mpc_no_tes |
| Steps | 2880 |
| Total cost CNY | 1,329,065.41 |
| Grid import kWh | 14,297,802.49 |
| Peak grid kW | 20,457.30 |
| Temp violation degree-hours | 0.0009 |
| Fallback count | 0 |
| Solve time p95 s | 1.0158 |
| Final SOC | 0.5000 |
| TES charge kWh_th | 0.00 |
| TES discharge kWh_th | 0.00 |
| DR event count | 0 |

## Analysis

- 该 case 的月总成本为 1,329,065.41 CNY，峰值购电为 20,457.30 kW。
- 存在温度约束压力：温度违约为 0.001 degree-hours，最高温度 27.003 C。
- 求解过程中未触发 fallback。
- 与配对场景 `peakcap_r0p97_eta20_mpc_tes` 相比，`mpc_no_tes -> mpc` 的 TES 增量为 节省 720.21 CNY/月。
- Peak-cap 参考峰值为 21,090.00 kW，最大 slack 为 0.000000 kW。

## Figures

### Grid/PV/power trace

![Grid/PV/power trace](01_power_grid_pv.png)

### TES charge/discharge and SOC

![TES charge/discharge and SOC](02_tes_soc_operation.png)

### Temperature constraints

![Temperature constraints](03_temperature_constraints.png)

### Tariff, critical-peak/fallback flags, and solver time

![Tariff, critical-peak/fallback flags, and solver time](04_tariff_solver_flags.png)
