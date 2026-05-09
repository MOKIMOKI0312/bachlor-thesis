# 当前 MPC 计算、代价函数与目标函数实现说明

日期：2026-05-09  
分支：`codex/energyplus-mpc-io-coupling`  
当前提交：`326edf1d feat: couple energyplus mpc io matrix`

## 1. 结论先行

当前仓库里的 MPC 主线是 **Kim-lite paper-like MILP**，核心求解器在：

- `mpc_v2/kim_lite/model.py`
- `Nanjing-DataCenter-TES-EnergyPlus/controller/energyplus_mpc/mpc_adapter.py`
- `Nanjing-DataCenter-TES-EnergyPlus/controller/energyplus_mpc/run_energyplus_mpc.py`

MPC 的核心优化变量是：

```text
冷机模式选择 s[j,k]
冷机供冷量 nu[j,k]
TES SOC[k]
正向购电 grid[k]
PV 弃电 spill[k]
峰值变量 d_peak
终端 SOC 偏差 term_pos / term_neg
可选 peak-cap slack
```

它真正优化的是：

```text
电费 + PV 弃电惩罚 + 峰值惩罚 + 终端 SOC 偏差惩罚 + 可选 peak-cap slack 惩罚
```

当前 EnergyPlus 在线版本已经能把 MPC 输出写到实际 EnergyPlus actuator：

```text
TES_Set
Chiller_T_Set
```

但必须注意：

> `Chiller_T_Set` 目前不是 MILP 内部决策变量，而是在 MILP 求出 TES 净动作之后，由 adapter 根据温度安全规则和价格启发式后处理得到。

所以当前版本是：

```text
TES action 由 MILP 优化
Chiller_T_Set 由后处理 I/O adapter 选择
EnergyPlus 实际执行 TES_Set + Chiller_T_Set
```

还不是完整的：

```text
TES_Set + Chiller_T_Set 同时进入 MILP 联合优化
```

## 2. 时间步与预测窗口

MPC 使用 15 分钟时间步：

```text
dt = 0.25 h
```

EnergyPlus 在线 runner 默认调用：

```text
horizon_steps = 8
```

也就是在线闭环每一步看未来：

```text
8 * 15 min = 2 h
```

Standalone Kim-lite 配置文件中默认是 96 步，也就是 24 小时：

```yaml
time:
  dt_hours: 0.25
  horizon_steps: 96
  default_steps: 96
```

在线 EnergyPlus 矩阵中实际使用的是 runner 传入的 `horizon_steps=8`。

## 3. 输入量

### 3.1 MILP 输入

MPC 每个 horizon 内需要这些序列：

```text
timestamp[k]
q_load[k]              冷负荷预测，单位 kW_th
p_nonplant[k]          非冷站电功率，单位 kW
pv[k]                  PV 功率，单位 kW
t_wb[k]                室外湿球温度，单位 °C
price[k]               电价，单位 CNY/kWh
cp_flag[k]             critical peak 标记
```

对应数据结构是 `KimLiteInputs`：

```python
KimLiteInputs(
    timestamps,
    q_load_kw_th,
    p_nonplant_kw,
    p_pv_kw,
    t_wb_c,
    price_cny_per_kwh,
    cp_flag,
)
```

### 3.2 EnergyPlus 在线输入

在线闭环中，每个 timestep 从 EnergyPlus Runtime API 读取：

```text
TES_SOC_Obs
TES_Avg_Temp_Obs
TES_Set echo
Chiller_T_Set echo
TES use/source heat transfer
chiller electricity
chiller cooling
facility electricity
zone temperature
outdoor drybulb / wetbulb
```

这些观测值用于：

```text
1. 用 EnergyPlus 当前 SOC 覆盖 MPC 初始 SOC；
2. 用上一时刻 TES_Set 形成 signed valve ramp 的 previous_u_signed；
3. 用 zone temperature 触发 I/O adapter 的温度安全过滤；
4. 输出 actual vs predicted 诊断字段。
```

PV 和电价不是 EnergyPlus 物理模型内部量，而是外部 CSV 经济核算输入。它们按 timestamp 做 15 分钟 forward-fill 对齐。

## 4. 决策变量

设：

```text
k = 0, ..., N-1
j = 0, ..., M-1
```

其中 `N` 是 horizon 步数，`M` 是冷机模式数量。

### 4.1 模式选择变量

```text
s[j,k] ∈ {0,1}
```

含义：

```text
s[j,k] = 1 代表第 k 步启用第 j 个 plant mode
```

