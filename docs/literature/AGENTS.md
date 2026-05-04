# Literature Rules

本目录保存毕业设计相关论文、参考文献和文献证据。它不是代码、模型或实验输出入口。

## 当前目录分工

- `core_references/`：核心参考文献。默认用于支撑当前论文主线，例如数据中心冷却、EnergyPlus、TES、PV、电价、MPC、控制或能耗建模。
- `other_references/`：其它参考文献。用于背景扩展、方法参考或备选论据，不默认视为当前主线依据。

## 使用边界

- 不在本目录中开发代码、修改 epJSON、保存 EnergyPlus 输出或存放临时运行产物。
- 不把文献观点直接写成当前模型事实；模型事实必须回到 epJSON、runner、输入数据或 EnergyPlus 日志验证。
- 不把 PDF 移入当前模型包 `Nanjing-DataCenter-TES-EnergyPlus/`，除非用户明确要求打包或交付。
- 文献只能作为设计依据、背景、方法或论文章节引用来源。

## 文献整理规则

- 新增文献时优先放入 `core_references/` 或 `other_references/`，不要散落在 `docs/literature/` 根目录。
- 文件名可以保留出版社原始文件名；如果重命名，应保留作者、年份或主题信息。
- 不创建空白占位 PDF。
- 不删除重复 PDF，除非已经确认内容、版本和引用状态。
- 如果无法确认来源或版本，明确写 `source unknown` 或 `version unknown`。

## 摘要和证据规则

如需为文献建立 Markdown 摘要，应记录：

- citation key 或可识别标题
- authors / year
- source 或 DOI
- 与当前项目的关系
- 原文明确结论
- 你的归纳
- 是否已经能迁移到当前 EnergyPlus/TES/PV/电价模型
- 未验证点

不要把“文献中可行”直接写成“当前模型已实现”。

## 与论文目录的关系

- 论文引用库位于 `../project_management/毕业设计论文/references.bib`。
- 新增或删除文献引用时，应检查 `thesis_draft.tex` 是否引用对应 citation key。
- 不随意改 citation key；如果必须改，必须同步更新 LaTeX 正文引用。

## Agent 分工要求

- 涉及 PDF 解析、文献摘要、引用整理、文献分类或 BibTeX 维护时，默认由显式 GPT-5.5 subagent 执行。
- 主 agent 默认只做目标澄清、只读核对、摘要验收和最终汇报。
- 文献处理 subagent 必须返回：
  - 处理文件清单
  - 每篇文献来源或未知项
  - 摘要依据
  - 与当前项目主线的关系
  - 是否影响 `references.bib` 或 `thesis_draft.tex`
  - 不确定点和后续验证建议
