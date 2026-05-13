# Codex 任务说明：PV–TES 技术推荐容量与尖峰电价抑制敏感性分析

版本：2026-05-13  
适用主线：MPC_V2 / Kim-lite relaxed proxy  
目标：基于当前 Kim-lite MPC 主线，增加一个**技术容量推荐**模块，用 PV–TES 容量矩阵分析削峰、PV 自消纳和尖峰电价冲击抑制能力，并给出**运行层面的推荐容量区间**。

---

## 0. 总原则

本阶段只做运行层面的技术推荐，不做投资经济性最优 sizing。

必须保持当前主线简洁：

```text
Kim-lite relaxed proxy
+ PV capacity sensitivity
+ TES capacity sensitivity
+ critical peak price impact
+ peak / self-consumption / CP suppression metrics
```

不要引入：

```text
CAPEX / LCOE / NPV
workload scheduling
RL / data-driven model
carbon trading / green certificate
full EnergyPlus online economic validation
strict binary chiller sequencing
```

论文表述中必须使用：

```text
technical recommended capacity range
```

不要写：

```text
economic optimum
optimal investment sizing
```

---

## 1. 研究问题冻结

本阶段回答以下问题：

```text
在给定数据中心负荷和地点条件下，PV 装机容量与 TES 容量如何影响：
1. 尖峰电价冲击抑制能力；
2. 尖峰时段购电削减；
3. PV 自消纳率；
4. 削峰能力；
5. TES 容量边际收益递减；
6. 运行层面推荐 PV–TES 容量区间。
```

核心自变量：

```text
PV capacity: 0, 10, 20, 40, 60 MWp
TES capacity: 0, 9, 18, 36, 72 MWh_th
```

核心控制器：

```text
Kim-lite MPC relaxed dispatch
```

可选 baseline：

```text
mpc_no_tes when TES = 0
storage_priority_tes only for representative cases, not full matrix
```

---

## 2. 文献和政策依据写入文档

创建或更新：

```text
docs/phase3_pv_tes_sizing_assumptions.md
```

必须写入以下依据：

### 2.1 PV 容量依据

主扫描值：

```text
PV = 0, 10, 20, 40, 60 MWp
```

其中：

```text
20 MWp 是 baseline / reference value
```

依据：Apple Maiden 数据中心存在 20 MW 级 solar array 的公开先例。20 MWp 应表述为：

```text
onsite or nearby behind-the-meter / dedicated PV resource
```

不要表述为：

```text
rooftop PV
```

### 2.2 TES 容量依据

主扫描值：

```text
TES = 0, 9, 18, 36, 72 MWh_th
```

其中：

```text
18 MWh_th 是 baseline / reference value
```

基准推导应写清楚：

```text
E_TES,kWh ≈ 1.163 × V_m3 × ΔT_K
```

并说明 18 MWh_th 是 literature-informed control-oriented baseline，不是精确工程设计值。

### 2.3 中国尖峰电价依据

主尖峰电价上浮：

```text
critical_peak_uplift = 0.2
```

可选压力测试：

```text
critical_peak_uplift = 0.5
```

必须说明：

```text
δ = 0.2 是政策锚定；δ = 0.5 是压力测试，不代表真实政策默认值。
```

---

## 3. 新增目录结构

在当前 repo 中新增：

```text
mpc_v2/phase3_sizing/
  __init__.py
  schema.py
  scenario_builder.py
  pv_scaling.py
  tes_scaling.py
  metrics.py
  recommendation.py
  plotting.py
```

新增脚本：

```text
mpc_v2/scripts/run_phase3_pv_tes_matrix.py
mpc_v2/scripts/audit_phase3_pv_tes_results.py
mpc_v2/scripts/plot_phase3_pv_tes_results.py
```

新增配置：

```text
mpc_v2/config/phase3_pv_tes_sizing.yaml
mpc_v2/config/phase3_locations.yaml
```

新增测试：

```text
tests/test_phase3_pv_scaling.py
tests/test_phase3_tes_scaling.py
tests/test_phase3_cp_metrics.py
tests/test_phase3_recommendation.py
tests/test_phase3_matrix_builder.py
```

新增输出目录：

```text
results/phase3_pv_tes_sizing/
  runs/
  summary/
  figures/
  docs/
```

---

## 4. 配置文件要求

创建：

```text
mpc_v2/config/phase3_pv_tes_sizing.yaml
```

建议内容：

