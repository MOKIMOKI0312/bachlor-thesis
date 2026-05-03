# Handoff for GPT Codex — 2026-04-25

> 给 OpenAI GPT Codex 的项目交接文档。设计为自包含：你不需要先读其他文档也能上手。深入细节时再按 §0 顺序读官方文档。

---

## 0. 速读指引（按时间余量选择）

| 时间预算 | 顺序 |
|---|---|
| **5 min** | 本文件 §1 + §2 + §6 |
| **20 min** | + 本文件全部 + `项目目标/技术路线.md` §6（41 维 obs / 6 维 action 的精确成分）|
| **40 min** | + `毕业设计项目进度/代码开发进度管理.md` §7（M2 任务表 + 已修 9 bug 清单）+ `项目目标/决策-切回-Nanjing-Jiangsu-TOU-2026-04-22.md` |
| **充分** | + 上一份 handoff `项目目标/handoff_2026-04-19.md`（Singapore→CAISO 的弃用决策上下文）|

**仓库根目录**：`C:\Users\18430\Desktop\毕业设计代码\`
**核心代码 / 数据 / 工具**全部在子目录 `AI-Data-Center-Analysis_migration_bundle_20260311/`，下文用 `<repo>/` 简写。

---

## 1. 项目背景（30 秒）

- **题目**：面向光伏自消纳的 AI 数据中心冷却-蓄冷-算力联合优化系统设计（东南大学能动专业本科毕设）
- **基础框架**：Xiao & You (2026) Sinergym/EnergyPlus 数据中心仿真（已剥离原作占位 PV/电池）
- **技术栈**：EnergyPlus 23.1 + Sinergym（fork）+ Stable-Baselines3 + Gymnasium + 自实现 DSAC-T
- **核心研究问题**：在同一站点同一硬件下，**RL-Cost reward**（最小化购电成本）与 **RL-Green reward**（最大化 PV 自消纳）会让 agent 学出**方向性不同**的 TES 蓄冷 + 弹性 IT 调度策略。
- **当前主站点**：**Nanjing + 江苏 2025 TOU 合成电价 + Nanjing PVGIS**（2026-04-22 决策，详见 §3）
- **决策权属**：所有重大设计变更（站点、reward 公式、obs 维度、容量参数）需先和用户对齐。GPT Codex 不要擅自切站点 / 改电价 / 改 obs 顺序。

---

## 2. 当前仓库状态（2026-04-25 ~14:50 UTC+2）

### 2.1 Git
- **本地分支**：`master`（仅一个；之前 34 个 `claude/*` worktree 分支全部 push 后清理）
- **HEAD**：`d885ae0f [cleanup] gitignore: 排除 *.rar`
- **上游**：`origin = https://github.com/MOKIMOKI0312/bachlor-thesis`（**Public**，全部分支已 push 备份）
- **关键近期 commit**（master 上的 M2 链路，从老到新）：
  ```
  bc10db0   [M2-E3b-v4-fix] Price signal 重写 3 维 TOU-aware + α 5e-4→2e-3
  3d0f178   [M2-B1-fix] P_5/P_7 chiller-kill 方向修正
  81e298b   [M2-B3B4-fix] EnergyScaleWrapper + obs_rms warmup freeze
  f5df387   [M2-B4-v2-fix] warmup 改 random action + obs_rms.var floor 1e-2
  66e98e1   [M2-DSAC-align] 对齐 DSAC-v2 官方 4 道防线修 critic σ 爆炸
  f5975ee   [M2-PBRS] Ng-Harada-Russell PBRS Φ_A = κ(SOC-0.5)(0.5-price_norm)
  429e3850  [M2-PBRS-v2] DPBA upgrade Φ + target_entropy=-2.0 + log_alpha floor
  8fb4cfbe  [M2-PBRS-v3] cost_term clip ±3→±8 (Jiangsu TOU 不需 CAISO 紧 clip)
  5f706eed  [M2-PBRS-v4] 移除 exp(-h/τ) 时间衰减，Φ 24h 全时段活跃
  6a0db391  [M2-PBRS-final] 回退到 DPBA v1 公式 (exp decay) + 保留 clip±8
  a58e7f1a  [M2-PlantFix] 修复 TES Use 分支不放冷的真正 root cause - 4 项
  405d70c0  [M2-PlantFix-followup] 关闭 Chiller Bypass 期间放电 + 季节性验证
  321c2293  [M2-merge] 合并 integrate-all-fixes 全部内容
  84ceaa15  [M2-merge-validation] integrate-all-fixes 合并后系统/组件双层验证 + ITE pipeline 调研  ← M2 工作的最新可信状态
  ```

### 2.2 Stash（开工前请审查并选择性 apply 或 drop）
```
stash@{0}: WIP-pre-master-merge-2026-04-25  (epJSON + 建筑模型说明.md)
stash@{1}: WIP-pre-master-merge-2026-04-25-part2  (4 个文件)
stash@{2}: WIP-pre-master-merge-2026-04-25  (其他)
```
这些是合并 elastic-jepsen 前在 master 工作树中的未提交修改，**不确定是否需要保留**。开工前请用 `git stash show -p stash@{N}` 看 diff，决定 apply 还是 drop。

### 2.3 当前 untracked 但有保留价值的资产（详见 §4）
14 项分析数据 + 验证脚本输出，全部位于 `<repo>/` 下：
```
analysis/m2_e3_lr1e4_FAILED/        ← M2-E3 lr=1e-4 失败诊断报告 + 4 seed 数据
tools/m1/component_iso_20260425-122322/  ← T1-T12 组件隔离测试
tools/m1/audit_baseline/            ← 基线审计输出
tools/m1/smoke_p5fix_20260425-121045/    ← P5 fix smoke test
tools/m1/v1_20260425-120925_7d/     ← 7 天 v1 验证
tools/m1/probe_valve_soc_out/       ← Valve/SOC 探针
tools/m1/smoke_tes_init_probe/      ← TES 初始化探针
tools/m1/smoke_tou/                 ← TOU 模式 smoke
tools/m1/verify_components_out/     ← Phase A 41+4 PASS 报告（重要！见 §5.2）
tools/m1/audit_annual_probe.py / audit_baseline_probe.py / smoke_tou_pattern.py
tools/launch_m2_f1_full.sh
tmp_audit/  (主仓库根目录)
```
这些**目前是 untracked**，不在 git 历史中。是否要 `git add` 到 master，由你和用户讨论后决定（建议保留为 untracked，避免再次让仓库膨胀）。

---

## 3. 站点 + 数据配置（不要改）

| 维度 | 配置 | 路径 |
|---|---|---|
| 气象 | Nanjing TMYx 2009-2023 | `<repo>/Data/weather/CHN_JS_Nanjing.582380_TMYx.2009-2023.epw` |
| 电价 | 江苏 2025 合成 TOU（4 段 × 3 季节，8 价位 29-200 USD/MWh，kurtosis = -1.3）| `<repo>/Data/prices/Jiangsu_TOU_2025_hourly.csv` |
| PV | Nanjing PVGIS（32.06°N, 118.80°E，27° tilt，6 MWp c-Si，年发电 7.14 GWh）| `<repo>/Data/pv/CHN_Nanjing_PV_6MWp_hourly.csv` |
| Building | DRL_DC_training.epJSON / DRL_DC_evaluation.epJSON（含 TES 4300→1400 m³ + Plant 修复）| `<repo>/Data/buildings/` |

**为什么不能切回 CAISO**：CAISO NP15 2023 kurtosis ≈ 120（极端重尾），DSAC-T critic σ² 爆炸，6 seed × 300 ep 实验 33% 收敛率。详见 `项目目标/决策-切回-Nanjing-Jiangsu-TOU-2026-04-22.md` 和 `analysis/m2_e3b_v2_CAISO_FAILED/FAILURE_REPORT.md`。

**论文章节安排**：CAISO 失败实验留作 Chapter 5「算法边界 / 鲁棒性挑战」案例研究，**不删数据**。

---

## 4. 41 维 obs / 6 维 action（精确）

### 4.1 Wrapper 链（inner → outer）
```
EplusEnv (base 20 维)
  → TESIncremental                                   (20 维)
  → TimeEncoding  (drop raw time + CRAH merge + sin/cos, 20 维)
  → TempTrend     (+6 → 26 维)
  → PriceSignal   (+3 → 29 维)
  → PVSignal      (+3 → 32 维)
  → Workload      (+9 → 41 维)
```

### 4.2 各 wrapper 输出维度（与技术路线 §6.1 对齐）
- TimeEncoding 4 维：`hour_sin / hour_cos / month_sin / month_cos`
- TempTrend 6 维：`outdoor_T_slope / mean / std / percentile / time_to_peak / time_to_valley`
- PriceSignal 3 维：`price_current_norm / price_future_slope / price_future_mean`（**5/95 percentile clip 归一化**，commit `36e05a1`，绝对禁止改 min-max）
- PVSignal 3 维：`pv_current_ratio / pv_future_slope / time_to_pv_peak`
- Workload 9 维：队列状态（详见 `<repo>/sinergym/envs/workload_wrapper.py`）

### 4.3 Action 6 维
1. CRAH_Fan
2. CT_Pump
3. CRAH_T setpoint
4. Chiller_T setpoint
5. **Workload action**（连续 [0,1]，wrapper 内部用 `(1/3, 2/3)` 阈值离散化为 `RUN/DEFER/SHED`，**不是 ±0.33**）
6. **TES 增量阀门**（[-1,+1]，符号即方向；δ_max=0.20）

---

## 5. 已完成工作（M2 链路全景）

### 5.1 M0 → M1 速通
- **M0 / E0 / E0.1 / E0.2 / E0.3**：12 seed × 300 ep DSAC-T 基线，PUE 1.3071 ± 0.022（baseline 1.3973，改善 6.45%）
- **M1（E1-R2c）**：6 seed × ~305 ep 带 TES，**PUE 倒退到 1.3505**（vs E0.3 1.3071），**TES 年循环仅 1.91-21.42 次**（理论 ≥300）。**根因：reward 缺电价信号 + obs 缺 hour_of_day**，TES 退化为常数阀门。详见 `analysis/E1_R2_results_summary.md`。
- **M1 论文价值**：作为 ablation"加 TES 不加电价的反面教材"，seed8 ckpt 保留为 Pareto 最优代表。

### 5.2 M2 实施（重点）

**整体路线**：M2 把 price + PV + time encoding + workload 一次性加全（避免 M1 那种"加硬件不加信号"的退化）。

**已完成（按 commit 链）**：
- **M2-A**：江苏 TOU + Nanjing PVGIS 数据生成 + 站点切换
- **M2-B1-B6**：6 个 wrapper（PriceSignal / PVSignal / TimeEncoding / TempTrend / Workload / 链组合）
- **M2-C1-C3**：RL_Cost / RL_Green reward + α/β pilot 框架
- **M2-D1**：双层 smoke test（mock 快测 + 真实 E+ 3-step），3 种 reward 数值差异验证 patch 生效（避免 R1 那种 reward fn 静默退化）
- **M2 代码审查 11 bug 全修**（H1, H2a-d, M1-M5, L1-L4），最严重是 R1：reward_fn 因 gymnasium Wrapper `__getattr__` 转发导致 patch 落不到 `env.unwrapped`。详见 `代码开发进度管理.md` §7.6。
- **M2-PBRS 系列（v1→v2→v3→v4→final）**：4 轮 PBRS（Potential-Based Reward Shaping）公式迭代，最终回退到 DPBA v1 公式 + clip ±8（Jiangsu TOU 比 CAISO 宽容，可放宽 clip）
- **M2-DSAC-align**：对齐 DSAC-v2 官方 4 道防线修 critic σ² 爆炸（warmup random action / obs_rms.var floor 1e-2 / EnergyScaleWrapper / log_alpha floor）
- **M2-PlantFix（4 项）**：修复 EnergyPlus 中 TES Use 分支不放冷的 root cause（关闭 Chiller Bypass 期间放电 + 季节性验证）
- **M2-merge-validation（HEAD = 84ceaa15）**：组件级 Phase A/B 验收 **41 PASS / 4 SKIP / 0 FAIL / 0 WARN**。验证报告完整保留在 `tools/m1/verify_components_out/report.md`，包括：
  - C1-C9 TES 能量平衡（drift 0.05，远低于 0.20 阈值）
  - C10-C19 各组件流量 / 温度 / EMS P_1/P_2 行为
  - C20 EMS P_5/P_7 TES 响应（discharge→use_avail≈1，charge→source_avail≈1）
  - C21 severe=0 fatal=0
  - C22 PUE = 1.3774（A1 Jul TOU TES 7 天 / A2 Jan passive 7 天）

### 5.3 失败实验记录（不要重蹈覆辙）
| 失败 | 配置 | 结果 | 教训 |
|---|---|---|---|
| **M2-E3 lr=1e-4** | DSAC-T `[256,256]` lr=1e-4 + CAISO + 4 seed × 300 ep | 1/4 收敛（25%）；seed2 ent=24.4，seed3 ep107 突然爆炸 | **DSAC-T + extreme-tail reward 必须 lr ≤ 5e-5** |
| **M2-E3b-v2** | A+C 修复（reward clip ±3 + price tanh）+ CAISO + 6 seed | 2/6 收敛（33%），seed4/5 omega 到 10⁷-10⁸ | A+C 治标不治本，CAISO 重尾分布与 DSAC-T Gaussian critic 根本不兼容 |

详见 `analysis/m2_e3_lr1e4_FAILED/FAILURE_REPORT.md` 和 `analysis/m2_e3b_v2_CAISO_FAILED/FAILURE_REPORT.md`。

---

## 6. 下一步任务（M2-D2 起，**就绪未启动**）

按 `代码开发进度管理.md` §7.4 的任务表：

| ID | 任务 | 验收标准 | 状态 |
|---|---|---|---|
| **M2-D2** | E3 训练（RL-Cost），4 seed × 300 ep，**lr=5e-5**（不是 1e-4） | 训练完成、PUE / 电费 / TES 利用率指标可读 | READY |
| **M2-D3** | E4 训练（RL-Green），同上 | 同上 | READY |
| **M2-D4** | 对比评估（PUE / 电费 / 峰值削减 / TES 年循环 / Workload 延迟） | 5 指标 RL-Cost vs RL-Green 表格 | READY |
| **M2-D5** | TES 激活验收 | **年循环 ≥ 100、SOC 日内幅度 ≥ 0.3、夜充日放可见** | READY |

### 6.1 启动模板（实际命令）

```bash
cd C:/Users/18430/Desktop/毕业设计代码/AI-Data-Center-Analysis_migration_bundle_20260311

# 必设环境变量（每次新 shell）
export EPLUS_PATH="$PWD/vendor/EnergyPlus-23.1.0-87ed9199d4-Windows-x86_64"
export PYTHONPATH="$PWD:$EPLUS_PATH"

# 推荐先跑 smoke 验证一切正常
D:/Anaconda/python.exe tools/smoke_m2_env.py

# E3 (RL-Cost) 4 seed 后台并行启动
for seed in 1 2 3 4; do
  D:/Anaconda/python.exe tools/launch_training_background.py \
    --repo "$PWD" \
    --episodes 300 \
    --seed $seed \
    --device cpu \
    --algo dsac_t \
    --learning-rate 5e-5 \
    --model-name "e3_rl_cost_seed${seed}" \
    --checkpoint-episodes 10 \
    --job-name "m2-e3-seed${seed}" \
    --python-exe D:/Anaconda/python.exe \
    --training-script tools/run_m2_training.py \
    --reward rl_cost
  sleep 20  # 错峰防 IO spike
done

# E4 (RL-Green) 待 E3 跑完磁盘空间允许后启动
# ...同上但 --reward rl_green --model-name "e4_rl_green_seed${seed}"
```

### 6.2 巡检命令

```bash
# 系统 uptime（< 0.5h 说明又崩了，要查 Event 41）
powershell -Command "\$up = (Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime; 'uptime {0:N2}h' -f \$up.TotalHours"

# python 进程数
tasklist //FI "IMAGENAME eq python.exe" | grep -c "python.exe"

# 每 seed 状态
for seed in 1 2 3 4; do
  D:/Anaconda/python.exe -c "
import json
s=json.load(open(f'training_jobs/m2-e3-seed${seed}/status.json'))
tm=s.get('training_metrics',{}) or {}
print(f'seed${seed} ep={s[\"approx_episode\"]} ent={tm.get(\"train/ent_coef\",0):.3f} critic={tm.get(\"train/critic_loss\",0):.2f}')
"
done
```

---

## 7. 关键文件索引

### 7.1 训练 / 评估入口
| 文件 | 用途 |
|---|---|
| `<repo>/tools/run_m2_training.py` | M2 训练主入口（41 维 obs / 6 维 action）|
| `<repo>/tools/launch_training_background.py` | Windows 安全 detach 后台启动器 |
| `<repo>/tools/evaluate_m2.py` | M2 评估（自带 P_5 死区掩膜 + 列唯一断言）|
| `<repo>/tools/launch_eval_background.py` | 评估后台启动器 |
| `<repo>/tools/smoke_m2_env.py` | 真实 E+ 3-step smoke（开训前必跑）|
| `<repo>/tools/smoke_signal_wrappers.py` | mock 快测，wrapper 链单元测试 |

### 7.2 算法 / 环境
| 文件 | 用途 |
|---|---|
| `<repo>/tools/dsac_t.py` | DSAC-T 算法（含 R3 方差缩放）|
| `<repo>/tools/distributional_critic.py` | 分布式 Critic 实现 |
| `<repo>/sinergym/envs/tes_wrapper.py` | TESIncremental（δmax=0.20）|
| `<repo>/sinergym/envs/price_signal_wrapper.py` | 5/95 percentile clip 归一化 |
| `<repo>/sinergym/envs/pv_signal_wrapper.py` | 3 维 PV 信号 |
| `<repo>/sinergym/envs/time_encoding_wrapper.py` | 4 维时间编码 + raw time drop + CRAH merge |
| `<repo>/sinergym/envs/temp_trend_wrapper.py` | 6 维温度趋势 |
| `<repo>/sinergym/envs/workload_wrapper.py` | 9 维队列 + (1/3, 2/3) 离散化 |
| `<repo>/sinergym/utils/rewards.py` | `PUE_TES_Reward` / `RL_Cost_Reward` / `RL_Green_Reward` |

### 7.3 文档
| 文件 | 用途 |
|---|---|
| `项目目标/技术路线.md` | 设计规范（41 维 / 6 维 / 站点 / 容量）|
| `毕业设计项目进度/代码开发进度管理.md` | 进度文档（章节多）|
| `Data/buildings/建筑模型说明.md` | 建筑模型说明（**改 epJSON 必读 + 必更新**）|
| `项目目标/决策-切回-Nanjing-Jiangsu-TOU-2026-04-22.md` | 站点决策 |
| `项目目标/决策-站点切换-CAISO-2026-04-19.md` | 上一轮决策（已弃用，仅参考）|

---

## 8. 重大约束 / 红线（违反会浪费几十小时训练）

### 8.1 永远不要做
1. **不要切回 CAISO** —— DSAC-T 在 kurtosis≈120 的批发市场重尾分布上不稳定（M2-E3b-v2 实测 33% 收敛率）
2. **不要用 lr ≥ 1e-4 训 DSAC-T** —— M2-E3 实测 1/4 收敛率
3. **不要从 M1 (E1-R2c) warm start** —— M2 41 维 obs vs M1 22 维 obs，shape mismatch；且 M1 的 TES valve 已学坏（常数 prior）
4. **不要并发 ≥ 5 seed** —— 历史触发 `ACE-CORE102700` minifilter + Event 41 系统重启，并发 ≤ 4 是硬限
5. **不要改 reward fn 时只赋值给最外层 wrapper** —— 必须 `env.unwrapped.reward_fn = cls(...)`，且加 isinstance + info-key 抽样断言（参考 commit `4f40b16` 的修复）
6. **不要改 WorkloadWrapper 阈值为 ±0.33** —— action[4] ∈ [0,1]，必须 `(1/3, 2/3)`
7. **不要把 vendor/EnergyPlus / runs/ / wandb / tmp_audit / *.rar 加入 git** —— 历史已经因为这些大文件膨胀过；`.gitignore` 已有规则

### 8.2 改东西必须做的事
- **改 epJSON**：先读 `Data/buildings/建筑模型说明.md`，改完同步更新该文档
- **改 wrapper 链**：先在 `tools/smoke_signal_wrappers.py` 加单元测试，再跑 `tools/smoke_m2_env.py` 真实环境验证
- **改 reward**：跑 3 reward 数值差异冒烟（参考 commit 4f40b16 的 smoke）
- **commit**：先看 `.gitignore`，确保不会带进大文件；`git add -p` 选择性加文件，不要 `git add -A`

---

## 9. 已知 bug / 陷阱

| ID | 位置 | 现象 | 修复 |
|---|---|---|---|
| SB3-resume | `tools/run_m2_training.py` | `reset_num_timesteps=False` 下 SB3 会**再加** `num_timesteps`，老脚本算 `total = already_done + N*steps` 会被加两次 | M2 已修：`total = N*steps`（commit `fe90c8a`），M1 的 `tools/run_tes_training.py` 未修（M1 已结束不再用）|
| monitor.csv 列重名 | LoggerWrapper 构造 + 任何用 csv.DictReader 的脚本 | `TES_valve_position` 出现 2 次，DictReader 取最后一列 = 错值 | M2 已修：`evaluate_m2.py` 加 `assert df.columns.is_unique`（commit `6d48f3a`）|
| Reward patch 静默失效 | `gymnasium.Wrapper.__getattr__` 转发陷阱 | `while hasattr(inner, 'reward_fn'): inner = inner.env` 0 次迭代 | 改用 `env.unwrapped.reward_fn = cls(...)`（commit `4f40b16` / `553e3ad`）|
| Git Bash `nohup ... &` | Windows 上不真正 detach | 父 bash 退出时子进程被 kill | 用 `tools/launch_training_background.py` 的 Python Popen + `CREATE_NEW_PROCESS_GROUP \| DETACHED_PROCESS` |
| `ACE-CORE102700` minifilter | Windows 反作弊 / 云盾驱动 | 8 seed 并发 IO 触发 DPC 超时 → Event 41 蓝屏 | 并发 ≤ 4 seed；可查 NirSoft BlueScreenView |
| EP loop pump + branch pump | EnergyPlus 23.1 不允许同 PlantLoop 共存 | 给 TES 加 Pump:VariableSpeed → fatal | 用 EMS `System Node Setpoint` actuator 直控 mass flow（已实现）|
| wrapper `_hour_idx` | `timesteps_per_hour=4` 时会漂移 | 1 step/hr 下无问题 | 不改 timestep 即可，否则需 patch 各 wrapper 的时钟逻辑 |
| Windows date 时区 | Git Bash `date` 与 PowerShell `Get-Date` 不一致 | 时间戳混乱 | 统一 `powershell -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'"` |

---

## 10. 数据恢复说明（2026-04-25 上下文）

本日（2026-04-25）发生过一次 worktree 清理事故：上一个 Claude Code 会话用 `cp -r` 备份 worktree 内未提交内容时，由于 Windows 文件系统某种异常行为，备份目录大部分内容在后续 `rm -rf worktree` 时被一并删除。**所有 master 上的 git 历史和 GitHub 上的备份都完好**，但有 14 项 untracked 工件（约 148 MB 验证 / 审计 / 失败诊断数据）一度丢失。

**已从用户预先制作的 145 GB `.rar` 备份恢复**，文件回到 §2.3 列出的位置。如果发现哪个文件还少（比如某个 `runs/` 训练日志或 `vendor/EnergyPlus-23.1.0-...`），可以从 `毕业设计代码.rar` 单独提取（路径前缀 `毕业设计代码\.claude\worktrees\<wt名>\...`）。

**被 ignore 的备份资源**：
- `毕业设计代码.rar` 本体（145 GB，已加 `*.rar` 到 .gitignore）
- 早期 `_worktree_artifacts_backup_2026-04-25/`（已清理）
- 3 个空壳 worktree 目录（`distracted-visvesvaraya-258d4a` / `elastic-jepsen-7cfa05` / `suspicious-stonebraker-38e2e1`）—— 因其他 Claude 会话锁定无法删除，可忽略或等会话关闭后用户自行删

---

## 11. GitHub 仓库速查

- **URL**：https://github.com/MOKIMOKI0312/bachlor-thesis
- **可见性**：Public（用户表示不在意）
- **分支**：`master` + 34 个 `claude/*` 分支（claude-code 历史会话 worktree，作为完整备份保留，不必清理）
- **凭据**：本机 Git Credential Manager 已缓存，`git push origin master` 可直接成功
- **clone 命令**（如需在其他机器拉）：
  ```bash
  git clone https://github.com/MOKIMOKI0312/bachlor-thesis.git
  ```
  注：仓库 `.git` 本地约 17 GB（早期错误 commit 的 `vendor/EnergyPlus-23.1.0-Windows-x86_64.zip` 171MB + 训练 jsonl + wandb logs 占大头）。**clone 会下载这些历史 blobs**，预计耗时较长。如要彻底瘦身需要 `git filter-repo` rewrite history + force-push，**不建议在毕设关键期做**（rewrite 会改所有 commit hash）。

---

## 12. 下一个会话的开工建议

1. **先 stash 处理**：审查 3 个 stash，apply 或 drop 后清空 `git stash list`
2. **读 `tools/m1/verify_components_out/report.md`**：确认 41 PASS Phase A 的具体 evidence，理解当前 plant 拓扑
3. **跑 smoke**：`python tools/smoke_m2_env.py`，确认环境无回归
4. **决定是否清理磁盘**：如果 `runs/train/` 有 50GB+ 旧 ckpt，可在 D2 启动前清，但保留 `seed8` 等 M1 关键 ckpt
5. **启动 M2-D2**：按 §6.1 模板，**lr=5e-5**，4 seed，每 10 ep checkpoint，并发 ≤ 4

---

## 13. 元信息

- **生成时间**：2026-04-25（UTC+2）
- **当前 commit**：`d885ae0f`
- **上一份 handoff**：`项目目标/handoff_2026-04-19.md`（Singapore→CAISO 切换上下文）
- **里程碑状态**：M0 / E0 / E0.3 / M1 / M2-A 到 M2-D1 全 DONE，M2 代码审查 + 9 bug 修复 DONE，M2-merge + Phase A/B 验证 DONE，**M2-D2 / D3 / D4 / D5 训练 + 评估 READY 未启动**
- **作者**：claude-opus-4-7（毕设主开发助理）
- **主 IDE 路径**：`D:/Anaconda/python.exe`，`D:/MATLAB/2025a/`，`D:/texlive/2025/`
