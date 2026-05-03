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
- 默认情况下，真正的代码、训练、评估和实验工作区是 `AI-Data-Center-Analysis_migration_bundle_20260311/`。
- 如果用户没有特别说明，代码阅读、代码修改、实验排查、训练执行和评估审查都应先从 `AI-Data-Center-Analysis_migration_bundle_20260311/` 开始，而不是从参考资料目录开始。

### 根目录分层

- `AI-Data-Center-Analysis_migration_bundle_20260311/`：核心代码与实验工作区。
- `其它参考文献/`：参考材料，不是主代码入口。
- `复现论文/`：论文复现相关资料。
- `外部项目/`：外部仓库或第三方参考实现。
- `毕业设计项目进度/`：项目进度和管理性文档。
- `项目目标/`：目标定义和路线性文档。
- `deep-research-report (1).md`：单独的研究报告文件。

### 核心工作区结构

- `AI-Data-Center-Analysis_migration_bundle_20260311/sinergym/envs/`：环境封装与 wrapper 逻辑。这里有 `tes_wrapper.py`、`time_encoding_wrapper.py`、`price_signal_wrapper.py`、`pv_signal_wrapper.py`、`temp_trend_wrapper.py`、`energy_scale_wrapper.py` 等核心行为文件。
- `AI-Data-Center-Analysis_migration_bundle_20260311/tools/`：训练、评估、诊断、下载、启动和监控脚本主目录。M2 相关关键入口通常在这里，例如 `run_m2_training.py`、`evaluate_m2.py`、`evaluate_m2_rule_baseline.py`、`m2_reward_audit.py`、`m2_validate_tes_failure_modes.py`。
- `AI-Data-Center-Analysis_migration_bundle_20260311/Data/`：输入数据目录，包含 `buildings/`、`weather/`、`prices/`、`pv/`、`Grid Data/`、`AI Trace Data/`。
- `AI-Data-Center-Analysis_migration_bundle_20260311/analysis/`：分析结果、对比表、说明文档和审计产物。
- `AI-Data-Center-Analysis_migration_bundle_20260311/runs/`：训练、评估、probe 和验证实验的运行产物目录。
- `AI-Data-Center-Analysis_migration_bundle_20260311/training_jobs/`：后台训练任务与作业记录目录，主要用于追踪 job、workspace 和状态。
- `AI-Data-Center-Analysis_migration_bundle_20260311/logs/`：运行日志目录。
- `AI-Data-Center-Analysis_migration_bundle_20260311/results/`：评估输出和结果整理目录。
- `AI-Data-Center-Analysis_migration_bundle_20260311/vendor/`、`wandb/`、`tmp/`：依赖、实验服务和临时产物相关目录。

### 默认路径优先级

- 代码行为问题：优先查看 `sinergym/envs/` 和 `tools/`。
- 训练状态问题：优先查看 `training_jobs/`、`runs/train/`、`runs/run/`、`logs/`。
- 评估结论问题：优先查看 `tools/evaluate_*.py`、`analysis/`、`runs/eval*`、`results/`。
- 数据来源问题：优先查看 `Data/`。
- 文献、报告、背景说明问题：再转向根目录下的参考资料目录和 Markdown 文档。

## 当前计划与结果落盘

### 默认查计划顺序

- 如果任务与当前主线实验有关，先查看 `AI-Data-Center-Analysis_migration_bundle_20260311/analysis/` 下最新的任务清单、问题定义和阶段性分析文档。
- 当前 M2-F1 主线下，默认先读：
  - `AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_tes_deep_research_task_checklist_20260502.md`
  - `AI-Data-Center-Analysis_migration_bundle_20260311/analysis/chatgpt55pro_m2f1_tes_problem_20260501.md`
- 然后查看项目级进度文件：
  - `毕业设计项目进度/代码开发进度管理.md`
- 再查看长期路线和约束：
  - `项目目标/技术路线.md`
- 如果需要理解为什么当前路线是这样定的，再查看 `项目目标/` 下最新的 handoff 和决策文档，例如：
  - `项目目标/archive/handoff_GPTCodex_2026-04-25.md`
  - `项目目标/archive/决策-切回-Nanjing-Jiangsu-TOU-2026-04-22.md`

### 如何理解这些计划文件

- `analysis/` 下的任务清单、问题定义和阶段分析：默认视为“当前执行层计划”和最近研究上下文。
- `毕业设计项目进度/代码开发进度管理.md`：默认视为“总进度与阶段状态面板”。
- `项目目标/技术路线.md`：默认视为“长期技术路线与总体设计约束”。
- `项目目标/handoff_*.md` 和 `决策-*.md`：默认视为“历史决策与交接上下文”，用于解释为什么当前方案如此，而不是替代当前执行清单。

### 默认写结果位置

- 新的分析结论、审计报告、对比表、阶段性说明：默认写到 `AI-Data-Center-Analysis_migration_bundle_20260311/analysis/`。
- 新的训练和评估运行产物：默认由脚本写到 `AI-Data-Center-Analysis_migration_bundle_20260311/runs/`，不要手工散落到根目录。
- 新的后台作业记录、stdout/stderr、status、manifest：默认写到 `AI-Data-Center-Analysis_migration_bundle_20260311/training_jobs/`。
- 新的项目级路线说明、交接文档、决策记录：默认写到 `项目目标/`。
- 只有在用户明确要求时，才更新 `毕业设计项目进度/代码开发进度管理.md` 这类总进度文件。

### 结果命名约定

- `analysis/` 下的新文件默认使用“主题 + 日期”的方式命名，并尽量延续现有风格，例如：
  - `m2f1_<topic>_YYYYMMDD.md`
  - `m2f1_<topic>_YYYYMMDD.json`
  - `m2f1_<topic>_YYYYMMDD.csv`
- 对已有结论做补充时，优先新建带日期的新文件，不覆盖旧证据。
- 不要把临时分析结果直接写到项目根目录，除非用户明确要求。

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
- 如果用户没有明确说明目标目录，但任务显然是代码、训练、评估或实验问题，默认目标目录是 `AI-Data-Center-Analysis_migration_bundle_20260311/`。
- 如果用户说“看当前计划”“按现在计划做”“更新结果”，默认按本文件中的“当前计划与结果落盘”规则执行。
- 新窗口不会继承旧窗口里已经创建好的 agent 实例；如果需要，应按本文件中的角色重新创建。

## 输出要求

- 先给结论，再给依据，再给下一步。
- 不确定时明确说明不确定点，并给出最小验证方法。
- 避免空泛建议，例如“继续试试”或“训练更久”；优先给最小可执行方案。