```yaml
phase3:
  name: pv_tes_technical_sizing
  model: kim_lite_relaxed
  purpose: technical_capacity_recommendation

locations:
  config: mpc_v2/config/phase3_locations.yaml

simulation:
  dt_hours: 0.25
  horizon_steps: 48
  episode_days: 7
  start_day_policy: hot_week_or_location_default
  use_kim_lite_proxy: true
  use_energyplus_online: false

pv:
  capacities_mwp: [0, 10, 20, 40, 60]
  reference_mwp: 20
  scale_method: linear_from_profile
  source_note: PVGIS_or_existing_location_profile

tes:
  capacities_mwh_th: [0, 9, 18, 36, 72]
  reference_mwh_th: 18
  keep_power_fixed: true
  q_tes_abs_max_kw_th: 4500
  soc_initial: 0.50
  soc_min: 0.15
  soc_max: 0.85
  soc_target: 0.50
  enforce_terminal_soc: true

critical_peak:
  uplift_values: [0.0, 0.2]
  optional_stress_uplift_values: [0.5]
  window_sets:
    evening:
      - [16, 20]
  default_window_set: evening

controller:
  name: paper_like_mpc_tes_relaxed
  enforce_signed_ramp: true
  max_signed_du: 0.25
  mode_integrality: relaxed
  report_mode_fractionality: true

recommendation:
  peak_reduction_threshold_fraction: 0.90
  cp_suppression_threshold_fraction: 0.90
  max_allowed_soc_abs_delta: 0.05
  min_pv_self_consumption_ratio: 0.80
  marginal_gain_threshold: 0.05
```

创建：

```text
mpc_v2/config/phase3_locations.yaml
```

建议内容：

```yaml
locations:
  - id: nanjing
    label: Nanjing
    role: baseline_east_china
    weather_profile: data/locations/nanjing/weather.csv
    pv_profile_20mwp: data/locations/nanjing/pv_20mwp.csv
    load_profile: data/locations/nanjing/load.csv

  - id: guangzhou
    label: Guangzhou
    role: hot_humid_south_china
    weather_profile: data/locations/guangzhou/weather.csv
    pv_profile_20mwp: data/locations/guangzhou/pv_20mwp.csv
    load_profile: data/locations/guangzhou/load.csv

  - id: beijing
    label: Beijing
    role: north_china_policy_relevance
    weather_profile: data/locations/beijing/weather.csv
    pv_profile_20mwp: data/locations/beijing/pv_20mwp.csv
    load_profile: data/locations/beijing/load.csv
```

如果某地点数据不存在，runner 不得静默跳过，必须报错或生成明确的 missing-data report。

---

## 5. PV 缩放模块

实现：

```text
mpc_v2/phase3_sizing/pv_scaling.py
```

函数：

```python
def scale_pv_profile(base_pv_kw: pd.Series, base_capacity_mwp: float, target_capacity_mwp: float) -> pd.Series:
    ...
```

要求：

```text
1. base_capacity_mwp 必须 > 0；
2. target_capacity_mwp = 0 时返回全零；
3. 输出单位保持 kW；
4. 线性缩放：pv_target = pv_base * target_capacity_mwp / base_capacity_mwp；
5. 不允许出现负 PV；
6. index 必须保持不变。
```

测试：

```text
PV 20 MWp → 40 MWp，所有值翻倍
PV 20 MWp → 0 MWp，所有值为 0
负值输入会被 clip 或抛错，二选一并写清楚
```

---

## 6. TES 缩放模块

实现：

```text
mpc_v2/phase3_sizing/tes_scaling.py
```

函数：

```python
def build_tes_config(base_cfg: dict, capacity_mwh_th: float, q_abs_max_kw_th: float | None = None) -> dict:
    ...
```

要求：

```text
1. capacity_mwh_th = 0 时，自动生成 no-TES case；
2. capacity_mwh_th > 0 时，设置 TES capacity；
3. 主实验 keep_power_fixed = true，所以 q_abs_max 默认不随容量变化；
4. 若 capacity = 0，必须强制：
   q_tes_abs_max = 0
   SOC constant
   Q_tes_net = 0
5. 不允许 capacity < 0。
```

测试：

```text
capacity 0 → q_tes_abs_max = 0
capacity 18 → capacity 正确
capacity 72 且 keep_power_fixed → q_tes_abs_max 仍为 4500
```

---

## 7. 场景构建器

实现：

```text
mpc_v2/phase3_sizing/scenario_builder.py
```

生成完整矩阵：

```text
location × pv_capacity_mwp × tes_capacity_mwh_th × cp_uplift
```

