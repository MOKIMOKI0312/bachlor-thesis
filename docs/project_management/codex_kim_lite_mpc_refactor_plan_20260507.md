# Codex 执行计划：从当前复杂 MPC 收束到 Kim et al. 2022 风格 paper-like MPC

版本：2026-05-07
目标：不要继续在当前复杂 MPC 上堆功能。新建一个清晰、可复现、可写论文的 `paper_like_mpc` 主线：先复现 Kim et al. 2022 的冷站-TES-MPC 结构，再逐步加中国 TOU / 尖峰电价 / peak-cap。

---

## 0. 执行原则

1. **不删除当前 `mpc_v2` 功能**。当前中国 TOU/DR 版本保留为 `advanced/current_full_mpc` 或原路径。
2. **新建 paper-like 主线**，用来写论文主结果。
3. **先复现结构，不追求功能大而全**。
4. **每完成一层都要生成 run、summary、figure 和测试**。
5. **PPT 文件在本地，不假设 Codex 能自动找到**。若用户提供 `PPT_PATH`，再更新 PPT；否则只生成 PPT storyboard 和图表素材。

---

## 1. 当前仓库状态确认

Codex 先执行：

```bash
git status --short
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
find . -maxdepth 3 -type d | sort > docs/repo_tree_depth3_before_kim_lite.txt
find mpc_v2 -maxdepth 3 -type f | sort > docs/mpc_v2_files_before_kim_lite.txt
pytest -q
```

生成：

```text
docs/codex_kim_lite_inventory_20260507.md
```

内容必须包括：

```text
current_branch
current_commit
pytest_result
current controller modes
current scenario sets
current result directories
current PPT handling assumption
```

验收：

```bash
test -f docs/codex_kim_lite_inventory_20260507.md
```

---

## 2. 新建 paper-like 模块骨架

建议新建：

```text
mpc_v2/kim_lite/
  __init__.py
  config.py
  model.py
  controller.py
  baseline.py
  metrics.py
  plotting.py
  README.md
```

也可以选择把文件放在 `mpc_v2/core/`，但必须避免污染现有复杂 MPC。推荐独立 `kim_lite/`。

新增配置：

```text
mpc_v2/config/kim_lite_base.yaml
mpc_v2/config/kim_lite_scenarios.yaml
```

新增脚本：

```text
mpc_v2/scripts/run_kim_lite_closed_loop.py
mpc_v2/scripts/run_kim_lite_matrix.py
mpc_v2/scripts/plot_kim_lite_results.py
```

新增结果目录：

```text
results/kim_lite_repro_20260507/
```

---

## 3. paper-like MPC 的数学定义

### 3.1 外生输入

每个预测步 `k = 0...N-1`：

```text
Q_load_kw_th[k]       # 数据中心/建筑冷负荷，外生预测
P_nonplant_kw[k]      # 非冷站电负荷，whole-facility 中通常为 IT load + non-cooling auxiliary
P_pv_kw[k]            # behind-meter PV
T_wb_C[k]             # 室外湿球温度或 dry-bulb proxy
price_cny_per_kwh[k]  # 电价
```

注意：第一版 paper-like MPC **不把 room temperature 作为优化状态**。温度只用于外部验证或后续扩展。这样接近 Kim et al. 的冷站调度结构。

### 3.2 状态变量

```text
soc[k]                # TES SOC, [0,1]
```

### 3.3 主要控制变量

```text
s[j,k]                # binary, plant mode j 是否开启
nu[j,k]               # continuous, mode j 下的冷机供冷量 kW_th
Q_chiller[k]          # total chiller cooling production kW_th
P_plant[k]            # cold plant electric power kW_e
P_grid_pos[k]         # positive net grid import kW_e
d_peak                # horizon peak grid import kW_e
```

### 3.4 第一版 TES 结构：paper-like signed net TES

定义：

```text
Q_tes_net[k] = Q_chiller[k] - Q_load_kw_th[k]
```

含义：

```text
Q_tes_net > 0: chiller output exceeds cooling load → TES charging
Q_tes_net < 0: cooling load exceeds chiller output → TES discharging
```

为了保持简单，第一版使用线性 SOC 动态：

```text
soc[k+1] = (1 - loss_per_h * dt_h) * soc[k]
           + Q_tes_net[k] * dt_h / E_tes_kwh_th
```

约束：

```text
-Q_dis_max_kw_th <= Q_tes_net[k] <= Q_ch_max_kw_th
soc_min - soc_slack_low[k] <= soc[k] <= soc_max + soc_slack_high[k]
soc_slack_low[k] >= 0
soc_slack_high[k] >= 0
```

这一版牺牲充放效率细节，换取论文结构清晰。实现后必须在 README 说明：这是 Kim-like LTI TES proxy，不是最终精细 TES efficiency model。

