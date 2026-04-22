# 决策记录：站点切回 Nanjing + 江苏 2025 TOU 合成电价

**决策日期**：2026-04-22
**决策人**：用户 + 主 Claude agent
**影响范围**：M2-E3b-v3 及后续全部训练实验
**替代此前决策**：`决策-站点切换-CAISO-2026-04-19.md`（2026-04-19 切到 CAISO）

---

## 背景

M2-E3b-v2（2026-04-21 启动，6 seed from scratch，CAISO NP15 2023 + SFO TMYx + Palo Alto PV，A+C 修复：reward clip ±3 + price tanh）运行 16.4 小时后（ep 132-145）出现严重失稳：

| seed | 最终 ep | ent_coef | omega | 分类 |
|------|---------|----------|-------|------|
| 1 | 132 | 0.063 | 1,409 | ✅ 健康 |
| 2 | 135 | 0.352 | 4,865,747 | ⚠ 振荡发散 |
| 3 | 134 | 0.124 | 4,084 | ✅ 健康 |
| 4 | 132 | 1.146 | **37,173,056** | ☠ UNSTABLE |
| 5 | 145 | 0.886 | **38,088,723** | ☠ UNSTABLE |
| 6 | 143 | 0.327 | 4,024,381 | ⚠ EARLY_WARN |

**成功率 2/6 = 33%**。A+C 修复相较未修复版（首轮 E3b 2/6）几乎无改善，从根本上验证了**算法-数据分布不匹配**是核心障碍。

---

## 根因（最终诊断）

**CAISO NP15 2023 价格分布**：
- kurtosis ≈ 120（正态分布 = 3）
- 0.07% 的 hour 贡献 > 20% 的总成本
- $1091/MWh 极端事件 vs $53/MWh median

**DSAC-T critic 设计**：
- 假设 Q 值服从 Gaussian 分布
- Gaussian NLL `(R-μ)²/σ²` 对 outlier **指数敏感**
- 遇到极端 reward 时梯度选"增大 σ"路径（而非调整 μ），触发 `omega` 爆炸

**A+C 修复局限**：
- A (reward clip ±3) 切断了"reward 极值 → σ 激增"的直接路径
- C (price obs tanh) 仅改 policy 输入，不触 critic 梯度通路
- 结果：ent_coef 被压住（policy 未完全 collapse），但 omega 仍发散到 10⁶-10⁸ 级

---

## 决策

**立即切换数据源**：

| 维度 | 原（CAISO 方案） | 新（Nanjing Jiangsu TOU）|
|------|-----------------|-----------------------|
| 气象 | SFO TMYx | **CHN_JS Nanjing TMYx**（与 M1 E1-R2c 对齐，可对比）|
| 电价 | CAISO NP15 2023 批发 | **江苏 2025 合成 TOU（4 段 + 3 季节）**|
| PV | Palo Alto 37.44°N | **Nanjing 32.06°N, 27° 倾角**（PVGIS）|
| Kurtosis | 120 | **-1.3**（excess），接近均匀分布 |

**电价合成依据**：江苏省发改委 2025 年第 426 号文《关于优化工商业分时电价结构促进新能源消纳降低企业用电成本支持经济社会发展的通知》，自 2025-06-01 起执行。

### 电价值表（USD/MWh，汇率 1 USD = 7 CNY）

**基础**（过渡季 3-6、9-11 月）：
- 尖峰 (19-21): **180**
- 高峰 (8-11, 17-19, 21-22): **150**
- 平段 (11-12, 13-17, 22-24): **83**
- 谷段 (0-8, 12-13): **29**

**季节调整**（仅 peak/super-peak）：
- 夏季迎峰 (7-8 月): 尖 200 / 峰 165
- 冬季迎峰 (1, 2, 12 月): 尖 190 / 峰 158
- 过渡季: 同基础表

### 验证

