# 文献简述

## 基本信息

- 编号：009
- 标题：An advanced control strategy for optimizing the operation state of chillers with cold storage technology in data center
- 作者：Yiqun Zhu a, Quan Zhang a, *, Liping Zeng b, Jiaqiang Wang c, Sikai Zou d, Haoran Zheng a
- 年份：2023
- DOI/source：10.1016/j.enbuild.2023.113684
- 文献类别：other_references
- PDF 页数：17
- 可抽取文本字符数：57915
- 复制的 PDF：`2023_Zhu_An_advanced_control_strategy_for_optimizing_the_operation_state_of_chill.pdf`

## 原始路径与重复项

- `docs\literature\other_references\1-s2.0-S0378778823009143-main.pdf` | sha256 `7d2d0773909d` | other_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> Keywords: Data centers facing huge energy consumption challenges, the chiller is one of the main energy expenditure Data center equipment. This study proposed a novel efficient operation strategy for chillers integrated with cold water Model predictive control (MPC) storage technology. An advanced model predictive control (MPC) was developed to regulate the running pa­ Water storage rameters of the chillers and cold water storage device, targeting the maximum energy efficiency of cooling Mixed integer linear programming (MILP) Model mismatch system. Specifically, the mixed integer linear programming (MILP) algorithm was constructed in MPC with low computer calculation cost to solve the optimization problem. The performance of the MPC strategy was validated through an actual data center test located at Guangzhou city and further comprehensively assessed through annual simulations. The relative error in terms of refrigeration capacity and cooling capacity of cold water storage device between simulation and field test was less than 5 %. During the on-site testing, compared with a Baseline strategy, the coefficient of performance (COP) of the MPC strategy increased by 1.96 on average with the cooling system energy consumption reduced by 5.8 %, and the power usage effectiveness (PUE) was reduced by 0.013. The annual PUE decreased by 0.018 and the annual electricity cost decreased by...

## 与当前项目主线的关系

与当前主线相关信号：data center, TES/storage, MPC, MILP, PV, tariff/TOU。需回到本项目模型和输入数据验证后才能写成当前模型事实。

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