### 3.5 第二版 TES 结构：带效率的 split TES，可选

如果第一版跑通，再加：

```text
Q_tes_net[k] = Q_ch_tes[k] - Q_dis_tes[k]
Q_ch_tes[k] >= 0
Q_dis_tes[k] >= 0
Q_ch_tes[k] <= z_ch[k] * Q_ch_max
Q_dis_tes[k] <= z_dis[k] * Q_dis_max
z_ch[k] + z_dis[k] <= 1
```

SOC：

```text
soc[k+1] = (1 - loss_per_h * dt_h) * soc[k]
           + eta_ch * Q_ch_tes[k] * dt_h / E_tes_kwh_th
           - Q_dis_tes[k] * dt_h / (eta_dis * E_tes_kwh_th)
```

这一步为后续中国 TOU/DR 正式结果使用。Codex 不要在第一天就强行完成 split 版。

### 3.6 冷机模式约束

```text
sum_j s[j,k] <= 1
Q_chiller[k] = sum_j nu[j,k]
Q_min[j] * s[j,k] <= nu[j,k] <= Q_max[j] * s[j,k]
```

如果系统允许关机：

```text
sum_j s[j,k] = 0 → Q_chiller[k] = 0
```

### 3.7 冷站功率模型

第一版：

```text
P_plant[k] = sum_j (a_kw_per_kwth[j] * nu[j,k]
                    + b_kw[j] * s[j,k]
                    + c_kw_per_C[j] * T_wb_C[k] * s[j,k])
```

若当前 active mode 的外温项不可靠，可先设：

```text
c_kw_per_C[j] = 0
```

但保留字段和日志。

### 3.8 whole-facility grid accounting

```text
P_grid_pos[k] >= P_nonplant_kw[k] + P_plant[k] - P_pv_kw[k]
P_grid_pos[k] >= 0
```

可选 PV spill：

```text
P_spill[k] >= P_pv_kw[k] - P_nonplant_kw[k] - P_plant[k]
P_spill[k] >= 0
```

第一版可以只保留 `P_grid_pos`。

### 3.9 peak epigraph

```text
P_grid_pos[k] <= d_peak
```

### 3.10 目标函数

第一版目标：

```text
min sum_k price[k] * P_grid_pos[k] * dt_h
    + w_peak * d_peak
    + w_soc * sum_k (soc_slack_low[k] + soc_slack_high[k])
```

第二版可加：

```text
+ w_cycle * sum_k abs(Q_tes_net[k]) * dt_h
+ w_switch * sum_k abs(u_signed[k] - u_signed[k-1])
+ w_terminal * |soc[N] - soc_target|
```

注意：`abs()` 必须线性化，不得直接进入 MILP。

---

## 4. Baseline 设计

### 4.1 storage-priority baseline

这是 paper-like 主 baseline。

规则：

```text
if low-price period and SOC < soc_high:
    Q_chiller = min(Q_load + Q_ch_max, plant_capacity)
    # charge TES
elif high-price period and SOC > soc_low:
    Q_chiller = max(Q_load - Q_dis_max, 0)
    # discharge TES
else:
    Q_chiller = Q_load
```

必须保持：

```text
Q_chiller >= 0
Q_tes_net = Q_chiller - Q_load
SOC remains inside physical bounds, or clipped with logged violation
```

### 4.2 mpc_no_tes baseline

同一个 paper-like MILP，但禁用 TES：

```text
Q_tes_net[k] = 0
soc constant
Q_chiller[k] = Q_load[k]
```

如果要允许 chiller mode optimization，但无 TES，则保留 mode 选择：

```text
Q_chiller[k] = Q_load[k]
```

这样能分离：

```text
mode selection / plant efficiency effect
vs
TES shifting effect
```

### 4.3 direct_no_tes baseline

冷机直接跟踪负荷：

```text
Q_chiller = Q_load
mode = smallest feasible mode or existing rule
```

---

## 5. 阶段化执行计划

## Phase A：paper-like 最小复现，预计 1–2 天

目标：跑通 `storage_priority_baseline` vs `paper_like_mpc`。

任务：

1. 创建 `mpc_v2/kim_lite/` 模块。
2. 实现 `KimLiteInputs`、`KimLiteConfig`、`KimLiteSolution` dataclass。
3. 实现最小 MILP：mode + Q_chiller + SOC + grid + peak。
4. 实现 storage-priority baseline。
5. 实现 `run_kim_lite_closed_loop.py`。
6. 输出：

```text
results/kim_lite_repro_20260507/phase_a/storage_priority/monitor.csv
results/kim_lite_repro_20260507/phase_a/paper_like_mpc/monitor.csv
results/kim_lite_repro_20260507/phase_a/summary.csv
```

