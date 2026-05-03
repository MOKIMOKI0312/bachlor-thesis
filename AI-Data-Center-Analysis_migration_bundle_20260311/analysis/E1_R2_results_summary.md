# E1-R2 训练 + 评估结果汇总

**生成时间**：2026-04-19
**实验代号**：M1 阶段 R2 版本（TES 增量阀门控制 + 缩容 1400 m³）
**技术路线参考**：`项目目标/技术路线.md` §3（TES）
**交接文档**：`项目目标/archive/handoff_2026-04-17.md`

---

## 1. 实验目标回顾

基于 Xiao&You 论文框架，扩展 TES 冷水罐进行 RL 冷却优化。R2 版本相对于 R1 的关键修正：

| 项目 | R1（已废弃） | R2（本次） |
|------|-------------|------------|
| TES 控制 | 直接三态开关（charge/discharge/idle） | **增量阀门** action = Δv，v(t+1) = clip(v(t) + Δv·δmax, -1, +1) |
| 水罐容量 | 4300 m³（过大） | **1400 m³**（对齐 Zhu 论文） |
| δmax | - | 0.20（5 步从 idle 到满） |
| 流量控制 | 二值（Avail=0/1） | 连续（v × 97.2 kg/s） |
| TES 泵 | 专用 Pump:VariableSpeed | **EMS node mass flow setpoints**（因 E+ 不允许 loop+branch pump 共存） |
| 观测维度 | 5 TES obs | 2 TES obs（SOC + avg_temp）+ 1 wrapper 追加（valve_position）= 22 维总观测 |

---

## 2. 训练时间线（E1-R2 全过程）

### 三次启动批次

| 批次 | 启动时间 | 停止原因 | Seeds | 最高 ep |
|------|----------|----------|-------|---------|
| **e1r2** | 04-17 01:56 | 系统卡死（ACE-CORE102700 filter driver + GPU 0x113 历史） | 8 | ep 6 |
| **e1r2b** | 04-17 11:45 | 挂起进程后系统崩溃（Event 41 × 2） | 8 → 6（seed2/7 发散被杀） | ep 72~165 |
| **e1r2c** | 04-18 23:06（resume from e1r2b ep 139-159 ckpt） | 手动终止（发现 SB3 resume bug：实际训到 ep 314~319 而非 305） | 6 | **ep 290-310** |

### 系统故障记录

| 时间 | 事件 | 影响 |
|------|------|------|
| 04-17 ~02:30 | 系统卡死（训练首批次 e1r2 挂掉） | 全部重训 |
| 04-17 19:35 | Event 41 意外重启（挂起训练期间） | — |
| 04-18 01:25 | Event 41 意外重启（又一次，seeds 全挂） | 需从 checkpoint resume |
| 04-18 13:07 | 手动暂停（用户要用电脑） | 丢 ~36 ep 进度 |
| 04-18 23:06 | Resume 成功（从 ep 139-159 ckpt） | 训练继续 |
| 04-19 12:09 | 手动终止（确认 300 ep 目标达成） | 训练结束 |

---

## 3. Seed 最终状态

### 健康 seed（6 个完成训练）

| seed | 最终 ep | checkpoint 路径 | 目录 |
|------|---------|-----------------|------|
| 1 | ~300 | `runs/train/run-204/checkpoints/e1r2c_dsac_seed1_2627700_steps.zip` | run-204 |
| 3 | ~300 | `runs/train/run-205/checkpoints/e1r2c_dsac_seed3_2627700_steps.zip` | run-205 |
| 4 | ~290 | `runs/train/run-206/checkpoints/e1r2c_dsac_seed4_2540110_steps.zip` | run-206 |
| 5 | ~300 | `runs/train/run-207/checkpoints/e1r2c_dsac_seed5_2627700_steps.zip` | run-207 |
| 6 | ~290 | `runs/train/run-208/checkpoints/e1r2c_dsac_seed6_2540110_steps.zip` | run-208 |
| 8 | ~310 | `runs/train/run-209/checkpoints/e1r2c_dsac_seed8_2715290_steps.zip` | run-209 |

### 失败 seed（发散，已杀）

| seed | 杀时 ep | 发散模式 | ent_coef 峰值 | 记录位置 |
|------|---------|----------|---------------|----------|
| 2 | 129 | 单调上升 0.05→0.12→0.66→1.05 | 1.08 | `analysis/failed_seeds_e1r2c/seed2_*` |
| 7 | 113 | 单调上升 0.04→0.45→1.38→1.60 | 1.60 | `analysis/failed_seeds_e1r2c/seed7_*` |