主矩阵：

```text
locations: from phase3_locations.yaml
pv: [0, 10, 20, 40, 60]
tes: [0, 9, 18, 36, 72]
cp_uplift: [0.0, 0.2]
```

若 3 个地点：

```text
3 × 5 × 5 × 2 = 150 cases
```

每个 scenario_id 格式：

```text
phase3_{location}_pv{PV}mwp_tes{TES}mwh_cp{UPLIFT}
```

示例：

```text
phase3_nanjing_pv20mwp_tes18mwh_cp20
phase3_guangzhou_pv40mwp_tes36mwh_cp00
```

输出：

```text
results/phase3_pv_tes_sizing/summary/scenario_manifest.csv
```

字段：

```text
scenario_id
location_id
pv_capacity_mwp
tes_capacity_mwh_th
critical_peak_uplift
critical_peak_window_set
controller
run_dir
status
```

---

## 8. 尖峰电价模型

在当前 Kim-lite tariff 服务基础上实现或复用。

关键公式：

```text
price_cp[t] = price_base[t] * (1 + uplift * I_cp[t])
```

其中 `I_cp[t]` 由显式窗口决定：

```text
16:00 <= hour < 20:00
```

要求：

```text
1. cp_uplift = 0 时，价格不得变化；
2. cp_uplift = 0.2 时，仅 CP window 内价格上浮 20%；
3. CP flag 必须写入每个 run 的 timeseries；
4. 不得使用 price quantile 自动推断 CP。
```

测试：

```text
15:45 不上浮
16:00 上浮
19:45 上浮
20:00 不上浮
```

---

## 9. 主 runner

实现：

```text
mpc_v2/scripts/run_phase3_pv_tes_matrix.py
```

CLI：

```bash
python -m mpc_v2.scripts.run_phase3_pv_tes_matrix \
  --config mpc_v2/config/phase3_pv_tes_sizing.yaml \
  --locations mpc_v2/config/phase3_locations.yaml \
  --output-root results/phase3_pv_tes_sizing \
  --parallel 4
```

要求：

```text
1. 读取 config 和 locations；
2. 构建 scenario manifest；
3. 对每个 scenario 生成 PV profile、TES config、critical peak price；
4. 调用 Kim-lite controller；
5. 保存 timeseries.csv、episode_summary.json、config_effective.yaml；
6. 失败 case 不得吞掉，必须写入 manifest status = failed；
7. 最终生成 phase3_summary.csv。
```

单个 run 输出：

```text
results/phase3_pv_tes_sizing/runs/{scenario_id}/
  config_effective.yaml
  timeseries.csv
  episode_summary.json
  solver_log.csv
```

总输出：

```text
results/phase3_pv_tes_sizing/summary/scenario_manifest.csv
results/phase3_pv_tes_sizing/summary/phase3_summary.csv
results/phase3_pv_tes_sizing/summary/phase3_capacity_recommendations.csv
```

---

## 10. 指标计算

实现：

```text
mpc_v2/phase3_sizing/metrics.py
```

### 10.1 基础能量指标

```text
facility_energy_kwh = sum(facility_power_kw * dt)
grid_import_kwh = sum(grid_kw * dt)
pv_generation_kwh = sum(pv_kw * dt)
pv_spill_kwh = sum(pv_spill_kw * dt)
pv_used_kwh = pv_generation_kwh - pv_spill_kwh
```

```text
pv_self_consumption_ratio = pv_used_kwh / pv_generation_kwh
pv_facility_load_coverage_ratio = pv_used_kwh / facility_energy_kwh
```

若 denominator 为 0，返回 NaN，不要返回 0。

### 10.2 削峰指标

基准为同地点、同 CP uplift 下：

```text
PV = 0, TES = 0
```

```text
peak_reduction_kw = peak_grid_kw_baseline - peak_grid_kw_case
peak_reduction_ratio = peak_reduction_kw / peak_grid_kw_baseline
```

### 10.3 尖峰窗口指标

```text
critical_peak_hours = hours where cp_flag == 1
critical_peak_grid_kwh = sum(grid_kw * dt over CP)
critical_peak_avg_grid_kw = critical_peak_grid_kwh / CP_duration_h
critical_peak_pv_used_kwh = sum(pv_used_kw * dt over CP)
critical_peak_tes_discharge_kwh_th = sum(q_tes_dis_kw_th * dt over CP)
critical_peak_tes_charge_kwh_th = sum(q_tes_ch_kw_th * dt over CP)
```