验收：

```bash
pytest -q
python -m mpc_v2.scripts.run_kim_lite_closed_loop --controller storage_priority --steps 96 --case-id kim_a_storage
python -m mpc_v2.scripts.run_kim_lite_closed_loop --controller paper_like_mpc --steps 96 --case-id kim_a_mpc
```

检查：

```text
SOC 有充放变化
Q_tes_net > 0 出现在低价或 PV-rich 时段
Q_tes_net < 0 出现在高价或 peak 时段
P_grid_pos 与 P_nonplant + P_plant - P_pv 一致
```

---

## Phase B：归因矩阵，预计 1 天

加入：

```text
direct_no_tes
mpc_no_tes
storage_priority_tes
paper_like_mpc_tes
```

输出：

```text
results/kim_lite_repro_20260507/phase_b_attribution/summary.csv
results/kim_lite_repro_20260507/phase_b_attribution/attribution_table.md
```

指标：

```text
cost_total
plant_energy_cost
grid_import_kwh
peak_grid_kw
soc_initial
soc_final
soc_delta
TES_charge_kwh_th
TES_discharge_kwh_th
TES_charge_weighted_avg_price
TES_discharge_weighted_avg_price
TES_arbitrage_spread
solver_time_avg_s
solver_time_p95_s
```

归因公式：

```text
MPC_value = cost(direct_no_tes) - cost(mpc_no_tes)
TES_value = cost(mpc_no_tes) - cost(paper_like_mpc_tes)
RBC_gap   = cost(storage_priority_tes) - cost(paper_like_mpc_tes)
```

---

## Phase C：中国 TOU / 尖峰电价，预计 1–2 天

在 `kim_lite_scenarios.yaml` 中加入：

```yaml
tou_scenarios:
  flat:
    spread_gamma: 0.0
    critical_peak_uplift: 0.0
  base:
    spread_gamma: 1.0
    critical_peak_uplift: 0.0
  base_cp20:
    spread_gamma: 1.0
    critical_peak_uplift: 0.20
  high_spread:
    spread_gamma: 2.0
    critical_peak_uplift: 0.0
  high_spread_cp20:
    spread_gamma: 2.0
    critical_peak_uplift: 0.20
```

电价公式：

```text
p_t = p_nonfloat + [mean(p_float) + gamma * (p_float_base_t - mean(p_float))] * (1 + cp_uplift * I_cp_t)
```

如果当前没有 float/nonfloat 拆分：

```text
p_float = alpha_float * p_all_in
p_nonfloat = (1 - alpha_float) * p_all_in
alpha_float default = 0.8
```

必须在 docs 中声明这是工程近似。

每个场景跑：

```text
mpc_no_tes
paper_like_mpc_tes
```

代表场景再跑四控制器。

输出图：

```text
fig_tou_cost_vs_gamma.png
fig_tou_arbitrage_spread_vs_gamma.png
fig_tou_representative_day_dispatch.png
```

---

## Phase D：peak-cap / DR，预计 1–2 天

先只做 peak-cap，不做复杂 DR baseline。

约束：

```text
P_grid_pos[k] <= P_cap + s_peak[k]
s_peak[k] >= 0
objective += w_peak_slack * sum_k s_peak[k] * dt_h
```

cap 生成：

```text
P_cap = r_cap * peak(mpc_no_tes_no_cap)
r_cap ∈ {1.00, 0.99, 0.97, 0.95}
```

每个 cap 跑：

```text
mpc_no_tes
paper_like_mpc_tes
```

记录：

```text
peak_grid_kw
peak_reduction_kw
peak_slack_max_kw
peak_slack_kwh
TES_discharge_during_peak_window_kwh_th
cost_increase_vs_no_cap
```

输出图：

```text
fig_peak_reduction_cost_tradeoff.png
fig_peak_window_dispatch.png
```

---

## Phase E：signed valve 作为扩展，预计 0.5–1 天

不要把 signed valve 放进 Phase A。

在 paper-like 模型跑通后，定义：

```text
u_signed[k] = Q_tes_net[k] / Q_tes_max_kw_th
-1 <= u_signed[k] <= 1
```

加 ramp：

```text
-du_max <= u_signed[k] - u_signed[k-1] <= du_max
```

输出：

```text
u_signed
signed_du
max_signed_du
signed_valve_violation_count
```

---

## Phase F：PPT 输出计划

由于 PPT 文件在用户本地，Codex 不得假设固定路径。

### 6.1 如果用户设置了环境变量

```bash
export PPT_PATH=/path/to/local/presentation.pptx
```

Codex 才允许修改 PPT：

1. 先备份：

```bash
cp "$PPT_PATH" "${PPT_PATH%.pptx}_backup_before_kim_lite_20260507.pptx"
```

