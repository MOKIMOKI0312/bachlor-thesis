# M2-E3b-v2 RL-Cost @ CAISO — 失败实验归档

**训练区间**：2026-04-21 17:55 启动 → 2026-04-22 10:17 手动终止
**总时长**：约 16.4 小时
**CPU 投入**：16.4 h × 6 seed ≈ **98 CPU-小时**
**完成度**：ep 132-145（目标 300 ep）
**最终决策**：弃用（切换 Jiangsu TOU，见 `项目目标/archive/决策-切回-Nanjing-Jiangsu-TOU-2026-04-22.md`）

## 配置

| 项 | 值 |
|----|----|
| 算法 | DSAC-T，net_arch=[256,256] |
| 学习率 | 5e-5（M1 验证值）|
| batch_size | 512 |
| alpha | 5e-4 |
| lambda_temperature | 1.0 |
| reward | RL_Cost_Reward **with A+C 修复**（clip ±3.0 + price tanh）|
| 电价源 | CAISO NP15 2023（$0 to $1091/MWh，kurtosis ≈ 120）|
| 站点 | California (SFO TMYx + Palo Alto PV 6 MWp) |
| IT trace | Earth hourly |
| seeds | 6 |
| 目标 | 300 ep |

## 终止时状态（2026-04-22 10:17）

| seed | 最终 ep | ent_coef | critic | actor | **omega** | 分类 |
|------|---------|----------|--------|-------|-----------|------|
| 1 | 132 | 0.063 | 2.76 | 240 | **1,409** | ✅ 健康 |
| 2 | 135 | 0.352 | 3.68 | 3,944 | **4,865,747** | ⚠ 振荡发散 |
| 3 | 134 | 0.124 | 3.35 | 395 | **4,084** | ✅ 健康 |
| 4 | 132 | **1.146** | 4.46 | 10,189 | **37,173,056** | ☠ UNSTABLE |
| 5 | 145 | 0.886 | 3.81 | 10,829 | **38,088,723** | ☠ UNSTABLE |
| 6 | 143 | 0.327 | 3.48 | 3,308 | **4,024,381** | ⚠ EARLY_WARN |

**分类汇总**：2 健康 + 2 振荡发散 + 2 UNSTABLE = **2/6 稳定收敛（33%）**

## 失败模式

### Omega 爆炸轨迹（关键指标）

| 窗口 | seed5 omega 轨迹 |
|------|----------------|
| ep6 | 51,206（WATCH 阈值附近）|
| ep22 | 15,339（回落）|
| ep29 | 3,070,200（单轮 200x 跳跃）|
| ep42 | 1,736,029 |
| ep63 | 8,725,813 |
| ep89 | 10,042,865 |
| ep131 | 48,977,781（峰值，超过首轮 E3b seed5 的 51.7M 峰值仅 6%）|
| ep145（终止）| 38,088,723 |

**seed4 类似**：从 ep47 ω=91k 稳定态一路爬到 ep132 的 37M。

### Ent-Omega 脱耦（A+C 的部分成效）

与首轮未修复对比：
- **首轮 (无 A+C)**：seed5 omega=51.7M 时 ent=2.3；随后 ent 继续到 24.1（policy 完全 collapse）
- **本轮 (A+C)**：seed5 omega=48.98M 时 ent=1.21；最终 1.21（压在 >1 <2 区间，policy 退化但未死）

A+C 的 reward clip 成功**切断了 omega → ent 的直接级联**，但没治住 omega 本身。

### Self-healing 能力（新现象）

**seed2 戏剧性自愈**：
- ep76: ω=12.4M, ent=0.328（濒危）
- ep84: ω=18k, ent=0.091（完全自愈）
- ep108: ω=1.08M（二次反弹，limit cycle 确认）

这种自愈在首轮从未出现。说明 A+C 让"1M-10M 级 ω"变可逆，但"10M-50M 级 ω"仍不可逆。

## 根因诊断

**算法-数据分布不匹配**：
- DSAC-T 的 Gaussian critic 假设 Q 分布 kurtosis ≈ 3
- CAISO NP15 2023 reward 分布 kurtosis ≈ 120（40 倍偏离）
- Reward 中的 $1091/MWh scarcity event（0.07% 频率）每次进入 replay batch 都对 critic σ² 产生 10⁴-倍的梯度贡献
- Gaussian NLL 梯度选择"增大 σ" 而非"调整 μ" 来最小化 loss → σ 发散

**修复效果**：
| 实验 | 配置 | 成功率 | 失败模式 |
|------|------|--------|--------|
| E3 (lr=1e-4) | 无修复 | 1/4 (25%) | Policy collapse ent=24 |
| E3b-v1 (lr=5e-5, resume) | 无修复 | 2/6 (33%) | Policy collapse |
| E3b-v2 (A+C) | reward clip + price tanh | 2/6 (33%) | Critic 散不 policy 退 |
| **E3b-v3 (Jiangsu TOU)** | 切换数据源 | 预期 ≥5/6 | 待验证 |

A+C 把 ent 从不可逆变成"退化但可用"，但 omega 本身仍发散。

## 学术价值

尽管实验目标未达成，本组 6 seed 有以下**可引用**价值：
1. **seed1/3 健康 ckpt**：在 CAISO 极端 reward 下仍能稳定收敛，证明 DSAC-T + A+C 在重尾数据上有可能成功
2. **seed4/5 失败轨迹**：omega 从 1k → 48M 的完整 bifurcation 曲线，可作为"分布式 critic 在重尾 reward 下失稳机理"的案例
3. **seed2 自愈曲线**：ω 12M → 18k → 1M 的 limit cycle，展示 A+C 扩展的稳定域边界

## 保留资产

- Run 目录：`runs/run/run-{062..067}/`（~60 GB，保留备查）
- Job 目录：本目录 `seed{1..6}/`（status.json、stdout、stderr、manifest）
- 下一步在毕设论文"敏感性分析"章节引用

## 下一步 — M2-E3b-v3

切换数据源：
- 气象：SFO → **Nanjing** (CHN_JS TMYx)
- 电价：CAISO NP15 → **Jiangsu 2025 TOU 合成**（4 段 + 3 季节，kurtosis ≈ 2）
- PV：Palo Alto → **Nanjing** (32.06°N)

预期：kurtosis 压缩 60 倍，critic σ 不再爆炸，6 seed 预期 ≥5 个稳定收敛。

---

*归档于 2026-04-22 10:17*
*Branch：`claude/great-hugle-fb3530`*
*前置 commit：`a27cb24` [M2-E3b-fix] Reward ±3 clip + price tanh*