合成数据统计特征（`Data/prices/Jiangsu_TOU_2025_hourly.csv`）：
```
min=29  max=200  median=83  mean=89.2  std=56.8
kurtosis(excess)=-1.344  (CAISO=117, 差 118 个单位)
distinct prices: 8 levels (29, 83, 150, 158, 165, 180, 190, 200)
```

Smoke test 验证（2026-04-22 11:14）：
- cost_term @ LMP=29 谷段 = -0.155（远小于 clip ±3）
- obs_dim=41, action_dim=6 保持
- 预期 TOU 下 reward clip **永不触发**（max cost = α × P × 200 = 1.2 < 3）

---

## 替代方案对比（已放弃）

| 方案 | 做法 | 理由 / 弃用原因 |
|------|------|---------------|
| A | CAISO + hard cap p95 = $120 | 相当于人为抹除市场极端事件，但仍保留 CAISO 噪声；论文表述模糊 |
| B | CAISO + log-transform | 学术合法但破坏 reward 真实性 ↔ 电费直观解释链 |
| C | 切 SAC（非 distributional） | 完全放弃 DSAC-T 框架，与技术路线脱节，代价过大 |
| D | 课程学习 | 工程复杂度高，毕设期限紧张 |
| **E（已选）** | **合成 TOU** | **贴合中国 DC 实际场景 + 工程简单 + 毕设定位一致 + 学术可解释** |

---

## 对毕设论文的影响

**正面**：
1. 主实验基于中国江苏站点，与用户研究方向（国内数据中心）一致
2. 电价稳定，训练成功率预期 ≥5/6（≥83%），有可靠结果
3. 电价值可追溯到公开政策文件（苏发改价格发 [2025] 426 号）

**CAISO 实验的学术价值保留**（不弃）：
- `analysis/m2_e3b_v2_CAISO_FAILED/FAILURE_REPORT.md` 归档
- `training_jobs/m2-e3b-v2-CAISO-FAILED/seed{1..6}/` 完整保留
- `runs/run/run-{062..067}/` episode 数据保留
- **论文中以"敏感性分析"章节**引用：证明 DSAC-T 在重尾 wholesale market 下的稳定性挑战是**领域 open problem**，不是个案

---

## 后续行动清单

1. ✅ 停止 6 seed CAISO 训练（2026-04-22 10:17 完成）
2. ✅ 归档 CAISO 训练数据到 `training_jobs/m2-e3b-v2-CAISO-FAILED/`
3. ✅ 生成 `Data/prices/Jiangsu_TOU_2025_hourly.csv`
4. ✅ 生成 `Data/pv/CHN_Nanjing_PV_6MWp_hourly.csv`
5. ✅ 更新 `tools/run_m2_training.py` + `tools/evaluate_m2.py` + `tools/smoke_m2_env.py` 默认路径
6. ✅ 冒烟测试 PASS（obs_dim=41, cost_term ∈ [-0.16, -0.05]）
7. ⏳ 更新 `项目目标/技术路线.md` §5 / §6
8. ⏳ 更新 `毕业设计项目进度/代码开发进度管理.md` §7 / §12
9. ⏳ Git commit
10. ⏳ 启动 6 seed E3b-v3 from scratch
11. ⏳ Cron 监控（阈值下调至 OMEGA_WATCH >10k / OMEGA_CRIT >100k）

---

## 预期验证指标

**启动后 1h（约 ep 6）**：
- 全 6 seed omega < 5,000
- 全 6 seed ent_coef < 0.15

**启动后 24h（约 ep 50，历史爆炸窗口）**：
- 全 6 seed omega < 10,000
- 无 UNSTABLE / OMEGA_CRIT 告警

**训练完成（~ep 300，预计 04-24 早晨）**：
- ≥ 5/6 seed 收敛到 ent_coef < 0.2
- Evaluation PUE 相对 E0.3 (1.307) 改善

---

*本决策文件为 M2 实验切换节点的权威记录，覆盖所有早期 Singapore USEP 和 CAISO NP15 决策。*