2. 生成 figures 到：

```text
results/kim_lite_repro_20260507/figures_for_ppt/
```

3. 只做增量修改，不删除用户已有页。

### 6.2 如果没有 PPT_PATH

只生成：

```text
docs/ppt_storyboard_kim_lite_20260507.md
```

PPT storyboard 建议 12 页：

```text
1. 研究问题：数据中心冷站 TES 的真实边际价值
2. 参考论文：Kim et al. 2022 的冷站-TES-MPC 骨架
3. 当前复杂 MPC 为什么需要收束
4. paper-like 系统边界：Q_load, P_nonplant, PV, TES, plant mode
5. MILP 变量与公式
6. Baseline：storage priority vs MPC
7. Attribution：direct_no_tes / mpc_no_tes / storage_priority / mpc_tes
8. 中国 TOU / 尖峰电价场景
9. peak-cap 场景
10. 代表性时序图：price + SOC + Q_tes_net + grid
11. 结果：TES 价值与边界
12. 结论与后续工作
```

验收：

```bash
test -f docs/ppt_storyboard_kim_lite_20260507.md
```

---

## 6. 测试清单

新增测试：

```text
tests/test_kim_lite_tes_net.py
tests/test_kim_lite_power_balance.py
tests/test_kim_lite_mode_constraints.py
tests/test_kim_lite_peak_epigraph.py
tests/test_kim_lite_storage_priority.py
tests/test_kim_lite_scenarios.py
```

测试内容：

```text
1. Q_tes_net = Q_chiller - Q_load
2. Q_tes_net > 0 时 SOC 增加
3. Q_tes_net < 0 时 SOC 减少
4. mode off 时 nu=0
5. mode on 时 Q_min <= nu <= Q_max
6. P_grid_pos >= P_nonplant + P_plant - P_pv
7. d_peak >= all P_grid_pos
8. storage_priority 低价充冷、高价放冷
9. peak-cap slack 非负
10. u_signed ramp 不超过 du_max
```

验收命令：

```bash
pytest -q
```

---

## 7. 最终交付物

Codex 最后必须生成：

```text
docs/kim_lite_final_report_20260507.md
results/kim_lite_repro_20260507/phase_a/summary.csv
results/kim_lite_repro_20260507/phase_b_attribution/summary.csv
results/kim_lite_repro_20260507/phase_c_tou/summary.csv
results/kim_lite_repro_20260507/phase_d_peakcap/summary.csv
results/kim_lite_repro_20260507/figures/
docs/ppt_storyboard_kim_lite_20260507.md
```

`docs/kim_lite_final_report_20260507.md` 必须包含：

```text
1. 实现了哪些模块
2. 与 Kim et al. 2022 的对应关系
3. 哪些地方是结构复现，哪些地方是数据中心/中国语境扩展
4. 数学公式
5. baseline 定义
6. 场景矩阵
7. 主要结果
8. TES 是否真的产生边际收益
9. 负结果和限制
10. PPT 更新说明
```

---

## 8. 禁止事项

Codex 不得：

```text
1. 删除当前 advanced MPC 代码；
2. 把 paper-like MPC 和当前复杂 MPC 混在同一个函数里难以区分；
3. 在 Phase A 就加入中国 TOU、DR、signed valve、room temperature 等复杂功能；
4. 只比较 direct_no_tes vs mpc_tes，然后把全部收益归因给 TES；
5. 不报告 final SOC；
6. 不报告 plant-level 和 whole-facility-level 两个成本口径；
7. 静默忽略 solver infeasible；
8. 未备份本地 PPT 就修改 PPT；
9. 声称数值复现 Kim et al. 2022。
```

---

## 9. 推荐 commit 顺序

```bash
git checkout -b refactor/kim-lite-paper-mpc

# Phase A
git add mpc_v2/kim_lite mpc_v2/scripts/run_kim_lite_closed_loop.py tests/test_kim_lite_*.py
git commit -m "Add Kim-style paper-like chiller TES MPC skeleton"

# Phase B
git add mpc_v2/scripts/run_kim_lite_matrix.py results/kim_lite_repro_20260507/phase_b_attribution docs/kim_lite_*.md
git commit -m "Add attribution matrix for paper-like MPC"

# Phase C/D
git add mpc_v2/config/kim_lite_scenarios.yaml results/kim_lite_repro_20260507/phase_c_tou results/kim_lite_repro_20260507/phase_d_peakcap
git commit -m "Add China TOU and peak-cap scenarios for Kim-style MPC"

# PPT/storyboard
git add docs/ppt_storyboard_kim_lite_20260507.md results/kim_lite_repro_20260507/figures
git commit -m "Add thesis PPT storyboard and Kim-lite figures"
```
