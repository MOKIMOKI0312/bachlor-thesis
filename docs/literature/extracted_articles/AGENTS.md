# Extracted Articles Rules

本目录是从 `docs/literature/core_references/` 和 `docs/literature/other_references/` 生成的低 token 文献索引目录，用于快速读取论文摘要、核心公式、伪代码、算法流程和可复现线索。

它不是原始文献归档目录，也不是 EnergyPlus 模型、MPC 实验或论文结果目录。

## 使用边界

- 不把本目录中的文献结论直接写成当前模型事实。
- 当前模型事实必须回到 `Nanjing-DataCenter-TES-EnergyPlus/` 的 epJSON、runner、输入数据或 EnergyPlus 日志验证。
- MPC 算法事实必须回到 `mpc_v2/` 的代码、配置、验证命令和结果验证。
- 本目录可以作为设计依据、背景证据、公式索引、算法复现入口和论文引用辅助材料。
- 不在本目录保存 EnergyPlus 输出、MPC 运行结果、临时截图或实验中间产物。

## 目录结构要求

- `README.md`：总索引，列出文献分组、标题、DOI、重命名后的 PDF 和文件夹路径。
- `manifest.json`：机器可读清单，记录来源路径、SHA256、去重信息、页数、抽取数量和重命名后的 PDF 路径。
- 每篇文献一个子文件夹。
- 每个文献子文件夹必须包含且只包含一个 PDF 副本，以及：
  - `summary.md`
  - `core_algorithm.md`

## PDF 副本命名规则

- 只重命名本目录中的 PDF 副本，不重命名 `core_references/` 或 `other_references/` 中的原始 PDF。
- PDF 文件名格式：
  `YYYY_FirstAuthor_Short_Title.pdf`
- 年份未知时使用 `unknown_year`。
- 作者未知时使用 `unknown`。
- 文件名应使用 Windows 安全字符，优先 ASCII 字母、数字和下划线。
- 标题过长时可以截断，但必须保留年份、第一作者和可识别标题。
- 重命名 PDF 后必须同步更新：
  - 对应 `summary.md` 中的 PDF 文件名
  - 对应 `core_algorithm.md` 中的 PDF 文件名
  - `manifest.json` 中的 `copied_pdf`
  - `README.md` 中的 `Renamed PDF`

## 去重和来源记录

- 不删除原始 PDF，也不删除上层目录中的重复 PDF，除非用户明确要求并已经核对引用状态。
- 如果多份 PDF 属于同一篇文章，应优先按 DOI 合并；没有 DOI 时再按标题、SHA256 和首页信息判断。
- 合并后只在本目录为该文章保留一个文献文件夹。
- `summary.md` 必须记录所有原始来源路径和每个来源的 SHA256 前缀。
- `manifest.json` 必须保留 `all_sources`，不能只保留被复制的那一份 PDF。

## summary.md 要求

每篇文献的 `summary.md` 至少记录：

- 编号
- 标题
- 作者
- 年份
- DOI/source，未知则写 `unknown`
- 文献类别：`core_references` 或 `other_references`
- PDF 页数
- 可抽取文本字符数
- 重命名后的 PDF 文件名
- 原始路径与重复项
- 摘要依据
- 与当前项目主线的关系
- 核心公式/伪代码页线索
- 可迁移判断
- 论文同步影响
- 不确定点

不要把“文献提出/文献验证”写成“本项目已经实现/本项目已经验证”。

## core_algorithm.md 要求

每篇文献的 `core_algorithm.md` 至少记录：

- 来源 PDF 文件名
- 标题
- 人工核对页线索
- 算法/控制流程候选
- 公式/优化模型候选
- 符号表/变量定义候选
- 面向本项目的复现接口

公式和伪代码抽取时优先保留：

- 优化目标函数
- 约束条件
- 状态转移方程
- SOC/TES/储能动态
- MPC rolling horizon / receding horizon 流程
- MILP/MINLP 决策变量和二进制变量
- 输入、状态、决策、目标、约束的映射关系

如果 PDF 文本抽取破坏了上下标、分式或跨栏顺序，不要把候选公式当作最终公式；应标注为候选，并给出页码让后续人工核对。

## 修改验证要求

每次新增、删除、重命名或合并文献后，必须检查：

- 每个文献子文件夹仍然只有一个 PDF、一个 `summary.md`、一个 `core_algorithm.md`。
- PDF 副本 SHA256 与 `manifest.json` 中记录一致。
- `summary.md` 和 `core_algorithm.md` 中的 PDF 文件名与实际文件名一致。
- `README.md` 与 `manifest.json` 的文献数量、标题、文件夹和 PDF 名称一致。
- 如果来源、作者、年份或 DOI 不确定，必须明确写 `unknown` 或说明不确定点。

## 与论文和版本记录的关系

- 只整理本目录 Markdown 和 PDF 副本，且不改变论文事实基础时，不需要更新 `thesis_draft.tex`。
- 新增或删除论文引用、修正 citation key、把文献结论写入正文时，必须同步检查并更新 `docs/project_management/毕业设计论文/thesis_draft.tex` 和 `references.bib`。
- 只维护文献索引、摘要和 PDF 副本命名时，通常不需要更新 `CHANGELOG.md`。
- 如果本目录变更被作为可复现版本、论文事实依据或正式交付材料的一部分，则必须按项目根目录 `AGENTS.md` 的版本记录要求检查 `CHANGELOG.md`。

## Agent 工作方式

- 批量 PDF 解析、文献摘要、引用整理或 BibTeX 核对时，遵守上层 `docs/literature/AGENTS.md` 的 subagent 分工要求。
- 主 agent 负责目标澄清、目录规则、去重策略、结果验收和最终汇报。
- 文献处理 agent 必须区分：
  - PDF 中明确可见的事实
  - 基于标题、DOI、哈希和首页信息的推断
  - 仍需人工核对的未知项