在 `mode_integrality="relaxed"` 且只有单模式时，`s[j,k]` 可以放松为连续变量。当前 EnergyPlus online proxy 通常是单模式，所以允许 relaxed。多模式时 relaxed 会直接报错。

### 4.2 冷机供冷变量

```text
nu[j,k] >= 0
```

含义：

```text
第 k 步、第 j 个模式下的冷机供冷量，单位 kW_th
```

总冷机供冷量：

```text
Q_chiller[k] = sum_j nu[j,k]
```

### 4.3 TES SOC

```text
SOC[k], k = 0, ..., N
```

SOC 是 0 到 1 的无量纲状态。当前实现使用硬约束：

```text
SOC_min <= SOC[k] <= SOC_max
```

现在没有 SOC slack。SOC 越界不会被软惩罚，而是直接让问题不可行。

### 4.4 TES 净热功率

当前 Kim-lite 使用 signed net TES proxy：

```text
Q_tes_net[k] = Q_chiller[k] - Q_load[k]
```

符号定义：

```text
Q_tes_net > 0  -> 冷机供冷大于负荷，TES 充冷
Q_tes_net < 0  -> 冷机供冷小于负荷，TES 放冷
```

这是 MPC 内部变量，不直接作为 EnergyPlus actuator 写入。写入 EnergyPlus 前会转换为 `TES_Set`。

### 4.5 grid、spill 和 peak

```text
grid[k]  >= 0
spill[k] >= 0
d_peak   >= 0
```

含义：

```text
grid[k]  正向购电功率，单位 kW
spill[k] PV 弃电功率，单位 kW
d_peak   horizon 内 peak grid 变量，单位 kW
```

## 5. 设备模型

### 5.1 冷机功率模型

每个 mode 的冷机电功率是线性模型：

```text
P_plant_j[k] = a_j * nu[j,k] + b_j * s[j,k] + c_j * T_wb[k] * s[j,k]
```

代码中写成：

```text
plant_terms = (a_j, b_j + c_j * T_wb[k])
```

所以总 plant power 是：

```text
P_plant[k] = sum_j (a_j * nu[j,k] + (b_j + c_j*T_wb[k]) * s[j,k])
```

当前 EnergyPlus 默认 proxy 参数来自：

```yaml
plant_proxy:
  q_load_kw_th: 6839.667166190265
  p_nonplant_kw: 7850.902251757906
  modes:
    - q_min_kw_th: 0.0
      q_max_kw_th: 10297.768525580605
      a_kw_per_kwth: 0.32331844265048487
      b_kw: 0.0
      c_kw_per_c: 0.0
```

measured-data MPC 会用 sampling 拟合结果替换 `a/b/c`、TES 容量和 TES 功率限制。

### 5.2 TES SOC 更新

TES enabled 时，SOC 递推为：

```text
SOC[k+1] = (1 - loss_per_h * dt) * SOC[k]
           + (Q_chiller[k] - Q_load[k]) * dt / E_TES
```

也就是：

```text
SOC[k+1] = decay * SOC[k] + Q_tes_net[k] * dt / E_TES
```

其中：

```text
decay = 1 - loss_per_h * dt
E_TES = TES capacity, kWh_th
```

当前 EnergyPlus adapter 中固定：

```text
loss_per_h = 0.002
```

默认 EnergyPlus proxy TES 容量：

```text
E_TES = 39069.768 kWh_th
```

### 5.3 TES 充放冷功率限制

由于：

```text
Q_tes_net = Q_chiller - Q_load
```

充冷限制：

```text
Q_tes_net[k] <= Q_ch_max
```

代码中等价写为：

```text
Q_chiller[k] <= Q_load[k] + Q_ch_max
```

放冷限制：

```text
Q_tes_net[k] >= -Q_dis_max
```

代码中等价写为：

```text
Q_chiller[k] >= Q_load[k] - Q_dis_max
```

## 6. 核心约束

### 6.1 每步最多一个 plant mode

```text
sum_j s[j,k] <= 1
```

### 6.2 mode 与冷机供冷绑定

上界：

```text
nu[j,k] <= Q_max_j * s[j,k]
```

下界：

```text
nu[j,k] >= Q_min_j * s[j,k]
```

如果 `s[j,k]=0`，则 `nu[j,k]=0`。

### 6.3 初始 SOC

```text
SOC[0] = SOC_initial
```

在线 EnergyPlus 中：

```text
SOC_initial = 当前 EnergyPlus TES_SOC_Obs
```

并且会裁剪到 `[SOC_min, SOC_max]`。

### 6.4 SOC 终端目标

