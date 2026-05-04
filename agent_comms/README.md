# agent_comms — Claude ↔ Codex 异步通信协议

**目的**：让 Claude（Anthropic Claude Code）与 Codex（OpenAI/GPT 助手）通过 git 仓库 + 文件系统异步沟通，避免用户在两个会话间来回粘贴长任务包。

**当前协议版本**：v1

---

## 文件结构

| 文件 | 谁写 | 谁读 | 说明 |
|---|---|---|---|
| `README.md` | Claude | 双方 | 协议规范（本文件） |
| `status.json` | 写者更新 | 双方 | 状态机：当前 turn / inbox 状态 / next_action |
| `codex_inbox.md` | Claude | Codex | Claude 给 Codex 的任务 |
| `claude_inbox.md` | Codex | Claude | Codex 给 Claude 的回复 |
| `poll_codex.ps1` | Claude | （执行）| Codex 端 Windows Task Scheduler 跑的 polling 脚本 |
| `_poll.log` | poll_codex.ps1 | 用户 | polling 日志（gitignore） |
| `_new_task_for_codex.flag` | poll_codex.ps1 | 用户 | 有新任务时的 flag 文件（gitignore）|
| `_last_seen_turn.txt` | poll_codex.ps1 | poll_codex.ps1 | 幂等防重发 alert（gitignore）|

---

## status.json schema

```json
{
  "schema_version": 1,
  "current_turn": 1,
  "last_writer": "claude",
  "last_writer_timestamp_utc": "2026-05-04T03:10:00Z",
  "codex_inbox": {
    "status": "pending",
    "topic": "<one-line topic>"
  },
  "claude_inbox": {
    "status": "empty",
    "topic": null
  },
  "next_action": "codex_to_process"
}
```

**字段定义**：

- `current_turn`：单调递增整数，从 1 开始，每条新消息 +1
- `last_writer`：`"claude"` 或 `"codex"`
- `last_writer_timestamp_utc`：ISO 8601 UTC 时间
- `codex_inbox.status` / `claude_inbox.status`：
  - `"pending"`：有待处理消息
  - `"consumed"`：消息已被读取并处理完毕
  - `"empty"`：占位状态，无消息
- `next_action`：
  - `"codex_to_process"`：Codex 需要处理 codex_inbox.md
  - `"claude_to_review"`：Claude 需要看 claude_inbox.md
  - `"idle"`：双方都已 consumed，等下一轮

---

## 工作流（每个 turn）

### Claude 写消息（用户 Claude 会话内触发）

1. 用 Edit/Write 改 `agent_comms/codex_inbox.md`（覆盖式）
2. 用 Edit 改 `agent_comms/status.json`：
   - `current_turn += 1`
   - `last_writer = "claude"`
   - `last_writer_timestamp_utc = <now>`
   - `codex_inbox.status = "pending"`
   - `codex_inbox.topic = <new topic>`
   - `claude_inbox.status = "consumed"`（如果之前是 pending）
   - `next_action = "codex_to_process"`
3. `git add agent_comms/{codex_inbox.md,status.json}`
4. `git commit -m "comms(turn N): claude→codex <topic>"`
5. `git push origin master`

### Codex 端 polling（自动）

`poll_codex.ps1` 通过 Windows Task Scheduler 每 60 秒跑：

1. `git pull origin master --quiet`
2. 读 `status.json`
3. 若 `next_action == "codex_to_process" AND codex_inbox.status == "pending" AND turn != last_seen`：
   - 触发 alert：`[Console]::Beep` + 写 `_new_task_for_codex.flag` + 终端打印
   - 用户接到 alert → 切到 Codex 终端 → 让 Codex 读 `agent_comms/codex_inbox.md` 干活
4. 更新 `_last_seen_turn.txt` 防重发

### Codex 处理消息

1. 读 `agent_comms/codex_inbox.md`（含 frontmatter）
2. 按 inbox 任务执行
3. 写 `agent_comms/claude_inbox.md`（覆盖式，含 frontmatter + 完整回贴）
4. 改 `agent_comms/status.json`：
   - `current_turn += 1`
   - `last_writer = "codex"`
   - `last_writer_timestamp_utc = <now>`
   - `codex_inbox.status = "consumed"`
   - `claude_inbox.status = "pending"`
   - `claude_inbox.topic = <reply topic>`
   - `next_action = "claude_to_review"`
5. `git add agent_comms/{claude_inbox.md,status.json}` + 任何任务产物（按 inbox 指示，可能不让 commit 任务产物，看 inbox 怎么说）
6. `git commit -m "comms(turn N+1): codex→claude <topic>"`
7. `git push origin master`

### Claude 读消息（用户下次会话说「check inbox」）

1. `git pull origin master`
2. 读 `agent_comms/status.json`
3. 若 `claude_inbox.status == "pending"`：读 `claude_inbox.md` → 处理决策

---

## 消息文件 frontmatter 模板

### codex_inbox.md

```markdown
---
turn: 1
from: claude
to: codex
written_at_utc: 2026-05-04T03:10:00Z
expected_back_by_utc: 2026-05-05T03:10:00Z
topic: <one-line>
status: pending
---

# 任务

<具体任务>

# 停止条件

<什么情况停>

# 回贴清单

<期望 Codex 在 claude_inbox.md 里写什么>

# 完成时 status.json 应改成

<显式写出 Codex 处理完后要写的状态字段，让 Codex 不需读 README 就懂>
```

### claude_inbox.md

```markdown
---
turn: 2
from: codex
to: claude
written_at_utc: 2026-05-04T04:00:00Z
in_reply_to_turn: 1
topic: <one-line>
status: pending
---

# 完成情况

<是否完成 / 部分完成 / 中断>

# 产物

<文件路径列表>

# 关键诊断

<具体数据>

# 待 Claude 决策

<如有>
```

---

## 死锁与冲突避免

- 每个 inbox 消息 frontmatter 都有 `expected_back_by_utc`（建议 +24h）
- polling 脚本若发现 `expected_back_by_utc` 已过 + 仍 `pending` → alert 升级
- 双方在写之前必须 `git pull origin master`
- push 失败 → `git pull --rebase` 重试一次；二次失败 → 写 alert 让用户介入
- 任一方发现 status.json 与 inbox 文件**状态矛盾**（如 status 说 consumed 但 inbox 还有未处理内容）→ 立即 alert 用户并停止自动处理

---

## 一次性配置：注册 Task Scheduler

用户在 admin PowerShell 中跑一次：

```powershell
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"C:\Users\18430\Desktop\毕业设计代码\agent_comms\poll_codex.ps1`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Seconds 60) `
    -RepetitionDuration (New-TimeSpan -Days 365)
Register-ScheduledTask -TaskName "ClaudeCodexPoll" -Action $action -Trigger $trigger -Force
```

注册后可手动跑一次验证：
```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\18430\Desktop\毕业设计代码\agent_comms\poll_codex.ps1"
type agent_comms\_poll.log
```

---

## 不在 v1 协议范围

- 多轮并发（多个 Codex 任务并发处理）→ v2
- 优先级队列 → v2
- Claude 端自动 polling（让 Claude 不需要用户启动会话即可读 inbox）→ 需要 always-on Claude，本协议不解决
- Codex 自动连环 turn（无人值守自动跑多个 turn）→ 当前协议假设每个 turn 后等用户审视
