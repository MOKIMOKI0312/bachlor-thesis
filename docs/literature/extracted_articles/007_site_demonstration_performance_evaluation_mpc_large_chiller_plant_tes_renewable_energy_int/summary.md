# 文献简述

## 基本信息

- 编号：007
- 标题：Site demonstration and performance evaluation of MPC for a large chiller plant with TES for renewable energy integration and grid decarbonization
- 作者：Donghun Kim; Zhe Wang; James Brugger; David Blum; Michael Wetter; Tianzhen Hong; Mary Ann Piette
- 年份：2022
- DOI/source：10.1016/j.apenergy.2022.119343
- 文献类别：core_references
- PDF 页数：16
- 可抽取文本字符数：79232
- 复制的 PDF：`2022_Kim_Site_demonstration_and_performance_evaluation_of_MPC_for_a_large_chiller.pdf`

## 原始路径与重复项

- `docs\literature\core_references\qt2tx5s8t5.pdf` | sha256 `60d394b11970` | core_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> Keywords: Thermal energy storage (TES) for a cooling plant is a crucial resource for load flexibility. Traditionally, simple, MPC demonstration heuristic control approaches, such as the storage priority control which charges TES during the nighttime and Building optimal control discharges during the daytime, have been widely used in practice, and shown reasonable performance in the Model predictive control past benefiting both the grid and the end-users such as buildings and district energy systems. However, the District energy system increasing penetration of renewables changes the situation, exposing the grid to a growing duck curve, which Carbon reduction Renewable energy encourages the consumption of more energy in the daytime, and volatile renewable generation which requires dynamic planning. The growing pressure of diminishing greenhouse gas emissions also increases the complexity of cooling TES plant operations as different control strategies may apply to optimize operations for energy cost or carbon emissions. This paper presents a model predictive control (MPC), site demonstration and evaluation results of optimal operation of a chiller plant, TES and behind-meter photovoltaics for a campus-level district cooling system. The MPC was formulated as a mixed-integer linear program for better numerical and control properties. Compared with baseline rule-based controls, the ...

## 与当前项目主线的关系

与当前主线相关信号：TES/storage, MPC, MILP, EnergyPlus, PV, tariff/TOU。需回到本项目模型和输入数据验证后才能写成当前模型事实。

## 核心公式/伪代码页线索

p6-p8 MPC formulation/MILP/constraints; p10-p12 PV/TES performance; p14-p15 appendix tank and power model.

补充判断：最接近当前 TES + PV + MPC + 冷站验证主线，虽非数据中心但方法迁移价值高。

## 可迁移判断

- 可直接迁移：文献中的变量定义、优化目标结构、控制流程、设备调度约束可以作为建模参考。
- 不可直接当作当前模型事实：节能率、设备规模、城市气象、负荷曲线和控制效果必须回到 `Nanjing-DataCenter-TES-EnergyPlus/` 或 `mpc_v2/` 的模型、输入、日志和验证结果复核。

## 论文同步影响

本次只创建文献整理 Markdown 和 PDF 副本，未新增或删除 BibTeX 条目，也未改变当前 EnergyPlus/TES/PV/电价模型事实。因此默认不直接修改 `references.bib` 或 `thesis_draft.tex`。如果后续把本文献结论写进论文正文，需要再补 citation key 并同步检查 LaTeX 引用。

## 不确定点

- 无明显抽取告警；仍需人工核对公式排版和表格含义。
- 标题、作者、DOI 由 PDF 文本启发式抽取；正式引用前应人工核对出版社页或 BibTeX。
- 公式和算法片段见 `core_algorithm.md`，其中换行和上下标可能受 PDF 排版影响。
