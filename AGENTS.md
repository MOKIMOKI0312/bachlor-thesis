# 项目级 AGENTS.md

## 总原则

- 请使用第一性原理思考。
- 不要假设用户已经非常清楚自己想要什么和该怎么得到。
- 从原始需求和问题出发判断目标、约束和最短路径。
- 如果动机或目标不清晰，先停下来澄清，再继续执行。
- 如果目标清晰但路径不是最短，直接指出，并给出更好的办法。
- 结论优先基于代码、数据、日志和可验证证据，不要把猜测当事实。

## 默认工作方式

- 主 agent 负责宏观调控：目标澄清、任务拆解、优先级、风险控制、结果整合和最终验收。
- 默认先读上下文，再改代码，再验证结果。
- 对研究、实验和分析任务，要区分：
  - 已证实的事实
  - 基于证据的推断
  - 仍待验证的假设
- 优先选择最短、最稳、最容易验证的路径，不为了“完整流程”而增加无必要复杂度。

## 项目结构

- 当前项目根目录 `毕业设计代码/` 是一个总工作区，不是单一代码包。
- 默认情况下，当前代码工作区是 `Nanjing-DataCenter-TES-EnergyPlus/`。
- 如果用户没有特别说明，EnergyPlus 模型、天气、价格/PV 输入、runner、模型说明和仿真验证都应先从 `Nanjing-DataCenter-TES-EnergyPlus/` 开始，而不是从参考资料目录开始。

### 根目录分层

- `Nanjing-DataCenter-TES-EnergyPlus/`：当前核心代码工作区，保留南京数据中心 TES EnergyPlus 最小模型包。
- `其它参考文献/`：参考材料，不是主代码入口。
- `复现论文/`：论文复现相关资料。
- `外部项目/`：外部仓库或第三方参考实现。
- `毕业设计项目进度/`：项目进度和管理性文档。
- `项目目标/`：目标定义和路线性文档。
- `deep-research-report (1).md`：单独的研究报告文件。

### 核心工作区结构

- `Nanjing-DataCenter-TES-EnergyPlus/model/`：唯一保留的 EnergyPlus epJSON 模型，当前为 `Nanjing_DataCenter_TES.epJSON`。
- `Nanjing-DataCenter-TES-EnergyPlus/weather/`：南京 EPW 天气文件。
- `Nanjing-DataCenter-TES-EnergyPlus/inputs/`：外部输入，当前保留江苏/南京 TOU 电价 CSV 和南京 PV 预测 CSV。
- `Nanjing-DataCenter-TES-EnergyPlus/docs/`：模型说明、manifest、验证口径和后续接入说明。
- `Nanjing-DataCenter-TES-EnergyPlus/run_energyplus_nanjing.ps1`：轻量 EnergyPlus runner，负责校验输入并运行模型。
- `Nanjing-DataCenter-TES-EnergyPlus/out/`：本地 EnergyPlus 运行输出目录，默认不入库。

### 默认路径优先级

- EnergyPlus 模型问题：优先查看 `Nanjing-DataCenter-TES-EnergyPlus/model/` 和 `Nanjing-DataCenter-TES-EnergyPlus/docs/`。
- 天气、电价、PV 数据问题：优先查看 `Nanjing-DataCenter-TES-EnergyPlus/weather/` 和 `Nanjing-DataCenter-TES-EnergyPlus/inputs/`。
- 仿真运行问题：优先查看 `Nanjing-DataCenter-TES-EnergyPlus/run_energyplus_nanjing.ps1` 和本地 `Nanjing-DataCenter-TES-EnergyPlus/out/`。
- 文献、报告、历史路线和背景说明问题：再转向根目录下的参考资料目录和 Markdown 文档。

## 当前计划与结果落盘

- 当前主线是南京 TES + PV + 电价 EnergyPlus 最小模型包，不再默认延续旧 RL/MPC/W2 实验目录结构。
- 模型说明、manifest 和验证口径默认写到 `Nanjing-DataCenter-TES-EnergyPlus/docs/`。
- EnergyPlus 本地运行结果默认写到 `Nanjing-DataCenter-TES-EnergyPlus/out/`，该目录默认不入库。
- 新的项目级路线说明、交接文档、决策记录默认写到 `项目目标/`。
- 只有在用户明确要求时，才更新 `毕业设计项目进度/代码开发进度管理.md` 这类总进度文件。

## 通用 Subagent 角色

以下角色是本项目的默认通用分工模板。它们是角色，不是持久实例；需要时在当前窗口内创建。均显式指定为GPT-5.5

### 1. 读代码与回答 Agent

- 负责读取本地代码、配置、日志和文档。
- 负责回答代码结构、行为、调用链、实现细节和现状判断问题。
- 默认只读，不编辑文件。

### 2. 写代码与回答 Agent

- 负责实现功能、修复问题、修改代码和做必要的本地验证。
- 负责回答与实现方案和代码变更有关的问题。
- 默认直接完成实现，不只停留在建议层。
- 不要回滚他人修改；如果存在并行改动，先适配再继续。

### 3. 代码变动审查 Agent

- 负责审查 diff、补丁和未提交变更。
- 输出重点是 bug、回归风险、口径不一致、测试缺口和实验/数据结论风险。
- 默认不改代码，只给审查结论。
- 审查结论按严重性排序，并尽量给出文件和行号证据。

### 4. 网络下载到本地 Agent

- 负责从网络定位并下载文件到本地。
- 负责核对来源、文件名、保存路径和基本完整性。
- 默认不做无关分析，只负责把目标文件安全落盘。

### 5. 本地 PDF 解析 Agent

- 负责读取和解析本地 PDF。
- 可以提取正文、章节结构、表格、元数据和关键信息。
- 可以输出问答、摘要、结构化笔记和表格整理结果。
- 默认不修改原 PDF。

## 触发规则

- 如果用户明确提到 `agent`、`subagent`、委派、并行处理，优先按上述角色分工。
- 如果用户没有明确说明目标目录，但任务显然是 EnergyPlus 模型、输入数据、runner 或仿真验证问题，默认目标目录是 `Nanjing-DataCenter-TES-EnergyPlus/`。
- 如果用户说“看当前计划”“按现在计划做”“更新结果”，默认按本文件中的“当前计划与结果落盘”规则执行。
- 新窗口不会继承旧窗口里已经创建好的 agent 实例；如果需要，应按本文件中的角色重新创建。

## 输出要求

- 先给结论，再给依据，再给下一步。
- 不确定时明确说明不确定点，并给出最小验证方法。
- 避免空泛建议，例如“继续试试”或“训练更久”；优先给最小可执行方案。
