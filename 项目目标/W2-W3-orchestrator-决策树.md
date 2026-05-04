# W2-W3 Orchestrator 决策树（Claude 自动唤醒指引）

**用途**：Claude 被 `mcp__scheduled-tasks` 每 20 分钟唤醒一次，新 session 没有上下文。本文件是 Claude 唤醒后的 self-contained 决策手册。

**关联**：
- 协议规范：`agent_comms/README.md`
- W2 plan：`项目目标/W2-计划-TES节能-PV自消纳-2026-05-04.md`
- W3 plan：`项目目标/3周收尾路线-MILP-MPC-2026-05-03.md` Week 3 段
- 主路线：`项目目标/技术路线.md`

---

## 唤醒后立即执行（顺序）

1. cd 到 `C:\Users\18430\Desktop\毕业设计代码`
2. `git pull origin master --quiet`
3. Read `agent_comms/status.json`
4. 检查情况：

### 情况 A: `claude_inbox.status != "pending"` 或 `next_action != "claude_to_review"`

Codex 还在干活（codex_to_process）或一切 idle。**不操作**，append 一行到 `agent_comms/_wake_log.txt`：

```
[2026-05-04T03:30:00Z wake idle] state=<status.next_action> codex=<codex_inbox.status> claude=<claude_inbox.status>
```

退出。

### 情况 B: `claude_inbox.status == "pending"` 且 `next_action == "claude_to_review"`

按下面决策树处理。

---

## 决策树

读 `agent_comms/claude_inbox.md` 完整内容，按 `in_reply_to_turn` 字段判断当前阶段：

### Turn 1 → Turn 2：W2 PHASE 3 诊断 → W2 主线决策

claude_inbox 应含：
- `m2f1_w2_scenario_compare_20260503_232820.md` 三表
- `m2f1_w2_pv_diagnostic_20260503_232820.json`
- `m2f1_w2_scenario_validation_20260503_232820.json`

按以下顺序判断：

**判断 1：PV 数据完整性**

读 pv_diagnostic.json，三 cell 的 `pv_col_used` 和 `pv_kw_max`：

- 若 `baseline_neutral.pv_col_used == "RECONSTRUCTED_FROM_CSV"` 或 `baseline_neutral.pv_kw_max < 100` → **PV wrapper 没挂载**：
  - 写 turn 2 = 让 Codex 检查 `tools/evaluate_m2_rule_baseline.py` line 109 是否真的挂了 `PVSignalWrapper(env, ...)`，并 grep monitor.csv 是否真的有 `current_pv_kw` 列。回贴 baseline cell monitor.csv 完整列名（前 50 列）+ wrapper 链构建顺序。
  - 不进 W2-B 重跑。

**判断 2：SCR 100% 物理性**

如果 PV 数据正常（pv_kw_max ~4000-6000）：

- 若三 cell `pv_exceeds_load_pct < 1%` → PV 峰值始终 < 负载。SCR 100% 是真实物理结果。论文 §4.2 叙事需要重写。
- 若 `pv_exceeds_load_pct > 5%` 但 SCR 还是 100% → 计算 bug。让 Codex 排查 `derive_pv_metrics`。

**判断 3：Cost 反向根因**

数据已知：cost_baseline 6.99M < cost_milp 7.38M，PUE 1.32 < 1.42，comfort 0.29% < 7.10%。

根因：MPC 充冷把建筑搞过热（comfort 7.1%）+ chiller 多工作（PUE +6.9%）+ 套利收益不足。

**写 turn 2 内容**：

合并判断 1+2+3，分两路：

#### 路 A：PV 数据有问题（判断 1 失败）
turn 2 = Codex 排查 PV wrapper 链 + 不重跑 batch。回贴清单：
- evaluate_m2_rule_baseline.py 实际 wrapper 链顺序
- baseline cell monitor.csv 全部列名
- 是否需要重新 build 一次 baseline cell（修 wrapper）

