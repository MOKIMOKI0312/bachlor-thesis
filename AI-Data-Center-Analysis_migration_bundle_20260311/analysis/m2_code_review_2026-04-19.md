# M2 代码审查报告 — 2026-04-19

> **2026-04-25 superseded note**: 本文审查的是曾计划加入 `WorkloadWrapper` 的 41 维观测 / 6 维动作 M2 草案。当前 M2 已删除 workload/ITE 空置动作维，实际 agent 空间为 32 维观测 / 5 维动作：4 个 HVAC 动作 + `TES_DRL`。因此本文中关于 workload action、`action[4]` ITE 调度、`obs_dim=41`、`action_dim=6` 的建议仅作为历史记录，不再代表当前训练环境。

审查范围：M2-A（数据下载）→ M2-D1（冒烟 + evaluate_m2）共 10 个文件，对照
`项目目标/code-review-request-M2-2026-04-19.md` §1 的文件清单 + §2 的 M1 坑 A–F。

## 总评

- 🔴 高优先级问题：**2** 个（至少 **1 个阻塞 M2-D2 训练**）
- 🟡 中优先级问题：**5** 个
- 🟢 低优先级问题：**4** 个
- **建议**：**需修改后再进入 M2-D2 训练**。H1 会让 WorkloadWrapper 的 defer 分支彻底失效，整个 §2（弹性 IT 调度）的实验设计变成伪命题，必须修；H2 是 41 维 obs 组成偏离技术路线 §6.1，虽不阻塞跑通，但论文 methodology 章节会被审稿人质疑。

---

## 🔴 高优先级问题（阻塞训练 / 撕裂核心实验设计）

### H1. WorkloadWrapper 离散化阈值与 ITE 动作空间 [0,1] 失配 — **defer 分支永远不触发**

