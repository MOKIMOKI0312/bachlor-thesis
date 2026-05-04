# Thesis Writing Rules

本目录保存毕业设计论文正文、引用库和写作相关文件。

## 当前文件

- `thesis_draft.tex`：论文草稿。
- `references.bib`：BibTeX 引用库。

## 使用边界

- 本目录不是代码或模型执行入口。
- 不在本目录中保存 EnergyPlus 输出、临时代码、实验原始数据或 PDF 文献原文。
- 不把论文中的计划性表述当成当前执行口径；执行口径以用户最新指令、根 `AGENTS.md` 和活跃模型包状态为准。

## 论文写作事实要求

修改论文技术内容时，必须能追溯到至少一种证据：

- 当前 EnergyPlus 模型文件
- runner 或验证日志
- 外部输入数据
- 文献来源
- 用户明确决策
- 已归档历史材料

对应路径：

```text
../../../Nanjing-DataCenter-TES-EnergyPlus/
../../literature/
../../../_archive/project_goals/
```

## LaTeX 修改规则

- 修改 `thesis_draft.tex` 前先确认目标章节。
- 不做全文件无意义格式化。
- 不编造实验结果、模型参数、文献结论或引用。
- 对模型、TES、PV、电价、冷却系统和验证结果的描述，应与当前模型包文档一致。
- 如果论文中使用某次运行结果，应注明运行目录、命令或验证日期。
- 大段新增内容应保持论文语气，不写成聊天记录或任务计划。

## BibTeX 规则

- 修改 `references.bib` 时，不随意改已有 citation key。
- 删除 BibTeX 条目前，必须确认 `thesis_draft.tex` 没有引用该 key。
- 新增 citation key 后，应保持命名稳定，并能追溯到 `../../literature/` 中的文献文件或外部来源。
- 如果某条引用来源不确定，先标注待确认，不要编造 DOI、期刊或年份。

## 提交前论文同步要求

- 每次提交代码、EnergyPlus 模型、输入数据、验证结果或项目结构变更前，必须检查本目录论文文件是否需要同步更新。
- 需要同步的典型情况包括：
  - EnergyPlus 模型结构或参数变化
  - runner 或验证流程变化
  - weather、price、PV 输入变化
  - warning/severe error 状态变化
  - 项目目录结构或主线目标变化
  - 新增、删除或替换文献引用
- 如影响论文正文，必须更新 `thesis_draft.tex`。
- 如影响引用库，必须更新 `references.bib`。
- 如无需更新，应在提交说明或最终回复中说明“论文无需更新”的理由。

## 与其它文档同步

以下变化需要检查是否同步其它文档：

- 论文中改变了项目目标或技术路线。
- 论文中新增或修改 EnergyPlus 模型描述。
- 论文中引用新的文献或删除旧引用。
- 论文中使用新的实验/验证结果。

需要同步检查的位置：

```text
../毕业设计技术路线及进度安排/
../../../Nanjing-DataCenter-TES-EnergyPlus/docs/
../../literature/
```

## Agent 分工要求

- 涉及论文正文修改、结构调整、BibTeX 维护或引用检查时，默认由显式 GPT-5.5 subagent 执行。
- 主 agent 默认只做目标澄清、事实核对、diff 审查和最终验收。
- 修改 subagent 必须返回：
  - 修改文件清单
  - 修改章节或 BibTeX key
  - 证据来源
  - 未确认引用或事实
  - 是否通过 LaTeX/BibTeX 基本一致性检查
  - 是否需要同步更新模型包文档或进度文档
