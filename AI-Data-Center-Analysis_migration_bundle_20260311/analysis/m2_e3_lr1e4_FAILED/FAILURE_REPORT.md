# M2-E3 RL-Cost (lr=1e-4) 训练失败记录

**训练开始**：2026-04-19 22:15（UTC+2）
**手动终止**：2026-04-20 10:14
**总时长**：**12.0 小时**
**CPU 投入**：12h × 4 seed = **48 CPU-小时**
**完成度**：seed1/2/3 @ ep 128-142，seed4 @ ep 147（目标 300）

## 配置（失败版）

| 项 | 值 |
|----|----|
| 算法 | DSAC-T |
| 网络 | **`[256, 256]`**（M1 [512] 的升级） |
| 学习率 | **`1e-4`**（M1 5e-5 的 2× 升级） |
| batch_size | 512 |
| 其他超参 | `gamma=0.99, learning_starts=8760`（与 M1 一致） |
| reward | `RL_Cost_Reward` |
| 站点 | CAISO California + SiliconValley |
| seeds | 4 |
| 目标 | 300 ep |

## 失败总览

| seed | 最终 ep | 最终 ent_coef | 峰值 ent | actor 范围 | 诊断 |
|------|---------|--------------|----------|-----------|------|
| 1 | 139 | **1.26** | 1.98 | 22.8 ~ 12100 | 全程震荡，最终爆炸 |
| 2 | 133 | **24.4** 💥 | **30.3** | -41300 ~ 269 | 严重 policy collapse（M1 最差 seed7 才 1.6） |
| 3 | 142 | **11.7** | 12.0 | -7110 ~ 340 | ep 100 前稳定，ep 107 后突然爆炸 |
| 4 | 147 | **0.227** | 0.632 | 9.63 ~ 4730 | ✓ **唯一存活**，ent 稳定在 0.2-0.3 |

**成功率**：1/4 = **25%**（对比 M1 的 6/8 = 75%）

## 失败模式分析

### 三种病态

1. **seed2：单调爆破**（M1 seed7 风格但更极端）
   - ent 从 0.05 一路飙升到 30.3，无自愈
   - actor_loss 跌到 -41300（M1 最惨 seed7 才 -1621）
   - critic 持续学但 policy 已彻底放弃 Q 最大化

2. **seed3：突然爆炸**（M1 未见过）
   - ep 0-100：ent 稳定在 0.05-0.23（看起来最健康）
   - ep 107：突然从 0.20 跳到 9.58（单轮 48×）
   - ep 142：稳定在 11.7 附近，无回落
   - **说明**：lr=1e-4 的 DSAC-T 即使训练稳定一段时间也可能突然失控，不是只在早期有风险

3. **seed1：持续震荡**（M1 seed6 风格）
   - ent 反复在 0.2-1.0 之间震荡
   - 看起来在"自愈-反弹-再自愈"循环
   - Q 函数和 policy 都受损，有效学习时间不足

### 根本原因

**lr=1e-4 对 DSAC-T + CAISO scarcity reward 过于激进**：
- CAISO 2023 NP15 有 $1091 scarcity event + 144 小时负价
- DSAC-T 的 distributional critic 对极端 reward 敏感
- lr=1e-4 让 critic 对单个极端样本过度响应 → Q 估计出现高方差 → entropy 自动调节器推 alpha 上升 → entropy 主导 → policy collapse

M1 用 lr=5e-5 时即使在 Nanjing 气候下只有 2/8 失败。M2 上 lr=1e-4 + CAISO 价格极端事件 → 3/4 失败。

**网络架构 [256, 256] 本身无罪**：M2 网络升级是为了 41 维 obs + 9 类信号的表达力，从参数量角度 ~100k 比 M1 的 ~50k 大一倍，但与 DSAC-T 原论文一致。

## 关键教训（给 M2 第二轮）

1. **lr 必须保守**：DSAC-T + extreme-tail reward 市场（CAISO、ERCOT 类）建议 lr ≤ 5e-5
2. **震荡不等于自愈**：seed1 反复 0.2↔1.0 震荡不是"U 型自愈"，是**不收敛**
3. **稳定期不保险**：seed3 稳定 100 ep 后突然爆炸，说明 lr 决定的是**长期稳定性**不仅仅是启动期
4. **降并发策略有效**：4 seed 并发期间系统无 Event 41，未重启，说明并发本身 OK

## 建议的下轮配置（M2-E3b）

| 参数 | M2-E3（失败）| M2-E3b（推荐） |
|------|-------------|---------------|
| net_arch | `[256, 256]` | **保留 `[256, 256]`** |
| learning_rate | `1e-4` ❌ | **`5e-5`** ✓（M1 验证值）|
| 并发 seed 数 | 4 | 4（不变）|
| episodes | 300 | 300（不变）|
| checkpoint_episodes | 10 | 10（不变）|

## 归档文件

```
analysis/m2_e3_lr1e4_FAILED/
├── FAILURE_REPORT.md          ← 本文档
├── summary_stats.json         ← 4 seed 聚合指标
├── seed{1,2,3,4}_status_at_kill.json
├── seed{1,2,3,4}_manifest.json
├── seed{1,2,3,4}_stdout_tail.log  ← 最后 1000 行
└── seed{1,2,3,4}_metrics.csv   ← ent/critic/actor 完整时序
```

训练 run 目录（episode 输出）保留在 `runs/train/run-*`（大量，60GB+）。可能想在 M2-E3b 开训前清理。

训练 job 目录已改名：
```
training_jobs/m2-e3-seed{1,2,3,4}_FAILED_lr1e4/
```

## seed4 的特殊地位

seed4 是唯一存活者，**虽然训练未完成（ep 147/300）**，但：
- ent 稳定 0.18-0.30
- actor_loss 在正值合理区间
- 可以作为 M2-E3b 训练健康度基线（如果 E3b 的 seed4 也稳定，说明 lr 修对了）

**要不要保留 seed4 checkpoint 尝试 resume？**
- 优点：不浪费 12h 训练
- 缺点：混合 lr（前 12h 在 lr=1e-4 下学，resume 后 lr=5e-5）可能引入论文解释麻烦
- **建议**：**不 resume**，from scratch 更干净

## 时间成本

- 已损失：12h × 4 seed = 48 CPU-h
- 下次预计：lr=5e-5 下训练速度可能**更快**（policy 不在极端 entropy 区，E+ 仿真更规则），300 ep × 4 seed ≈ 24-28 小时

---

*报告生成时间：2026-04-20 10:15*
*Branch: `claude/great-hugle-fb3530`*
*HEAD 在杀进程时：`e8ceb07` [M2-D2] 网络升级 [512]→[256,256] + lr 5e-5→1e-4*