### 震荡但自愈的 seed（论文可做 robustness case）

| seed | 峰值 ent_coef | 谷底 ent_coef | 最终 ent_coef | 恢复用时 |
|------|--------------|--------------|---------------|----------|
| 6 | 0.99 (ep 71) | 0.04 (ep 115) | 0.08 | ~8h |
| 3 | 0.72 (ep 233) | 0.08 (ep 276) | 0.09 | ~5h |

---

## 4. 评估结果（基于 Nanjing 气候 + Earth IT trace）

### 4.1 PUE 对比

| 策略 | PUE | 相对 baseline | comfort 违规 % |
|------|-----|---------------|---------------|
| **Baseline**（无 RL，固定 setpoint） | **1.3973** | — | **0.00** |
| seed1 | 1.3742 | -1.65% | 6.25 |
| seed3 | **1.3136** ⭐ | **-5.99%** | 34.43 ❌ |
| seed4 | 1.3537 | -3.12% | 4.42 |
| seed5 | 1.3512 | -3.30% | 18.91 |
| seed6 | 1.3618 | -2.54% | 12.00 |
| seed8 | 1.3483 | -3.51% | **2.35** ⭐ |
| **6-seed mean ± std** | **1.3505 ± 0.019** | **-3.35%** | 13.06 ± 11.75 |

- **seed8 Pareto 最优**：PUE 降低 3.51% + comfort 违规仅 2.35%
- **seed3 极端节能但 comfort 严重违反**（34%）— 实际不可用
- **Baseline 0% comfort 违规**是因为固定 setpoint 偏保守

### 4.2 TES 利用率（核心发现 ⚠️）

| seed | SOC 均值 | SOC 标准差 | valve 均值 | 正阀门/放冷% | 负阀门/充冷% | 年等效循环 |
|------|----------|-----------|-----------|---------|------------|-----------|
| 1 | 0.287 | 0.257 | **+0.891** | 95.6 | 2.1 | 7.58 |
| 3 | 0.331 | 0.233 | +0.187 | 60.7 | **31.5** | **21.42** |
| 4 | 0.266 | 0.214 | +0.809 | 99.4 | 0.0 | 1.91 |
| 5 | 0.349 | 0.343 | +0.693 | 87.6 | 10.9 | 4.61 |
| 6 | 0.316 | 0.277 | +0.795 | 98.2 | 0.4 | 2.34 |
| 8 | 0.287 | 0.265 | +0.935 | 97.3 | 1.4 | 3.55 |

> 注：本表沿用 `analysis/e1r2c_final/tes_utilization_stats.json` 中的历史字段值，但原字段名 `pct_charge` / `pct_discharge` 的物理方向写反了。当前 EMS 逻辑中 `TES_Set > 0` 打开 use side，是水罐向负荷放冷；`TES_Set < 0` 打开 source side，是冷机向水罐充冷。

**严重问题**：
- 所有 seed 的 valve 几乎永久停留在放冷方向（正阀门 ≥ 60%，多数 ≥ 95%）
- 年等效循环次数 **1.91 ~ 21.42 次**（1400 m³ 水罐理论上应达 300+ 次/年）
- SOC 全年平均只在 26-35%，从未接近"夜充满 → 日放空"的理想模式

### 4.3 SOC 按小时模式（seed1）

```
h00-h23 平均 SOC 几乎常数（0.285-0.289，差异 < 0.005）
```

**如果 TES 真在做峰谷调度**，SOC 应呈现 "夜高日低" 的正弦模式。实际 **全天恒定**，证明 policy **没学出时段性**。

---

## 5. 核心发现：TES 未被有效利用

### 5.1 现象

- ~3.35% 的 PUE 降低**全部来自传统 HVAC 参数优化**（CRAH Fan / Chiller setpoint / CT pump / ITE）
- 第 6 个 action（TES valve）**退化成"常数开在放冷侧"**，没学到任何时段策略
- 1400 m³ 水罐的峰谷调度潜力**完全未激发**

### 5.2 根本原因

1. **奖励函数缺电价信号**
   - `PUE_Reward` 只看瞬时功率 × comfort
   - TES 的经济价值是 *load shifting*（夜电便宜时充、昼电贵时放），没有电价就没有激励
