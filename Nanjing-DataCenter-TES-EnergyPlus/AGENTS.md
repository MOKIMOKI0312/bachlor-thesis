# Nanjing DataCenter TES EnergyPlus Package

本目录是当前主线代码包。所有 EnergyPlus 模型、天气、电价输入、PV 输入、runner 和模型说明都以这里为准。

## 工作原则

- 默认先保护可运行性，再做结构或参数修改。
- 修改 `model/` 后必须重新运行 EnergyPlus，或明确说明为什么暂时不能运行验证。
- `inputs/` 中的电价和 PV 是外部输入，不是 EnergyPlus 原生物理输入。
- `out/` 是本地运行输出目录，默认不提交 Git，除非是 `out/AGENTS.md` 或用户明确要求保留的精选结果。
- 不恢复旧 RL、Sinergym、MPC v2 或 W2/W3 实验结构，除非用户明确要求。
- 新增文件时优先保持当前最小项目结构，不把历史实验材料重新混入主线。

## Agent 分工要求

- 主 agent 默认负责目标澄清、任务拆解、风险控制、验收、提交范围确认和最终汇报。
- 涉及代码、EnergyPlus 模型、runner、输入校验脚本、图表脚本或说明文档的实际修改时，默认创建显式 GPT-5.5 subagent 处理。
- 代码/模型/文档修改 subagent 应只在本目录范围内工作，并在完成后返回：
  - 修改文件清单
  - 修改原因
  - 验证命令
  - 验证结果
  - 已知风险或未验证项
- 主 agent 不直接编辑代码、epJSON、CSV 或运行结果文件，除非任务非常小、subagent 不可用，或用户明确要求主 agent 直接处理。
- 主 agent 可以进行必要的只读核对，例如读取 `git diff`、错误日志、测试输出、EnergyPlus `eplusout.err`、README 和 manifest，以完成验收。
- 每次代码或模型修改后，优先再使用显式 GPT-5.5 审查 subagent 做一次 diff review；审查重点是可运行性、物理口径、路径一致性、输出文件污染和文档是否同步。

## 当前主线内容

- `model/`：唯一主线 EnergyPlus epJSON 模型。
- `weather/`：EnergyPlus 天气文件。
- `inputs/`：外部电价、PV 和后续多地点场景输入。
- `docs/`：模型说明、manifest、验证口径和后续接入说明。
- `run_energyplus_nanjing.ps1`：轻量 EnergyPlus runner。
- `out/`：本地 EnergyPlus 运行输出，默认忽略。

## 默认验证

运行入口：

```powershell
& .\run_energyplus_nanjing.ps1 -EnergyPlusExe "<path-to-energyplus.exe>"
```

成功标准：

- EnergyPlus completed successfully。
- 0 Severe Errors。
- `Timestep.number_of_timesteps_per_hour = 4`，即 15 分钟。
- 冷却塔核心 warning 不应重新出现：
  - `Cooling tower air flow rate ratio calculation failed`
  - `Tower approach temperature is outside model boundaries`
  - `Tower range temperature is outside model boundaries`

## 输出和提交规则

- 本地仿真结果保留在 `out/`，默认不入库。
- 文档性模型说明写入 `docs/`。
- 修改模型参数时，同步更新相关说明文档。
- 提交前检查 `git status`，避免把 EnergyPlus 大型输出文件加入 Git。
- 提交前必须检查是否需要同步更新论文 LaTeX；如果无需更新，应说明原因。
