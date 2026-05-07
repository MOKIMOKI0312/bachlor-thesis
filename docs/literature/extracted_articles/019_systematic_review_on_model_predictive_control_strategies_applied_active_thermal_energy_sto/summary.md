# 文献简述

## 基本信息

- 编号：019
- 标题：Systematic review on model predictive control strategies applied to active thermal energy storage systems
- 作者：Joan Tarragona a, b, Anna Laura Pisello b, c, Cèsar Fernández a, Alvaro de Gracia a,; Luisa F. Cabeza a,; GREiA Research Group, Universitat de Lleida, Pere de Cabrera s/n, 25001-Lleida, Spain
- 年份：2021
- DOI/source：10.1016/j.rser.2021.111385
- 文献类别：other_references
- PDF 页数：14
- 可抽取文本字符数：87850
- 复制的 PDF：`2021_Tarragona_Systematic_review_on_model_predictive_control_strategies_applied_to_acti.pdf`

## 原始路径与重复项

- `docs\literature\other_references\1-s2.0-S1364032121006705-main.pdf` | sha256 `40345e849202` | other_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> Keywords: This paper presents a review of the application of model predictive control strategies to active thermal energy Thermal energy storage storage systems. To date, model predictive control has been used to manage such energy systems as heating, Model predictive control ventilation and air conditioning equipment or power generation plants. In all cases, the aim of the strategy has Systematic review been to anticipate both production and consumption decisions to optimize the system performance, reducing the Energy management final energy cost. This ability of the strategy to forecast weather conditions and predict demand requirements in Renewable energy Active systems advance exceeds the performance of conventional control methods and made the strategy a very effective option to be coupled with active thermal energy storage systems. In this regard, this review paper presents the progress and results of the combination of these two technologies. The key contributions consist of a summary of the technical parameters employed, such as the prediction horizon length, the computational architecture ap­ proaches, the thermal energy storage material used and the influence of renewables in this kind of system. Additionally, the review summarises the latest enhancements to overcome computational issues and an analysis of the objective functions employed in each study, which were mai...

## 与当前项目主线的关系

与当前主线相关信号：TES/storage, MPC, MILP, PV, tariff/TOU。需回到本项目模型和输入数据验证后才能写成当前模型事实。

## 核心公式/伪代码页线索

自动抽取；未做人工页码核对。

补充判断：无人工补充说明。

## 可迁移判断

- 可直接迁移：文献中的变量定义、优化目标结构、控制流程、设备调度约束可以作为建模参考。
- 不可直接当作当前模型事实：节能率、设备规模、城市气象、负荷曲线和控制效果必须回到 `Nanjing-DataCenter-TES-EnergyPlus/` 或 `mpc_v2/` 的模型、输入、日志和验证结果复核。

## 论文同步影响

本次只创建文献整理 Markdown 和 PDF 副本，未新增或删除 BibTeX 条目，也未改变当前 EnergyPlus/TES/PV/电价模型事实。因此默认不直接修改 `references.bib` 或 `thesis_draft.tex`。如果后续把本文献结论写进论文正文，需要再补 citation key 并同步检查 LaTeX 引用。

## 不确定点

- 无明显抽取告警；仍需人工核对公式排版和表格含义。
- 标题、作者、DOI 由 PDF 文本启发式抽取；正式引用前应人工核对出版社页或 BibTeX。
- 公式和算法片段见 `core_algorithm.md`，其中换行和上下标可能受 PDF 排版影响。