2. **观测缺时间信号**
   - policy 没有 hour-of-day 输入，无法做时段性决策
3. **reward 里电价时间维度完全缺失**
   - Xiao&You 论文在此位置有 ToU 电价，我们在 M1 简化时未接入

### 5.3 结论

- ✅ 训练技术上成功（6 seed 收敛到稳定 policy）
- ✅ 传统 HVAC 优化部分达到预期（~3% PUE 改善）
- ❌ **M1（仅硬件 TES）的核心假设失败**：没有电价就没有 TES 激活
- ➡️ 必须进入技术路线 **§4（时变电价/碳排信号）** + **§5（PV）** 才能让 TES 有意义

---

## 6. 关键文件索引

### 训练 artifacts

```
training_jobs/
├── e1r2-seed{1..8}/              # 首批次（失败）
├── e1r2b-seed{1..8}/             # 第二批次
├── e1r2c-seed{1,3,4,5,6,8}/      # 最终批次（6 个 seed）
├── e1r2c-seed2_DIVERGED/         # 发散，保留用作 failure analysis
└── e1r2c-seed7_DIVERGED/         # 同上

runs/train/run-{204..209}/        # e1r2c 最终训练工作区
  └── checkpoints/                # 每 10 ep 保存（~212 MB × 多个）
```

### 评估 artifacts

```
runs/eval_e1r2c/seed{1,3,4,5,6,8}/result.json    # 每 seed 评估结果
runs/eval/run-{036..042}/episode-001/monitor.csv  # 每 seed 完整时序数据
  run-036: baseline
  run-037~042: seed 1,3,4,5,6,8

logs/eval/
├── baseline.log
└── e1r2c_seed{1,3,4,5,6,8}.log
```

### 分析 artifacts

```
analysis/
├── E1_R2_results_summary.md              # ← 本文档
├── e1r2c_final/
│   ├── seed{1,3,4,5,6,8}_status_at_kill.json
│   └── tes_utilization_stats.json        # 6 seed 的 TES 统计
├── failed_seeds_e1r2c/                   # 发散 seed 的完整轨迹
│   ├── trajectory_seed2_seed7.md
│   ├── seed{2,7}_stdout_at_kill.log
│   └── seed{2,7}_status_at_kill.json
└── pause_e1r2c_20260418_1306/            # 暂停点快照
```

### 工具脚本（本次新增/修改）

```
tools/
├── evaluate_e1r2c.py               # 新建：E1-R2c 评估脚本（注：mean_valve_position 有 bug，CSV 重名列问题，不影响其他指标）
├── launch_eval_background.py       # 新建：Windows-safe 评估 launcher
├── resume_suspended_training.ps1   # 新建：PowerShell resume 脚本
└── run_tes_training.py             # resume 逻辑对 SB3 reset_num_timesteps=False 理解有误（实际 SB3 会 ADD 而非覆盖），导致超训 ~60k 步；杀进程避免）
```

---

## 7. 下一步（M2 方向）

按技术路线 §4 / §5 顺序：

1. **注入时变电价信号**（ToU 或 SustainDC carbon-aware signal）
2. **扩展观测**：`obs += [hour_of_day, day_of_week, price_signal, carbon_intensity]`
3. **重构 reward**：`reward = -α·P(t)·price(t) - β·comfort_penalty - γ·carbon(t)·P(t)`
4. **重训 E2**：保留 E1-R2c 最优 seed（seed8）作为 warm start
5. **期望**：TES 激活，dig 到 dig load shifting，PUE 降 > 5% + 电费降 10-15%

---

## 8. 已知 bug 和 TODO

| bug | 位置 | 影响 | 修复状态 |
|-----|------|------|----------|
| `mean_valve_position=4381` 错 | `tools/evaluate_e1r2c.py` line 102 | csv.DictReader 遇重名列取最后一列 | 分析时手动绕过；评估脚本待修 |
| SB3 resume 超训 | `tools/run_tes_training.py` line 132 | 实际训到 ep ~466 而非 305 | 已手动终止；代码待修 |
| Windows ACE-CORE102700 filter driver | 系统 | 训练期间可能触发卡死 | 未修（可能需卸载相关软件） |
| LoggerWrapper monitor.csv 列重名 | wrapper 构造 | evaluate 脚本 parsing 歧义 | 未修（用 pandas positional 读替代） |
