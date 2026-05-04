# M2-F1 Thesis Main Tables

**Date**: 2026-05-04

## Table 1. W2 head-to-head under two load designs

| design | algorithm | cost_usd_total | pue_avg | comfort_violation_pct | total_load_mwh | SCR_pct | mode_switches |
|:--|:--|--:|--:|--:|--:|--:|--:|
| trainlike | baseline_neutral | 6993059.4375 | 1.3237 | 0.2911 | 78260.4194 | 100.0000 | N/A |
| trainlike | heuristic | 7371878.6806 | 1.4121 | 4.5377 | 83535.6946 | 100.0000 | 3231 |
| trainlike | mpc_milp | 7375161.6760 | 1.4147 | 7.1005 | 83711.5960 | 100.0000 | 5309 |
| official_ood | baseline_neutral | 14206633.4598 | 1.2119 | 0.0200 | 159232.1029 | 100.0000 | N/A |
| official_ood | heuristic | 14354248.1249 | 1.2326 | 2.6684 | 162010.6007 | 100.0000 | 3166 |
| official_ood | mpc_milp | 14310199.8762 | 1.2302 | 4.6946 | 161734.9529 | 100.0000 | 5578 |

## Table 2. W1-3 robustness curve summary

| sigma / persistence | sign_rate | dsoc_prepeak | dsoc_peak | pue |
|:--|--:|--:|--:|--:|
| 0.00 (perfect) | 1.0000 | 0.1851 | -0.3246 | 1.26291 |
| 0.05 | 0.9852 ± 0.0128 | 0.1816 ± 0.0035 | -0.3309 ± 0.0150 | 1.26295 ± 0.00012 |
| 0.10 | 0.9827 ± 0.0150 | 0.1656 ± 0.0216 | -0.3125 ± 0.0043 | 1.25444 ± 0.00199 |
| 0.20 | 0.9049 ± 0.1072 | 0.1670 ± 0.0186 | -0.3310 ± 0.0187 | 1.26345 ± 0.00836 |
| persistence_h=1 | 0.9574 | 0.1827 | -0.2345 | 1.25625 |
| persistence_h=4 | 0.9714 | 0.1230 | -0.1931 | 1.26117 |
| persistence_h=12 | 0.9722 | 0.1262 | -0.1936 | 1.26149 |

Gaussian rows report mean ± sample standard deviation across three seeds. The perfect and persistence rows are single-cell measurements.

## Table 3. MILP solve time performance

| dataset | mean (s/step) | max (s/step) | n_cells |
|:--|--:|--:|--:|
| W1-3 (13 cells x 672 step) | 0.0923 | 0.8084 | 13 |
| W2 trainlike (1 cell x 35040 step) | 0.1171 | 0.3449 | 1 |
| W2-B official_ood (1 cell x 35040 step) | 0.1098 | 0.2295 | 1 |

Solve-time statistics are derived from the `tes_mpc_solve_seconds` monitor column.

## §4.1 一句话

在 trainlike (ITE_Set=0.45) 与 official_ood (ITE_Set=1.0) 双工况、Jiangsu TOU + 6 MWp Nanjing PV + 1400 m^3 TES 配置下，no-TES baseline 在 cost / PUE / comfort 三维全胜，MPC 充冷过程的 chiller 损失超过 TOU 套利收益。

## §4.2 一句话

MPC 在 forecast noise 下的鲁棒性是其相对 baseline 的核心优势：MILP 在 σ ≤ 0.10 完全鲁棒（sign_rate 0.983），σ=0.20 出现拐点失守；persistence_h 是利用率衰减而非方向衰减。

## §4.3 future work

扩大 TOU 谷峰差到 10×+；引入 chiller 部分负载效率模型；显式建模水罐热损失；多站点泛化（CAISO 等批发市场）；stochastic MPC + chance constraint。