- 位置：[workload_wrapper.py:54](sinergym/envs/workload_wrapper.py#L54)、
  [workload_wrapper.py:190-197](sinergym/envs/workload_wrapper.py#L190-L197)、
  [run_m2_training.py:100](tools/run_m2_training.py#L100)
- 问题：
  1. [sinergym/__init__.py:126-127](sinergym/__init__.py#L126-L127) 把 Eplus-DC-Cooling-TES 的 action_space 声明为：
     `low = [0, 0, 0, 0, 0, -1]`、`high = [1, 1, 1, 1, 1, 1]`。
     即 **idx 4（ITE actuator）范围是 [0, 1]**。
  2. SAC 内部输出 tanh ∈ [-1, 1]，经 `unscale_action` 映射到 env.action_space
     后，**训练 / 评估阶段 env.step 看到的 action[4] ∈ [0, 1]**（policy.scale_action 的标准做法）。
  3. WorkloadWrapper 当前阈值是 `(-0.33, 0.33)`，对 [0, 1] 的 raw 值：
     - `raw < -0.33` ⇒ DEFER — **永远为假**
     - `raw < 0.33` ⇒ NOOP
     - `raw ≥ 0.33` ⇒ PROCESS
- 影响：
  - agent 无法选择"延迟负荷"的动作。任务队列永远不会被 agent 主动填充，
    `queue_status / hist_24h_plus / oldest_task_age` 等 9 维队列观测始终 ≈ 0，
    信息价值趋近于零。
  - RL-Cost / RL-Green 的"把负荷挪到便宜/绿电时段"这一核心论文立意，依赖
    workload defer。H1 不修 → **整个 workload 调度实验为伪实验**。
  - 冒烟测试 [smoke_signal_wrappers.py:39](tools/smoke_signal_wrappers.py#L39) 用 mock env
    `action_space = Box(low=-1, high=1, shape=(6,))` 无法捕获此 bug（mock 把所有
    6 维都设为 [-1, 1]，与真实 env 不一致）。测试 defer 时传了 `a[4] = -0.9`
    直接绕过了 unscale 流程，看起来通过。
- 修复建议（二选一）：
  - **方案 A（推荐，最小改动）**：把阈值改为基于 [0, 1] 的等分：
    ```python
    discretize_thresholds: Tuple[float, float] = (1/3, 2/3)
    ```
    语义：`raw < 1/3` → DEFER；`1/3 ≤ raw < 2/3` → NOOP；`raw ≥ 2/3` → PROCESS。
  - **方案 B**：在 wrapper 里重写 action_space[4] 为 [-1, 1]，并在 step 里将
    discretized 后的 utilization 从 [-1, 1] 重新映射回 [0, 1] 写回 action[4]。
    好处：policy 的 6 个动作维度语义更对称；坏处：需要重设 action_space.low/high
    子数组，gym.spaces.Box 不支持 per-dim 改，得新建 Box。
- 验证步骤（修后）：
  1. 真实 env 跑 100 step，统计 `info["workload_action"]` 三类分布应大致均匀。
  2. 跑几次 random policy，`info["workload_queue_len"]` 应增长。
  3. smoke_signal_wrappers.py 改 mock env 的 action_space 为 `low=[0]*5+[-1]`、
     `high=[1]*6`，重跑保证 defer 测试仍通过。

### H2. 41 维 obs 组成偏离技术路线 §6.1（**temperature trend 6 维缺失 + 额外 6 维填充**）

- 位置：[run_m2_training.py:208-211](tools/run_m2_training.py#L208-L211)（只断言 dim 数，不检查 dim 语义）、
  基础 env 登记 [sinergym/__init__.py:119-232](sinergym/__init__.py#L119-L232)
- 问题：obs dim 计数 41 对齐，但**成分**不对齐。

  | 技术路线 §6.1 分组 | 应该有 | 代码实际 | 差异 |
  |--------------------|--------|----------|------|
  | A 时间编码 4 维 | hour_sin/cos + month_sin/cos | 3 维原始 time (month/day_of_month/hour) + 4 维 sin/cos = 7 维 | **多 3 维原始时间**，技术路线明确要 sin/cos 替代 raw |
  | B 室外 2 维 | outdoor_T + outdoor_wetT | 同 | ✓ |
  | C 温度趋势 6 维 | temperature_slope, temp_mean, temp_std, temp_percentile, time_to_next_temp_peak, time_to_next_temp_valley | **完全没有** | **缺 6 维** |
  | D 机房 9 维 | air_T + air_H + CT + CW + CRAH_diff(合并) + 4×act | air_T + air_H + CT + CW + **CRAH_T1 + CRAH_T2（未合并，多 1 维）** + 4×act + **act_ITE** = 11 维 | **多 2 维**（tech route §6.1-D 明确要求合并 CRAH + 删 act_ITE）|
  | E 能耗 2 维 | Electricity:Facility + ITE-CPU | 2 dims + **Water:Facility** = 3 维 | **多 1 维**（tech route §6.1-E 明确要求删 Water）|
  | F 队列 9 维 | SustainDC queue stats | 同 | ✓ |
  | G 电价 3 维 | 同 | 同 | ✓ |
  | H PV 3 维 | 同 | 同 | ✓ |
  | I TES 3 维 | SOC + avg_temp + valve | 同 | ✓ |
  | **合计** | 41 | 41 | dim 数对齐，但 **C 缺 6 + A/D/E 多 6 = 净 0** |
- 影响：
  - 缺失温度 trend 6 维：policy 看不到"未来 6 小时温度是升还是降"，难以做前瞻性蓄冷/
    放冷决策。对 Palo Alto 海洋性气候（日温差 ~10°C）影响尚可，但对论文严谨性
    是红旗 —— 审稿人会追问为何实际 obs 与技术路线不一致。
  - 多出的 3 维 raw time（month / day / hour）与 sin/cos 编码信息重叠，policy
    容量浪费。
  - 多出的 `act_ITE` 与 SustainDC 的 `current_workload` 语义重复（技术路线 §6.1-D
    明确点名要求删 act_ITE）。
  - NormalizeObservation 会把 raw month (1-12)、day (1-31)、hour (0-23) 算进滑动
    均值方差，与 E+ 物理量同一尺度归一，**不会影响计算但会污染 policy 的输入分布**。
- 修复建议（按优先级）：
  1. **必改**：在 TimeEncodingWrapper 或新增 ObservationSliceWrapper 里**显式删掉
     obs[0:3]（raw month/day/hour）**，否则 policy 拿到冗余信号。
  2. **必改**：删 `act_ITE` 和 `Water:Facility` 出 variables/meters（改 `sinergym/__init__.py`
     Eplus-DC-Cooling-TES 注册块），合并 `CRAH_temperature_1/2` 为单个 `CRAH_temp_diff`
     （可以用 EMS Output:Variable 直接给出 diff，或在 wrapper 里 `obs[10] - obs[9]`）。
  3. **补实现**：新增 TempTrendWrapper，参考 SustainDC `extract_ci_features()` 的结构
     读入 TMY EPW 的 outdoor_temperature 时间序列，输出 6 维 lookahead trend 特征。
     这是技术路线 §6.1-C 明确的 6 维，不能省。
  4. **修后加断言**：`run_m2_training.py` 训练前增加：
     ```python
     expected_names = ['hour_sin', 'hour_cos', 'month_sin', 'month_cos',
                       'outdoor_temperature', 'outdoor_wet_temperature',
                       'temperature_slope', 'temp_mean', ...（41 项）]
     assert list(env.get_wrapper_attr('observation_variables')) == expected_names
     ```
- 备注：如果由于排期压力决定**不补** C 类 temp trend（降级为简化版），必须
  在 handoff 里明确记录此偏差，且论文方法章节用"变体说明"标注，**不能默默跑**。

---

## 🟡 中优先级问题（训练前最好修）

### M1. RL_Green 在负电价时的 MWh 反推可能丢数（当 market_price == 0）

- 位置：[rewards.py:1903](sinergym/utils/rewards.py#L1903)
  ```python
  mwh = terms['cost_usd_step'] / market_price if market_price else 0.0
  ```
- 问题：当 `market_price == 0.0` 时，mwh 被强置为 0。随后 `new_cost_usd = 0 × effective_price = 0`。
  但物理上，当 LMP=0 的小时仍然消耗了电，new_cost 应为 `P_facility × effective_price`。
  CAISO 2023 有 144 小时价格为负或近零（见数据 sanity check 结果），这些小时会被错误跳过。
- 影响：小（144/8760 = 1.6%），但逻辑不对；更干净的写法是直接用 `self._energy_MWh(obs_dict)`
  获取 MWh，不去除以 price 反推。
- 修复建议：
  ```python
  mwh = self._energy_MWh(obs_dict)  # ← direct, price-independent
  ```
  同时在 `RL_Cost_Reward.__call__` 的 `terms` 里加 `'mwh_step': mwh`，供子类 RL_Green 直接读取。

### M2. PriceSignalWrapper min-max 归一化被极端值压缩（CAISO 实测 min=-$19, max=$1091）

- 位置：[price_signal_wrapper.py:53-56](sinergym/envs/price_signal_wrapper.py#L53-L56)
- 问题：数据 sanity check 发现 CAISO NP15 2023 的 `mean=$61, min=-$19, max=$1091`（**scarcity 单小时 $1091**
  是 2023-09-06 加州极端热浪事件）。min-max 归一化后 span = $1110，大部分工作日的 $40–$80 小时被
  压缩到 `(80-(-19))/1110 = 0.089` 附近，policy 几乎感知不到每天的 $50 波动（这才是 peak-valley
  套利的主要信号）。
- 影响：
  - `current_price` 信号几乎恒为 0.05–0.10，`price_future_slope` 接近 0，`price_mean` 亦然。
  - RL-Cost 在观测层无法看到有用的电价信号，主要依赖 reward 的梯度。训练效率下降。
- 修复建议：
  - **方案 A（最小改）**：clip 到 [5th, 95th] percentile 做 min-max：
    ```python
    lo = np.percentile(prices, 5)
    hi = np.percentile(prices, 95)
    self._price_norm = np.clip((prices - lo) / max(hi - lo, 1e-6), 0, 1)
    ```
  - **方案 B**：log 变换 `np.log1p(np.clip(prices, 0, None)) / log1p(max_typical)` —— 对负价单独标记。
- 优先级理由：M 不 H 因为论文主要卖点是 "reward shaping 改变 agent 行为"，obs 层降级会让分化更慢
  显现但不会倒置结论。

### M3. PriceSignal / PVSignal / Workload wrapper 维护独立 hour 计数器，与 EnergyPlus 时钟可能不同步

> **2026-04-25 update**: M2 已切到 `timesteps_per_hour=4`。`PriceSignalWrapper`、`PVSignalWrapper`、`TempTrendWrapper` 现在通过底层 `step_size` 推断 `steps_per_hour`，同一小时内 4 个 15-min timestep 使用同一小时索引，不再每步快进 1 小时。M2 未加入 `WorkloadWrapper`，所以 workload 时钟问题不影响当前训练环境。

- 位置：[price_signal_wrapper.py:59, 99](sinergym/envs/price_signal_wrapper.py#L59)、
  [pv_signal_wrapper.py:49, 100](sinergym/envs/pv_signal_wrapper.py#L49)、
  [workload_wrapper.py:71-73, 209-212](sinergym/envs/workload_wrapper.py#L71-L73)
- 问题：3 个 wrapper 都自己维护 `self._hour_idx`（或 `_current_day/_current_hour`），
  reset 时归零，step 时 `% 8760` 递增。但 EnergyPlus 仿真的时钟由 runperiod 控制
  `(1,1,2025, 31,12,2025)`，timesteps_per_hour=1。只要 **每个 env.step 恰好对应 1 小时**，
  wrapper 时钟与 EP 时钟对齐。
- 风险：
  - 若未来改 `timesteps_per_hour=4`（15 min 粒度），wrapper 没跟着走（`_hour_idx` 每步 +1 导致
    读价表比实际快 4 倍）。**现在不是 bug，但改时序会成 bug**。
  - 若某个 episode 提前 terminated（仿真错误），wrapper 的 `_hour_idx` 在下一 reset 归零，
    价格重新从 Jan 1 开始，EP 也重新从 Jan 1 开始 —— 此时反而一致。
- 修复建议：**改从 obs_dict['month', 'day_of_month', 'hour'] 直接算 hour_of_year**
  （与 rewards.py 的 `_hour_of_year()` 一致），彻底消除时钟分离风险。
- 优先级：M（当前 1 step/hr 设计下没实际问题，但改成更细粒度 timestep 时会炸）。

### M4. evaluate_m2 的 TES annual cycles 公式依赖 EMS 流量与 valve 线性成正比的假设

- 位置：[evaluate_m2.py:183-185](tools/evaluate_m2.py#L183-L185)
  ```python
  cycles_rough = valves.abs().sum() * TES_MAX_FLOW_KG_S * 3600 / 1000 / TES_TANK_M3
  ```
- 问题：公式假设 `flow_mass_rate = |v| × 97.2 kg/s`。根据 handoff §8.2，EMS Program P_5
  根据 `TES_Set` 信号计算目标流量。但未确认 flow 是否严格线性比例。若 EMS 里是分段函数
  （如 `v < 0.1 → flow = 0` 死区），则此公式高估了实际循环数。
- 影响：`cycles_rough ≥ 100` 的激活判据可能放得过松 —— 报告说激活但实际还是稳态。M1 已经踩过这个坑。
- 修复建议：
  - 验证方式 1（最快）：在 `DRL_DC_evaluation.epJSON` 里找 `EnergyManagementSystem:Program P_5`
    的源码，确认 flow = MAX × |v|。或问 eplus-modeler subagent 确认。
  - 验证方式 2（更准）：用 `Output:Variable "Chilled Water Thermal Storage Tank Use Side Mass Flow Rate"`
    从 EP 仿真输出里读实际流量，不靠 valve 开度推算。monitor.csv 里加此变量。
- 优先级：M（M2-D2 训练可先训，但激活判定前必须校核）。

### M5. attach_reward 里 reward fn 依赖 obs_dict 的 `TES_SOC` 键而 TES_SOC 是 Schedule Value — 需确认 E+ 会导出此键

- 位置：[run_m2_training.py:132](tools/run_m2_training.py#L132)、
  [rewards.py:1710](sinergym/utils/rewards.py#L1710)
- 问题：`RL_Cost_Reward` 继承 `PUE_TES_Reward`，后者调用 `obs_dict.get('TES_SOC')`。
  在 sinergym/__init__.py Eplus-DC-Cooling-TES 注册里，`variables.TES_SOC` 绑定到
  `('Schedule Value', 'TES_SOC_Obs')` —— 一个 Schedule:Constant 变量（由 EMS 写入）。
  Sinergym 把 variables 值填进 obs_dict 时使用的 key 是 variable 字典的 key（即 `'TES_SOC'`）。
  所以理论上可行。
- 但需要校核：**冒烟测试 smoke_m2_env.py 有没有打印 reward terms 验证 soc 被读到了**？
- 现状：smoke 只打印 reward 标量，未验证 `terms['soc_value']` 非零。需要小改 smoke 打印 terms。
- 修复建议：
  - 短期：smoke_m2_env.py 在每步打印 `info` 字典中的 reward terms（确认有 `soc_value` 且不是 0）。
  - 长期：`RL_Cost/Green_Reward.__call__` 里如果 `soc is None`，打一次 warning（当前是静默返回 0）。
- 优先级：M（如果 SOC 读不到，RL-Cost 退化为仅 PUE + cost，TES 该不做的约束丢失）。

---

## 🟢 低优先级问题（训练后可再修）

### L1. evaluate_m2 没显式处理 pandas.read_csv 的 duplicate column auto-rename

- 位置：[evaluate_m2.py:154-160](tools/evaluate_m2.py#L154-L160)
- 问题：虽然 M2-fix commit `fe90c8a` 在 LoggerWrapper 加了 header dedupe 保险栓，但如果某个
  未来 wrapper 改动再次引入重名列，`pd.read_csv` 会把第二个重名列重命名为 `col.1`。当前代码
  按名读取 `df["TES_valve_wrapper_position"]` 只会拿到第一个同名列（即使重复）。
- 影响：目前 wrapper 链加的列名都是唯一的，不会触发。但对抗回归不足。
- 修复建议：在 `evaluate_m2.py` 开头加：
  ```python
  df = pd.read_csv(monitor_path)
  assert df.columns.is_unique, f"Duplicate columns in {monitor_path}: {df.columns[df.columns.duplicated()].tolist()}"
  ```

### L2. PVSignalWrapper `time_to_pv_peak` 在极夜小时的定义模糊

- 位置：[pv_signal_wrapper.py:54-64](sinergym/envs/pv_signal_wrapper.py#L54-L64)
- 问题：若某一天整天 PV 输出全为 0（连阴雨 / 极夜），`np.argmax(pv_kw[start:end])` 返回 0，
  `hours_to_peak` 就变成 `(0 - hod + 24) / 23` —— 既不物理合理也无实际意义（但也不会 crash）。
- 影响：policy 会看到"距 PV 峰 0-23 小时"的乱跳信号，在全日零 PV 时给错误方向。
- 修复建议：当 `pv_kw[start:end].max() < threshold` 时，把 `hours_to_peak[start:end] = 1.0`（表示
  "今天没 PV 峰"），或新增第 4 维 `has_pv_today` 二值信号。

### L3. generate_pvgis.py 把 2020（闰年）映射到 2023（非闰）只删 Feb 29，不 re-align DST

- 位置：[generate_pvgis.py:74-115](tools/generate_pvgis.py#L74-L115)
- 问题：PVGIS 返回的是 UTC 时间序列。`tz_convert('America/Los_Angeles').tz_localize(None)` 之后再 floor('h')
  会把 PST（UTC-8）小时和 PDT（UTC-7）小时统一成 naive wall clock。2020 的 DST 边界
  （3 月 8 日、11 月 1 日）在 reindex(8760-hour non-DST grid) 时靠 ffill/bfill 填补，
  物理上对 PV 而言是合理近似（PV 峰值不变形）。
- 影响：论文严谨性层面，审稿人可能追问"你的 PV 是 2020 年 DST 下数据，映射到 2023 年标称小时"。
  实际光伏曲线几乎无区别，但值得在注释里明说。
- 修复建议：在 README 或 handoff 里记录"PV 用 2020 源数据 + DST 去除 + 年份重标"。

### L4. run_m2_training.py 的 `timesteps_per_episode - 1` 魔法数字没有注释

- 位置：[run_m2_training.py:266](tools/run_m2_training.py#L266)
  ```python
  timesteps_per_episode = env.get_wrapper_attr("timestep_per_episode") - 1
  ```
- 问题：`-1` 是因为 EnergyPlus 把 Dec 31 23:00 → Jan 1 00:00 边界算两次（EplusEnv 特殊处理）还是其他
  原因，没注释说明。M1 的 `run_tes_training.py` 有同样 `-1`，没注释。
- 修复建议：加一行注释 `# -1 to drop the duplicate wraparound timestep at year boundary`（待确认）。

---

## ✅ 做得好的地方（点名表扬）

1. **SB3 resume bug 彻底修了**（坑 A）。
   - [run_m2_training.py:270](tools/run_m2_training.py#L270) `timesteps = episodes * timesteps_per_episode`，
     不再手工 `+ model.num_timesteps`。
   - [run_m2_training.py:322](tools/run_m2_training.py#L322) `reset_num_timesteps=not bool(args.resume)` 正确联动。
   - commit `fe90c8a` 的 diff 清理彻底，不留 dead code。

2. **LoggerWrapper dedupe 保险栓**（坑 B）。
   - [sinergym/utils/wrappers.py:307-316] 加了 `seen/deduped` 的列名去重，preserve order。
   - [tes_wrapper.py:62](sinergym/envs/tes_wrapper.py#L62) 把 `TES_valve_position` 改名为 `TES_valve_wrapper_position`，
     避免与 E+ actuator `TES_Set` 输出潜在同名冲突。
   - [evaluate_m2.py:154](tools/evaluate_m2.py#L154) 用 `pd.read_csv` 替代 `csv.DictReader`。

3. **obs dim 断言在训练+评估两侧都有** (`expected_obs_dim = 41`)，不会再因维度错位训练到一半才发现。

4. **CAISO / PVGIS 数据质量合格**（见下方 sanity check）。

5. **Wrapper 链顺序逻辑清晰**（Workload 最外层、TES 最内层紧贴 base env），action 和 obs 的
   修改链都单向、可追踪。

6. **reward 对 CAISO 负电价的自然处理**：RL-Cost `cost = mwh × price` 负价 → 奖励 agent 多用电，
   符合真实电力市场激励（除 M1 边界外）。

7. **pilot 基础设施先搭后训练**：[analysis/m2_reward_pilot/](analysis/m2_reward_pilot) 目录存在，α/β
   延迟到 D2 pilot 再调，而不是凭感觉猛调，工程 discipline 好。

8. **冒烟测试双层**：`smoke_signal_wrappers.py`（mock 快速，CI 友好）+ `smoke_m2_env.py`（真实 E+ 端到端），
   分层合理。

---

## 数据 sanity check 结果

### CAISO_NP15_2023_hourly.csv

| 指标 | 值 | 期望区间 | 判定 |
|------|-----|----------|------|
| 行数 | 8760 | 8760 | ✓ |
| 列名 | `['timestamp', 'price_usd_per_mwh']` | 同 | ✓ |
| mean | **$61.34 / MWh** | $20–120 | ✓ 在合理区间（接近 2023 年 NP15 实际 $50–70）|
| min | **-$19.02** | ≥ -$150 | ✓（CAISO midday PV glut 负价正常）|
| max | **$1090.90** | ≤ $2500 | ✓（scarcity event，2023-09-06 加州热浪）|
| NaN 数 | 0 | 0 | ✓ |
| 负价小时数 | 144（1.6%）| < 5% | ✓ 符合 NP15 年度统计 |
| 首行 | `2023-01-01 00:00:00, $152.97` | 1 月初冬季高价 | ✓ |

### CAISO_PaloAlto_PV_6MWp_hourly.csv

| 指标 | 值 | 期望区间 | 判定 |
|------|-----|----------|------|
| 行数 | 8760 | 8760 | ✓ |
| 列名 | `['timestamp', 'power_kw']` | 同 | ✓ |
| mean | 1191.78 kW | — | ✓ 日均 ~ 1.2 MW 合理（6 MWp × CF 0.2）|
| min | 0.00 | ≥ 0 | ✓ |
| max | 5287.44 kW | ≤ 6000 kW | ✓ 峰值 88% of 装机，合理 |
| 零发电小时数 | 4373（49.9%）| ≈ 50% | ✓ 夜间占一半 |
| 年发电量 | **10.44 GWh** | — | ✓ |
| 年单位装机产能 | **1740 kWh/kWp** | 1500–1900 | ✓ NorCal 典型 |
| 夏至日（Jun 21）峰值位置 | argmax=13h，max=4282 kW | 11h–14h | ✓ |
| 冬至日（Dec 21）峰值位置 | argmax=12h，max=4284 kW | 11h–13h | ✓ |
| 月度发电（MWh）| Jan 593 → Jul 1049 → Dec 670 | 夏冬比 ~1.5–2.0 | ✓ 夏冬比 1.77 |

**两个 CSV 都通过 sanity check，可以进入训练。**

注：夏至和冬至的日峰值接近（4282 vs 4284 kW）看似反常，但这是**单日极清洁天**的峰值，
与月度总量（Jul 1049 vs Dec 670 MWh）的差异不矛盾 —— 月度差异体现在清天数量和日长上，不在单日峰值。

---

## 冒烟测试覆盖度评估

### smoke_signal_wrappers.py（mock env，快）

**覆盖得好**：
- obs 维度递增（+4/+3/+3/+9）
- reset 后 info 含 `current_price_usd_per_mwh` / `current_pv_kw`
- 时间编码在 hour 0 month 1 的数值精度（sin=0, cos=1）
- PV 24h 曲线形状（峰值在 9-15h 之间）
- obs 范围约束（price/pv slice ∈ [0,1] / [-1,1]）
- 队列 defer / process 动作语义（3 次 defer 后 queue 增长）

**未覆盖**（对应 H1 盲点）：
- Mock env 的 action_space = `Box(-1, 1, shape=(6,))`，**与真实 Eplus-DC-Cooling-TES 的
  `low=[0,0,0,0,0,-1]` 不一致**，导致 workload 的 [0, 1] 离散化 bug 完全测不到。
- 没测试 hour 索引跨 8759 → 0 的 wrap（年底最后 6 小时 lookahead 是否正确绕回年初）。
- 没测试 PriceSignal 的 min-max 归一化在极端值上的表现（应发现 M2）。

### smoke_m2_env.py（真实 E+，3 step）

**覆盖得好**：
- obs_dim == 41 / action_dim == 6 断言
- reset + 3 step 不抛异常
- info 含 price/pv 原始值
- 选择 RL-Cost vs RL-Green 分支都能跑

**未覆盖**：
- 只跑 3 step，无法验证年度统计 / TES 激活指标
- 没断言 reward `info` 中 `terms['soc_value']` 非零（对应 M5）
- 没验证在 **真实 action_space 下** workload 的 defer/process/noop 三类动作分布（对应 H1）
- 没验证完整一个 episode，runperiod 8760 h 跑完是否还 alive

---

## M2-D2 训练前检查清单

- [ ] **H1**：workload 离散化阈值改为 `(1/3, 2/3)` 并验证 action[4] 实际分布
- [ ] **H2a**：TimeEncodingWrapper 或新建 ObservationSliceWrapper 删 obs[0:3] raw time
- [ ] **H2b**：sinergym/__init__.py 删 `act_ITE` / `Water:Facility` / 合并 `CRAH_temperature_1/2`
- [ ] **H2c**：补实现 TempTrendWrapper（+6 维）或书面接受简化并在 handoff 记录偏差
- [ ] **H2d**：训练前加 `observation_variables` 名称列表断言
- [ ] **M1**：RL_Green 的 MWh 反推改用 `self._energy_MWh(obs_dict)`
- [ ] **M2**：PriceSignal 归一化改 percentile clip（或明确接受原地不动，记入 handoff）
- [ ] **M4**：确认 EMS P_5 的 flow = MAX × |v| 线性比例，否则改 monitor.csv 直接读 mass flow
- [ ] **M5**：smoke_m2_env.py 打印 reward terms 确认 `soc_value` 非空
- [ ] **L1**：evaluate_m2 加 `df.columns.is_unique` 断言
- [ ] （α/β pilot 验证留到 D2 自行 tune，不属审查范围）

---

## 🚨 紧急通知

**H1 是严重 bug，会让"负荷调度"这一论文 Chapter 4 主实验完全失效**。修 1 行代码（改
`discretize_thresholds` 默认值）即可。**强烈建议先修 H1 再考虑 8-seed launcher**。否则训练 7 天
得到的 RL-Green 与 RL-Cost 的 policy 差异，只来自 TES 维度 + HVAC 维度，workload 维度近乎常数，
论文结论会被大幅削弱。

**H2 是偏离技术路线但不阻塞跑通**。如果排期紧，可以："先跑 H1 fix 版本，看 workload 实际是否对
policy 分化有显著贡献；若无显著，再回补 H2"。但这样做需要在论文方法章节**明确写清偏差**，避免
evaluation 被审稿人 reject。

---

*审查时间：2026-04-19 下午*
*审查人：新 CC session（在 worktree hardcore-euler-726f6f 里工作）*
*审查请求文档：项目目标/code-review-request-M2-2026-04-19.md*
*审查对应 commits：`fb08455` → `b27a744`（共 9 个 M2 commits）*
*数据 sanity check 运行时间：~3 秒*