代码中引入两个非负变量：

```text
term_pos >= 0
term_neg >= 0
```

约束：

```text
SOC[N] - term_pos + term_neg = SOC_target
```

等价于：

```text
SOC[N] - SOC_target = term_pos - term_neg
```

目标函数会惩罚：

```text
w_terminal * (term_pos + term_neg)
```

所以它是在最小化终端 SOC 到目标 SOC 的绝对偏差。

### 6.5 grid 和 PV spill

定义：

```text
P_total[k] = P_nonplant[k] + P_plant[k]
```

购电功率：

```text
grid[k] >= P_total[k] - PV[k]
grid[k] >= 0
```

弃光功率：

```text
spill[k] >= PV[k] - P_total[k]
spill[k] >= 0
```

因此优化会得到：

```text
grid[k]  = max(0, P_total[k] - PV[k])
spill[k] = max(0, PV[k] - P_total[k])
```

### 6.6 peak 变量

```text
grid[k] <= d_peak
```

所以：

```text
d_peak >= max_k grid[k]
```

是否真正惩罚 peak 取决于：

```text
w_peak
```

当前 EnergyPlus online adapter 中：

```text
w_peak = 0
```

所以 `d_peak` 被建模和输出，但默认不参与优化成本。

### 6.7 可选 peak cap

如果传入 `peak_cap_kw`，则每步增加：

```text
grid[k] <= peak_cap_kw + cap_slack[k]
cap_slack[k] >= 0
```

目标函数惩罚：

```text
w_peak_slack * dt * cap_slack[k]
```

EnergyPlus online controller matrix 当前没有启用 peak cap。

### 6.8 signed valve ramp

在线 MPC 调用时启用：

```text
enforce_signed_ramp=True
```

定义归一化 signed valve proxy：

```text
u[k] = Q_tes_net[k] / Q_abs_max
```

第 0 步约束：

```text
|u[0] - u_previous| <= du_max
```

后续步约束：

```text
|u[k] - u[k-1]| <= du_max
```

当前参数：

```text
du_max = 0.25 per 15-min step
```

在线 EnergyPlus 中：

```text
u_previous = - last_TES_Set
```

因为 EnergyPlus actuator 的符号和 Kim-lite 内部符号相反。

## 7. 目标函数

当前 MILP 的目标函数是线性的：

```text
min J
```

其中：

```text
J =
sum_k price[k] * dt * grid[k]
+ sum_k w_spill * dt * spill[k]
+ w_peak * d_peak
+ w_terminal * (term_pos + term_neg)
+ sum_k w_peak_slack * dt * cap_slack[k]   # 仅 peak_cap 启用时存在
```

展开写：

```text
min
  Σ_k price[k] * dt * grid[k]
  + Σ_k w_spill * dt * spill[k]
  + w_peak * d_peak
  + w_terminal * |SOC[N] - SOC_target|
  + Σ_k w_peak_slack * dt * cap_slack[k]
```

但代码里绝对值不是直接写 `abs()`，而是用 `term_pos/term_neg` 线性化。

## 8. 当前权重

### 8.1 EnergyPlus online MPC 权重

在 `mpc_adapter.build_kim_config()` 中写死为：

```python
ObjectiveConfig(
    w_peak=0.0,
    w_terminal=80000.0,
    w_spill=0.001,
    w_peak_slack=100000.0,
)
```

含义：

```text
w_peak = 0
  默认不惩罚峰值。

w_terminal = 80000
  强烈要求 horizon 末端 SOC 回到 soc_target 附近。

w_spill = 0.001
  轻微惩罚 PV spill。

w_peak_slack = 100000
  仅 peak-cap 场景有效；当前 EnergyPlus online matrix 未启用 peak cap。
```

### 8.2 Standalone Kim-lite 配置权重

`mpc_v2/config/kim_lite_base.yaml` 中也是：

```yaml
objective:
  w_peak: 0.0
  w_terminal: 80000.0
  w_spill: 0.001
  w_peak_slack: 100000.0
```

## 9. MPC 输出到 EnergyPlus 的映射

MPC 内部先得到：

```text
Q_tes_net[0] = Q_chiller[0] - Q_load[0]
```

然后只执行 horizon 的第 0 步动作。

### 9.1 TES_Set

EnergyPlus 里：

```text
TES_Set < 0 -> source side charge
TES_Set > 0 -> use side discharge
```

Kim-lite 里：

```text
Q_tes_net > 0 -> charge
Q_tes_net < 0 -> discharge
```

所以映射为：

