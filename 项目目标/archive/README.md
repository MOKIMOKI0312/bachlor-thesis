# 项目目标 / archive — 历史 handoff 与决策归档

**归档时间**：2026-05-03

本目录存放已被主路线（`项目目标/技术路线.md`、`项目目标/3周收尾路线-MILP-MPC-2026-05-03.md`）覆盖、但仍有"为什么"价值的历史 handoff 与决策记录。按 AGENTS.md "历史决策与交接上下文"语义保留，**不是当前执行清单**。

| 文件 | 阶段 | 角色 |
|---|---|---|
| `handoff_2026-04-17.md` | M1-R2 凌晨 2:15 | M1 TES 实现重做（4300 m³ → 1400 m³ + 增量阀门 + EMS workaround）的会话交接 |
| `handoff_2026-04-19.md` | M2 联合环境完成 | 41 obs / 6 action 联合环境 + 9 次代码审查 + R1 reward patch 失效 bug 修复后的会话交接 |
| `handoff_GPTCodex_2026-04-25.md` | M2-E3b → M2-F1 过渡 | 给 OpenAI GPT Codex 的项目交接（自包含、跨 agent） |
| `决策-站点切换-CAISO-2026-04-19.md` | M2 站点决策 v2 | Singapore USEP 不可访问 → 切 CAISO California（**已被下条决策推翻**） |
| `决策-切回-Nanjing-Jiangsu-TOU-2026-04-22.md` | M2 站点决策 v3（终版） | CAISO 重尾分布触发 DSAC-T omega 爆炸 → 切回 Nanjing + 江苏 2025 TOU 合成 |

## 阅读顺序建议

如果你想了解项目当前主线路径，**不要从这里开始**——读：

1. `项目目标/技术路线.md`（主路线）
2. `项目目标/3周收尾路线-MILP-MPC-2026-05-03.md`（当前 3 周执行计划）
3. `毕业设计项目进度/代码开发进度管理.md` §3 / §4 / §11 / §13 / §14（进度面板）

如果你想理解"为什么是当前这个方案"，按时间轴读本目录：

1. `handoff_2026-04-17.md`（M1 TES 实现重做的设计权衡）
2. `决策-站点切换-CAISO-2026-04-19.md` → `handoff_2026-04-19.md`（M2 联合环境 + 站点选择 v2）
3. `决策-切回-Nanjing-Jiangsu-TOU-2026-04-22.md`（站点选择终版，CAISO 失败原因）
4. `handoff_GPTCodex_2026-04-25.md`（跨 agent 交接快照）

## 内部引用注记

本目录内部的文件互相引用时，路径仍写作 `项目目标/handoff_*.md` / `项目目标/决策-*.md`（归档前的原路径）。这是有意保留的历史快照原貌——表示该 handoff 在写作时的认知。要点击跳转时手动加上 `archive/` 前缀即可。

## 相关上层引用更新

外部活跃文档（`AGENTS.md`、`技术路线.md`、`3周收尾路线-*.md`、`代码开发进度管理.md`、`Data/{pv,prices}/README.md`、`analysis/.../FAILURE_REPORT.md`、`analysis/E1_R2_results_summary.md`、`tools/download_caiso_lmp.py`）已在 2026-05-03 同步把引用路径从 `项目目标/<file>` 更新到 `项目目标/archive/<file>`。