#### 路 B：PV 数据正常 + 物理性失败（判断 2/3 真实）
turn 2 = Codex 切 official_ood 重跑 3 cells × 35040 step（ITE_Set=1.0 高负载，TES 套利空间应更大）：

```powershell
& D:/Anaconda/python.exe tools/m2_tes_mpc_oracle.py `
    --tag w2b_mpc_milp_year_$TS_NEW --eval-design official_ood `
    --out-dir runs/m2_tes_mpc_oracle --solver milp `
    --forecast-noise-mode perfect

& D:/Anaconda/python.exe tools/m2_tes_mpc_oracle.py `
    --tag w2b_mpc_heuristic_year_$TS_NEW --eval-design official_ood `
    --out-dir runs/m2_tes_mpc_oracle --solver heuristic `
    --forecast-noise-mode perfect

& D:/Anaconda/python.exe tools/evaluate_m2_rule_baseline.py `
    --tag w2b_baseline_neutral_year_$TS_NEW --eval-design official_ood `
    --policy neutral
```

然后跑 build_w2_scenario_summary.py（新 TS，同样 --skip-validation 加保险）+ 回贴新数据。预估 wall-clock 同 ~75-100 min。

---

### Turn 2 → Turn 3：W2 official_ood 数据回来后

如果 turn 2 是路 A（排查）：基于 Codex 的排查结果决定下一步（修 wrapper / 重跑 baseline / 接受 SCR 物理结果）。

如果 turn 2 是路 B（official_ood 重跑）：

**情况 i：cost 单调性恢复（baseline ≥ heuristic ≥ milp）**

W2 数据齐了。turn 3 = 让 Codex 把 W2 数据 commit + push（W2 csv/md + W2 batch ps1 + summary py 一并入库），并起步 W3 第一项任务（W3-1：论文图表生成）。

**情况 ii：cost 仍反向**

接受负面结果，转 W2-D（双重叙事）。turn 3 = 让 Codex commit W2 数据（所有 cells 的 csv/md，标注 trainlike + official_ood 两套数据），写一份 `analysis/m2f1_w2_negative_finding_summary.md` 总结"在当前 reward + Jiangsu TOU + 数据中心物理参数下 MPC 不展示 cost saving"。然后跳过 W2-A LP 对照，直接进 W3。

---

### Turn N → Turn N+1：W3 推进（W2 收尾后）

W3 任务（按依赖顺序，每 turn 干一件）：

| W3 子任务 | 内容 | 工具 / 产物 |
|---|---|---|
| W3-1 | 论文图表生成 | `tools/m2_mpc_plots.py`（matplotlib），4 张图：(a) 全年 SOC trajectory 对照、(b) cost / PUE / comfort head-to-head 柱状图、(c) PV 自消纳分时段统计、(d) W1-3 robustness curve |
| W3-2 | W2 + W1 数据汇总表 | `analysis/m2f1_thesis_main_table.{csv,md}`，含全年 cost/PUE/comfort/SCR + W1-3 σ-curve 关键数字 |
| W3-3 | 演示脚本 | `tools/m2_mpc_demo.ps1`：5 min 内跑出 SOC trajectory + valve sign-rate（用 96-step 短跑）|
| W3-4 | handoff README | `README_handoff.md`：环境配置 + 关键工具入口 + 数据目录 + future work hooks |
| W3-5 | 论文图表 verify | 让 Codex 跑一次 W3-1 / W3-3 verify 图表生成无 error |
| W3-6 | 论文写作素材打包 | `analysis/m2f1_thesis_materials_<ts>.zip` 含全部 csv/md/png |

**W3 不让 Codex 写中文论文文字**（用户自己写）。Codex 只做：数据图表 / 脚本 / handoff README / 素材打包。

每个 W3 子任务写一个 codex_inbox turn，约束：
- 任务范围明确（一次只做一件）
- wall-clock < 30 min
- 失败立停
- 完成后改 status.json next_action=claude_to_review