```text
TES_Set = -clip(Q_tes_net / Q_abs_max, -1, 1)
```

也就是：

```text
Q_tes_net > 0 -> TES_Set < 0
Q_tes_net < 0 -> TES_Set > 0
```

### 9.2 Chiller_T_Set

I/O-coupled controller 会额外写：

```text
Chiller_T_Set ∈ {0.0, 0.5, 1.0}
```

但当前它不是 MILP 变量。

实际选择逻辑是：

```text
if zone_temp >= 26.5:
    Chiller_T_Set = min(levels)
elif zone_temp <= 25.0 and Q_tes_net <= 0 and current price >= horizon 70% quantile:
    Chiller_T_Set = max(levels)
elif zone_temp <= 25.5 and Q_tes_net <= 0:
    Chiller_T_Set = median(levels)
else:
    Chiller_T_Set = min(levels)
```

当前默认：

```text
levels = [0.0, 0.5, 1.0]
```

直观解释：

```text
温度偏高时，把 Chiller_T_Set 拉到最低，倾向于更强供冷；
温度较低且高价放冷时，可以放松 setpoint；
其它情况保持较保守的最低 setpoint。
```

## 10. 温度安全过滤

I/O adapter 中有两个温度阈值：

```text
warm_threshold = 26.5 °C
hot_threshold  = 27.0 °C
```

规则：

```text
if zone_temp >= 26.5 and TES_Set < 0:
    TES_Set = 0
    safety_override = True
    temp_guard_charge_block = True
```

也就是：

```text
室温偏高时禁止 TES 充冷
```

如果：

```text
zone_temp >= 27.0
```

则：

```text
Chiller_T_Set = min(levels)
TES_Set 不允许继续充冷
safety_override = True
```

注意：

> 这不是 MILP 内部的温度约束，而是 EnergyPlus adapter 后处理安全过滤。

因此它不能保证优化问题本身预测温度安全，只能在实际写 actuator 前阻止明显危险动作。

## 11. Controller 类型差异

当前 runner 支持这些相关 controller：

| Controller | 是否求 MILP | 写 TES_Set | 写 Chiller_T_Set | 写 ITE_Set |
| --- | --- | --- | --- | --- |
| `no_mpc` | 否 | 否 | 否 | 否 |
| `tes_only_mpc` | 是 | 是 | 否 | 否 |
| `io_coupled_mpc` | 是 | 是 | 是 | 否 |
| `io_coupled_measured_mpc` | 是 | 是 | 是 | 否 |
| `sampling` | 否 | 是 | 是 | 是 |

`ITE_Set` 只用于辨识采样，不作为正常 MPC 控制量。

## 12. default MPC 与 measured-data MPC 的区别

### 12.1 default MPC

使用默认 proxy 参数：

```text
q_load_kw_th
p_nonplant_kw
TES capacity
TES q_abs_max
冷机线性功率系数
```

这些参数来自 `energyplus_mpc_params.yaml` 中的静态提取和 baseline 识别。

### 12.2 measured-data MPC

`io_coupled_measured_mpc` 会读取：

```text
results/energyplus_mpc_sampling_20260507/prediction_models.yaml
results/energyplus_mpc_sampling_20260507/samples_15min.csv
```

然后替换：

```text
冷机功率模型 a/b/c
TES capacity
TES loss
TES charge/discharge power limits
Chiller_T_Set 对预测冷机功率的线性系数
```

但即使是 measured-data MPC：

> `Chiller_T_Set` 仍然不是 MILP 决策变量，只是在后处理预测功率和写 actuator 时使用。

## 13. 在线闭环流程

每个 EnergyPlus system timestep：

```text
1. Runtime callback_begin_system_timestep_before_predictor 触发。
2. 读取 EnergyPlus 当前观测。
3. 根据当前 simulation_step 生成 forecast horizon。
4. 用当前 EnergyPlus SOC 作为 MPC 初始 SOC。
5. 调用 solve_paper_like_mpc 求 MILP。
6. 取 horizon 第 0 步：
   Q_tes_net[0], Q_chiller[0], P_plant_pred[0]
7. 映射：
   Q_tes_net[0] -> TES_Set
8. 如果是 I/O-coupled controller：
   再选择 Chiller_T_Set
   应用温度 safety filter
9. 写入 EnergyPlus actuator：
   TES_Set
   Chiller_T_Set，如果 controller 支持
10. callback_end_zone_timestep_after_zone_reporting 记录 EnergyPlus 实际响应。
```

## 14. 当前成本核算与目标函数的区别

需要区分：