### 10.4 尖峰电价冲击

对同一地点、同一 PV、同一 TES：

```text
cp_cost_impact = cost(cp_uplift=0.2) - cost(cp_uplift=0.0)
```

对可选压力测试：

```text
cp_cost_impact_stress = cost(cp_uplift=0.5) - cost(cp_uplift=0.0)
```

### 10.5 尖峰电价抑制率

对同一地点、同一 PV、同一 TES，以同地点同 PV 的 no-TES 为参考：

```text
I_ref = cost(location, PV, TES=0, cp=0.2) - cost(location, PV, TES=0, cp=0.0)
I_case = cost(location, PV, TES=E, cp=0.2) - cost(location, PV, TES=E, cp=0.0)
critical_peak_suppression_ratio = 1 - I_case / I_ref
```

如果 `I_ref <= 0`，返回 NaN，并在 warning 中说明该地点/容量组合没有正向尖峰电价冲击基准。

### 10.6 TES 容量利用指标

```text
tes_charge_kwh_th = sum(max(Q_tes_net,0) * dt)
tes_discharge_kwh_th = sum(max(-Q_tes_net,0) * dt)
tes_discharge_cp_ratio = critical_peak_tes_discharge_kwh_th / tes_discharge_kwh_th
tes_effective_capacity_kwh_th = tes_capacity_mwh_th * 1000 * (soc_max - soc_min)
tes_cp_capacity_utilization = critical_peak_tes_discharge_kwh_th / tes_effective_capacity_kwh_th
```

若 TES capacity 为 0，相关 TES 指标返回 0 或 NaN，保持一致：

```text
charge/discharge energy = 0
ratios requiring denominator = NaN
```

### 10.7 边际收益指标

按地点和 PV 分组，计算 TES 容量边际改善：

```text
marginal_cp_suppression_per_mwh =
  (cp_suppression_ratio[E_j] - cp_suppression_ratio[E_{j-1}]) /
  (E_j - E_{j-1})
```

按地点和 TES 分组，计算 PV 容量边际改善：

```text
marginal_peak_reduction_per_mwp =
  (peak_reduction_ratio[PV_i] - peak_reduction_ratio[PV_{i-1}]) /
  (PV_i - PV_{i-1})
```

---

## 11. 技术推荐规则

实现：

```text
mpc_v2/phase3_sizing/recommendation.py
```

本阶段输出**技术推荐容量区间**，不是投资经济性最优。

### 11.1 90% 最大效果最小容量规则

对每个地点，计算所有 PV–TES 组合中的：

```text
max_cp_suppression_ratio
max_peak_reduction_ratio
max_pv_facility_load_coverage_ratio
```

推荐满足以下条件的最小容量组合：

```text
cp_suppression_ratio >= 0.90 * max_cp_suppression_ratio
peak_reduction_ratio >= 0.90 * max_peak_reduction_ratio
pv_self_consumption_ratio >= 0.80
abs(soc_delta) <= 0.05  # if available
```

容量排序成本代理：

```text
capacity_size_score = normalized(PV_MWp) + normalized(TES_MWh_th)
```

选择 size_score 最小的组合。

输出字段：

```text
location_id
recommended_pv_mwp
recommended_tes_mwh_th
rule_name
cp_suppression_ratio
peak_reduction_ratio
pv_self_consumption_ratio
pv_facility_load_coverage_ratio
notes
```

### 11.2 Pareto frontier

建立 Pareto frontier：

目标越大越好：

```text
cp_suppression_ratio
peak_reduction_ratio
pv_facility_load_coverage_ratio
pv_self_consumption_ratio
```

容量越小越好：

```text
pv_capacity_mwp
tes_capacity_mwh_th
```

输出：

```text
is_pareto_frontier
pareto_rank
```

### 11.3 边际收益递减判断

对于 TES 容量：

```text
marginal_gain_threshold = 0.05
```

如果从某个容量继续增加后：

```text
additional_cp_suppression_gain < 5% of previous gain
```

标记：

```text
diminishing_return_after_this_capacity = true
```

---

## 12. 图表生成

实现：

```text
mpc_v2/scripts/plot_phase3_pv_tes_results.py
```

输出目录：

```text
results/phase3_pv_tes_sizing/figures/
```

必须生成：

### 12.1 Heatmap: CP suppression

```text
x-axis: PV capacity MWp
y-axis: TES capacity MWh_th
color: critical_peak_suppression_ratio
facet: location
```

文件：