---

### W3 全部完成 → 关闭协议

判定标准：`analysis/` 下出现以下文件齐全：
- `m2f1_w2_scenario_compare_*.{csv,md}`
- `m2f1_w2_figures_*/` 4 张图
- `m2f1_thesis_main_table.{csv,md}`
- `analysis/m2f1_thesis_materials_*.zip`
- `tools/m2_mpc_demo.ps1`
- `README_handoff.md`

满足后写 turn N = 让 Codex 关闭协议：
1. 改 `agent_comms/status.json`：
   ```json
   {
     "next_action": "idle",
     "claude_inbox.status": "consumed",
     "codex_inbox.status": "consumed"
   }
   ```
2. commit message 含 `W2+W3 ALL DONE`
3. 写 `agent_comms/claude_inbox.md` 一份"全部完成"摘要。

Claude 唤醒下次检测到 next_action=idle 不再操作。**用户手动 disable scheduled task**（命令在最下面）。

---

## 异常处理

### 连续 3 次唤醒都 idle（Codex 卡住）

读 `agent_comms/_wake_log.txt` 末 5 行。如果连续 3 个 `[wake idle]` + 时间间隔 ≥ 60 min（说明 Codex 那边没在干活）→ 写一份 turn N，topic="🔔 user check needed"，frontmatter `expected_back_by_utc=now+1h`，内容是"Codex 没响应，请用户检查 _poll.log 或手动触发"。

### Codex 报告 plan-vs-reality 冲突

claude_inbox.md 含"plan vs reality conflict"或停止条件触发：

不要硬推。写新 turn = 让 Codex 提供更多诊断（具体路径 / 文件内容 / line 号）。

### turn 数 > 20 仍未完成 W2+W3

可能进入 ping-pong 循环。写 turn = 让 Codex 总结当前阻塞 + 把整个 stuck 状态写到 `analysis/_orchestrator_stuck_<ts>.md` 让用户介入。

---

## 安全规则（永不违反）

- 不修 epJSON / wrapper / reward / m2_tes_mpc_oracle.py / evaluate_m2_rule_baseline.py 核心逻辑
- 每个 codex_inbox 必须含 frontmatter + "停止条件" + "完成时 status.json 应改成什么"
- 不让 Codex 一次跑 > 100 min wall-clock 任务
- 不让 Codex 写中文论文文字（W3）
- 不让 Codex 自主多 turn 连环（每 turn 完成后必须停下等 Claude）
- 任何 git 冲突 → `git pull --rebase` 重试一次，二次失败立刻停下写诊断
- W2-A LP × 9 gaussian cells 已推迟到 W2 之后；除非用户明确要求，不主动起这个 turn

---

## 写入 codex_inbox.md 的标准模板

```markdown
---
turn: N
from: claude
to: codex
written_at_utc: <ISO now>
expected_back_by_utc: <ISO now + 24h>
topic: <一句话>
status: pending
---

# 背景

<本轮 context；上一轮回贴的关键发现；当前阶段定位>

# 任务

<具体要做的事，命令到行级>

# 停止条件

<什么情况停下，回贴诊断而不是硬推>

# 回贴清单

<期望 Codex 在 claude_inbox.md 里写什么>

# 完成时 status.json 应改成

<显式 JSON 块>

# 提交命令

<git add / git commit / git push 命令，明确不要 commit 哪些目录>
```

---

## 关闭定时唤醒（用户手动）

W3 全部完成后，用户在 admin PowerShell 跑：

```powershell
Unregister-ScheduledTask -TaskName "ClaudeCodexPoll" -Confirm:$false
# Claude 自己的 wake task ID 见 ~/.claude/scheduled-tasks/<task-id>/SKILL.md
```

或在 Claude 会话内说 "stop scheduled wake"，Claude 调用 `mcp__scheduled-tasks` 的 update 接口禁用任务。