```text
MPC 内部优化成本
EnergyPlus 结果汇总成本
```

### 14.1 MPC 内部成本

MPC 内部用 proxy 模型估计：

```text
P_total_pred = P_nonplant_forecast + P_plant_pred
grid_pred = max(0, P_total_pred - PV_forecast)
```

然后最小化：

```text
sum price * dt * grid_pred + penalties
```

### 14.2 EnergyPlus 汇总成本

EnergyPlus 结果中用实际 meter：

```text
facility_electricity_kw = Electricity:Facility / dt
grid_import_kw = max(0, facility_electricity_kw - PV_external)
pv_adjusted_cost = grid_import_kw * price * dt
```

所以结果报告中的成本来自 EnergyPlus 实际响应，不是直接来自 MILP objective。

这也是为什么当前报告会同时记录：

```text
mpc_predicted_chiller_power_kw
chiller_electricity_kw
actual_vs_predicted_chiller_power_mae_kw
```

## 15. 当前实现边界

当前已经实现：

```text
1. MILP 优化 TES signed net dispatch；
2. EnergyPlus Runtime API 在线闭环；
3. TES_Set actuator 写入与 echo 校验；
4. Chiller_T_Set actuator 写入与 echo 校验；
5. measured sampling 参数映射；
6. 温度 safety filter；
7. 四季 controller matrix；
8. cost_comparison_valid 温度安全判据。
```

当前尚未实现：

```text
1. Chiller_T_Set 作为 MILP 决策变量；
2. 室温状态进入 MILP 约束；
3. chiller availability 控制；
4. pump/fan/CRAH 控制；
5. peak objective 默认启用；
6. demand charge 真实结算；
7. EnergyPlus 内部 PV 物理耦合；
8. 完整全年在线收益验证。
```

## 16. 为什么当前矩阵不能作为论文节能主结论

最新 I/O coupling matrix 的 audit 通过：

```text
16/16 case completed
EnergyPlus exit code = 0
TES_Set mismatch = 0
Chiller_T_Set mismatch = 0
fallback_count = 0
```

这说明：

```text
MPC 输出已经能写到 EnergyPlus actuator；
EnergyPlus 在线闭环可以稳定生成结果；
I/O coupling 的工程链路是通的。
```

但结果中所有 MPC rows 都是：

```text
cost_comparison_valid = false
```

原因是：

```text
虽然 PV-adjusted cost 有下降，
但 zone temperature degree-hours 或最高室温相对 no_mpc 恶化。
```

因此当前结果的合理表述是：

```text
I/O-coupled EnergyPlus-MPC feasibility demo passed.
Current control surface still cannot support thesis-grade energy saving claims under temperature safety criteria.
```

不能写成：

```text
MPC 已证明在 EnergyPlus 中节能有效。
```

## 17. 最小复核命令

渲染前可用这些命令复核当前实现：

```powershell
python -m pytest -q
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.audit_controller_matrix --root results/energyplus_mpc_io_coupling_matrix_20260509
```

查看核心结果：

```powershell
@'
import pandas as pd
root = 'results/energyplus_mpc_io_coupling_matrix_20260509'
summary = pd.read_csv(root + '/season_summary.csv')
comparison = pd.read_csv(root + '/comparison_summary.csv')
print(summary[['season','controller','fallback_count','tes_set_mismatch_count','chiller_t_set_mismatch_count','safety_override_count','zone_temp_max_c','temp_violation_degree_hours_27c']])
print(comparison[['season','controller','cost_saving_pct','temp_violation_delta_vs_no_mpc','zone_temp_max_delta_vs_no_mpc','cost_comparison_valid']])
'@ | python -
```

## 18. 代码位置索引

核心 MILP：

```text
mpc_v2/kim_lite/model.py
```

配置对象：

```text
mpc_v2/kim_lite/config.py
```

EnergyPlus adapter：

```text
Nanjing-DataCenter-TES-EnergyPlus/controller/energyplus_mpc/mpc_adapter.py
```

EnergyPlus Runtime runner：

```text
Nanjing-DataCenter-TES-EnergyPlus/controller/energyplus_mpc/run_energyplus_mpc.py
```

I/O coupling 矩阵：

```text
Nanjing-DataCenter-TES-EnergyPlus/controller/energyplus_mpc/run_io_coupling_matrix.py
```

I/O coupling contract：

```text
Nanjing-DataCenter-TES-EnergyPlus/docs/mpc_io_coupling_contract_20260509.md
```

当前 I/O coupling 结果：

```text
results/energyplus_mpc_io_coupling_matrix_20260509/
```
