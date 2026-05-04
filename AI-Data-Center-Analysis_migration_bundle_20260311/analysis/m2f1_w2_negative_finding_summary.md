# W2 负面发现：MPC 在 Jiangsu TOU + 数据中心物理参数下未展现 cost saving

**日期**：2026-05-04
**实验范围**：W2 trainlike + W2-B official_ood 双 batch（共 6 cells；baseline monitor 为 35041 rows，MPC monitor 为 35040 rows）

## 1. 实验设计

W2 以同一套 M2-F1 wrapper 链对比 TES-MPC 与无 TES baseline 的全年效果。三类算法保持一致：

- `baseline_neutral`：`evaluate_m2_rule_baseline.py --policy neutral`，TES valve 永远为 0，作为 no-TES baseline。
- `heuristic`：`m2_tes_mpc_oracle.py --solver heuristic`，规则式 TES 调度。
- `mpc_milp`：`m2_tes_mpc_oracle.py --solver milp`，24h rolling-horizon MILP oracle。

两档负载设计：

- `trainlike`：`DRL_DC_training.epJSON`，`ITE_Set=0.45`，低负载训练式工况。
- `official_ood`：`DRL_DC_evaluation.epJSON`，`ITE_Set=1.0`，高负载 OOD stress 工况。

六个 cell 均使用相同 PVSignal + PriceSignal + TESValve 对照口径、相同 Nanjing weather / Jiangsu TOU / 6 MWp PV 输入和 4 step/h 分辨率；差异仅来自负载设计和控制策略。

## 2. 主表

| design | algorithm | cost_usd_total | pue_avg | comfort_violation_pct | total_load_mwh | SCR_pct | mode_switches |
|:--|:--|--:|--:|--:|--:|--:|--:|
| trainlike | baseline_neutral | 6993059.4375 | 1.3237 | 0.2911 | 78260.4194 | 100.0000 | N/A |
| trainlike | heuristic | 7371878.6806 | 1.4121 | 4.5377 | 83535.6946 | 100.0000 | 3231 |
| trainlike | mpc_milp | 7375161.6760 | 1.4147 | 7.1005 | 83711.5960 | 100.0000 | 5309 |
| official_ood | baseline_neutral | 14206633.4598 | 1.2119 | 0.0200 | 159232.1029 | 100.0000 | N/A |
| official_ood | heuristic | 14354248.1249 | 1.2326 | 2.6684 | 162010.6007 | 100.0000 | 3166 |
| official_ood | mpc_milp | 14310199.8762 | 1.2302 | 4.6946 | 161734.9529 | 100.0000 | 5578 |

## 3. 物理根因（按重要性排序）

1. **MPC 充冷阶段的能耗 > TOU 套利收益**：PUE 相对 baseline 退化约 +0.02 到 +0.09，绝对能耗增加约 +2500 到 +6500 MWh/年。trainlike 下额外负载约 +5275 到 +5451 MWh/年；official_ood 下额外负载约 +2503 到 +2778 MWh/年。
2. **MPC 牺牲 comfort**：trainlike MILP comfort violation 为 7.10%，official_ood MILP 为 4.69%；baseline 在两种负载下分别为 0.29% 和 0.02%，均显著更稳。
3. **TES 套利空间不足**：Jiangsu TOU peak 190 / valley 29 USD/MWh，约 6.5x 价差；扣除 chiller 部分负载效率损失、水罐热损失、充冷阶段过热补偿后，当前 TES/MPC 配置净亏。
4. **PV 自消纳已饱和**：PV 6 MWp 峰值约 5060 kW 始终低于负载（trainlike 诊断最低负载约 6970 kW，official_ood baseline 最低负载约 17887 kW），SCR 全部为 100%；TES 无法进一步提升 SCR。

## 4. 唯一 silver lining：heuristic 在 official_ood 下 mechanism_gate PASS

heuristic 在高负载下 `sign_rate=1.0`、`ΔSOC_prepeak=+0.232`、`ΔSOC_peak=-0.506`、`comfort=2.67%`、`mechanism_gate=True`。这说明 TES 的机理方向物理可达：低价/峰前可充冷，高价可放冷，且 comfort 没有越过 5% gate。但 cost 维度仍输给 baseline，且是三者中成本最高。

## 5. 论文叙事重组

- **§4.1 工况边界讨论**：在当前 reward + Jiangsu TOU + 1400 m^3 TES + 6 MWp PV + Nanjing 气象配置下，MPC 不展现 cost saving。baseline ALL-WIN 是真实物理结果，不应修饰为脚本或 schema 问题。
- **§4.2 MPC 在 forecast robustness 维度的优势**：复用 W1-3 sigma-curve 数据。MILP 在 sigma <= 0.10 完全鲁棒，sigma=0.20 出现拐点失守；`persistence_h` 表现为利用率衰减而非方向衰减。
- **§4.3 future work**：扩大 TOU 谷峰差到 10x+；引入 chiller 部分负载效率模型；显式建模水罐热损失项；做多站点泛化；引入 stochastic MPC + chance constraint。

## 6. 数据文件清单

- W2 trainlike: `analysis/m2f1_w2_scenario_compare_20260503_232820.csv`
- W2 trainlike: `analysis/m2f1_w2_scenario_compare_20260503_232820.md`
- W2 trainlike validation: `analysis/m2f1_w2_scenario_validation_20260503_232820.json`
- W2-B official_ood: `analysis/m2f1_w2b_scenario_compare_20260504_054338.csv`
- W2-B official_ood: `analysis/m2f1_w2b_scenario_compare_20260504_054338.md`
- W2-B official_ood validation: `analysis/m2f1_w2b_scenario_validation_20260504_054338.json`
- PV 诊断: `analysis/m2f1_w2_pv_diagnostic_20260503_232820.json`
- PV 诊断: `analysis/m2f1_w2b_pv_diagnostic_20260504_054338.json`
- 汇总索引: `analysis/m2f1_mpc_oracle_summary_202605.csv`
- 汇总索引: `analysis/m2f1_mpc_oracle_summary_202605.json`
- 工具: `tools/build_w2_scenario_summary.py`
- 工具: `tools/run_w2_scenario_batch.ps1`
- 工具: `tools/run_w2b_scenario_batch.ps1`