```text
heatmap_cp_suppression_by_location.png
```

### 12.2 Heatmap: peak reduction

```text
color: peak_reduction_ratio
```

文件：

```text
heatmap_peak_reduction_by_location.png
```

### 12.3 Heatmap: PV self-consumption

```text
color: pv_self_consumption_ratio
```

文件：

```text
heatmap_pv_self_consumption_by_location.png
```

### 12.4 TES capacity marginal curves

```text
x-axis: TES capacity
 y-axis: CP suppression ratio
line: PV capacity
facet: location
```

文件：

```text
tes_capacity_cp_suppression_curves.png
```

### 12.5 Pareto scatter

```text
x-axis: pv_self_consumption_ratio
 y-axis: peak_reduction_ratio or cp_suppression_ratio
color: PV capacity
size: TES capacity
facet: location
```

文件：

```text
pareto_capacity_recommendation_scatter.png
```

要求：

```text
1. 所有图必须有单位；
2. 不使用 notebook；
3. 脚本可通过 CLI 运行；
4. 缺少指标时图表跳过并记录 warning，不得静默失败。
```

---

## 13. 审计脚本

实现：

```text
mpc_v2/scripts/audit_phase3_pv_tes_results.py
```

CLI：

```bash
python -m mpc_v2.scripts.audit_phase3_pv_tes_results \
  --summary results/phase3_pv_tes_sizing/summary/phase3_summary.csv \
  --output results/phase3_pv_tes_sizing/summary/audit_report.md
```

审计内容：

```text
1. 每个地点是否覆盖所有 PV × TES × CP uplift；
2. cp_uplift=0 和 cp_uplift=0.2 是否成对存在；
3. TES=0 时 TES charge/discharge 是否为 0；
4. PV=0 时 PV generation/spill/used 是否为 0；
5. SOC delta 是否超阈值；
6. critical_peak_suppression_ratio 是否出现 NaN / inf；
7. 是否存在 cp_suppression_ratio < 0 的 case；
8. 是否存在 PV self-consumption ratio > 1；
9. 是否存在 grid balance violation；
10. 是否存在 signed valve violation；
11. 推荐容量是否在 Pareto frontier 上。
```

---

## 14. 单元测试要求

### 14.1 PV scaling

```text
tests/test_phase3_pv_scaling.py
```

测试：

```text
20 → 40 MWp: output doubles
20 → 0 MWp: output zero
index preserved
negative PV rejected or clipped consistently
```

### 14.2 TES scaling

```text
tests/test_phase3_tes_scaling.py
```

测试：

```text
TES=0 disables TES
TES=18 sets correct capacity
TES=72 with keep_power_fixed keeps q_abs_max unchanged
negative capacity raises
```

### 14.3 Critical peak metrics

```text
tests/test_phase3_cp_metrics.py
```

构造简单数据：

```text
cp=0 cost = 100
cp=0.2 cost noTES = 120
cp=0.2 cost TES = 110
```

期望：

```text
I_ref = 20
I_case = 10
suppression = 0.5
```

### 14.4 Recommendation

```text
tests/test_phase3_recommendation.py
```

测试：

```text
选择达到 90% maximum KPI 的最小容量组合
Pareto frontier 标记正确
marginal diminishing return 标记正确
```

### 14.5 Matrix builder

```text
tests/test_phase3_matrix_builder.py
```

测试：

```text
3 locations × 5 PV × 5 TES × 2 CP = 150 scenarios
scenario_id 唯一
all required fields present
```

---

## 15. 最小执行命令

先只跑南京 pilot：

```bash
python -m mpc_v2.scripts.run_phase3_pv_tes_matrix \
  --config mpc_v2/config/phase3_pv_tes_sizing.yaml \
  --locations mpc_v2/config/phase3_locations.yaml \
  --location-filter nanjing \
  --output-root results/phase3_pv_tes_sizing/pilot_nanjing
```

审计：

```bash
python -m mpc_v2.scripts.audit_phase3_pv_tes_results \
  --summary results/phase3_pv_tes_sizing/pilot_nanjing/summary/phase3_summary.csv \
  --output results/phase3_pv_tes_sizing/pilot_nanjing/summary/audit_report.md
```

绘图：

```bash
python -m mpc_v2.scripts.plot_phase3_pv_tes_results \
  --summary results/phase3_pv_tes_sizing/pilot_nanjing/summary/phase3_summary.csv \
  --output-dir results/phase3_pv_tes_sizing/pilot_nanjing/figures
```

全量运行：

```bash
python -m mpc_v2.scripts.run_phase3_pv_tes_matrix \
  --config mpc_v2/config/phase3_pv_tes_sizing.yaml \
  --locations mpc_v2/config/phase3_locations.yaml \
  --output-root results/phase3_pv_tes_sizing/full_matrix \
  --parallel 4
```

---

## 16. 最低验收标准

Phase 3 完成必须满足：

```text
1. pytest -q tests/test_phase3_* 全部通过；
2. pilot_nanjing 完成 5×5×2 = 50 scenarios；
3. full_matrix 至少完成 3 个地点 × 5×5×2 = 150 scenarios；
4. 每个 scenario 有 timeseries.csv 和 episode_summary.json；
5. phase3_summary.csv 包含所有关键指标；
6. audit_report.md 无 P0 级错误；
7. 至少生成 4 张核心图；
8. 每个地点输出推荐 PV/TES 容量区间；
9. 文档明确写明：technical recommendation only, no CAPEX optimum。
```

---

## 17. 禁止事项

Codex 不得做：

```text
1. 不得加入 CAPEX 或声称 economic optimum，除非用户另行提供成本数据；
2. 不得把推荐容量写成唯一最优容量；
3. 不得新增 workload scheduling；
4. 不得新增 RL / LSTM / data-driven thermal model；
5. 不得把 EnergyPlus online diagnostic 结果混入 Phase 3 主结果；
6. 不得只看 total_cost 而忽略 PV self-consumption、peak、SOC、CP impact；
7. 不得隐藏 cp_suppression_ratio < 0 的 case；
8. 不得在 PV=0 或 TES=0 的情况下生成虚假的 PV/TES 指标；
9. 不得用 all-in tariff multiplier 替代 explicit critical peak uplift。
```

---

## 18. 论文输出建议

Codex 需要生成：

```text
results/phase3_pv_tes_sizing/docs/phase3_methods.md
results/phase3_pv_tes_sizing/docs/phase3_results_summary.md
results/phase3_pv_tes_sizing/docs/phase3_capacity_recommendation.md
```

### phase3_methods.md 必须包含

```text
1. PV capacity scan definition；
2. TES capacity scan definition；
3. critical peak uplift definition；
4. Kim-lite controller boundary；
5. technical recommendation rule；
6. limitations: no CAPEX, no economic optimum。
```

### phase3_results_summary.md 必须包含

```text
1. 每个地点的 heatmap 结果概述；
2. TES 容量边际收益是否递减；
3. PV 自消纳是否随 PV 增大下降；
4. TES 是否提高 PV self-consumption；
5. TES 是否提高 CP suppression；
6. negative cases 解释。
```

### phase3_capacity_recommendation.md 必须包含

```text
1. 每个地点推荐 PV/TES 容量区间；
2. 推荐依据；
3. 不推荐过大 PV/TES 的原因；
4. 技术推荐与经济最优的区别。
```

---

## 19. 推荐提交信息

阶段性提交：

```bash
git add .
git commit -m "Add phase3 PV-TES technical sizing matrix"
```

完成指标和推荐：

```bash
git commit -m "Add phase3 capacity recommendation metrics and plots"
```

完成文档：

```bash
git commit -m "Document phase3 PV-TES technical capacity recommendation"
```

---

## 20. 最终交付物

最终应交付：

```text
Code:
  mpc_v2/phase3_sizing/*
  mpc_v2/scripts/run_phase3_pv_tes_matrix.py
  mpc_v2/scripts/audit_phase3_pv_tes_results.py
  mpc_v2/scripts/plot_phase3_pv_tes_results.py

Config:
  mpc_v2/config/phase3_pv_tes_sizing.yaml
  mpc_v2/config/phase3_locations.yaml

Tests:
  tests/test_phase3_*.py

Results:
  results/phase3_pv_tes_sizing/full_matrix/summary/phase3_summary.csv
  results/phase3_pv_tes_sizing/full_matrix/summary/phase3_capacity_recommendations.csv
  results/phase3_pv_tes_sizing/full_matrix/summary/audit_report.md
  results/phase3_pv_tes_sizing/full_matrix/figures/*.png

Docs:
  docs/phase3_pv_tes_sizing_assumptions.md
  results/phase3_pv_tes_sizing/docs/phase3_methods.md
  results/phase3_pv_tes_sizing/docs/phase3_results_summary.md
  results/phase3_pv_tes_sizing/docs/phase3_capacity_recommendation.md
```
