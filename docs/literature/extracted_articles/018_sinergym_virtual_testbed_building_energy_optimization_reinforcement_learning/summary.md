# 文献简述

## 基本信息

- 编号：018
- 标题：Sinergym – A virtual testbed for building energy optimization with Reinforcement Learning
- 作者：Alejandro Campoy-Nieves ∗ , Antonio Manjavacas, Javier Jiménez-Raboso,; Miguel Molina-Solana, Juan Gómez-Romero
- 年份：2025
- DOI/source：10.1016/j.enbuild.2024.115075
- 文献类别：other_references
- PDF 页数：15
- 可抽取文本字符数：71488
- 复制的 PDF：`2025_Campoy_Nieves_Sinergym_A_virtual_testbed_for_building_energy_optimization_with_Reinfor.pdf`

## 原始路径与重复项

- `docs\literature\other_references\1-s2.0-S0378778824011915-main.pdf` | sha256 `413d2b48649c` | other_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> Dataset link: https:// Simulation has become a crucial tool for Building Energy Optimization (BEO) as it enables the evaluation of github.com/ugr-sail/sinergym diﬀerent design and control strategies at a low cost. Machine Learning (ML) algorithms can leverage large- scale simulations to learn optimal control from vast amounts of data without supervision, particularly under Keywords: Building Energy Optimization the Reinforcement Learning (RL) paradigm. Unfortunately, the lack of open and standardized tools has hindered Simulation the widespread application of ML and RL to BEO. To address this issue, this paper presents Sinergym, an open- HVAC source Python-based virtual testbed for large-scale building simulation, data collection, continuous control, and EnergyPlus experiment monitoring. Sinergym provides a consistent interface for training and running controllers, predeﬁned Machine Learning benchmarks, experiment visualization and replication support, and comprehensive documentation in a ready-to- Reinforcement Learning use software library. This paper 1) highlights the main features of Sinergym in comparison to other existing frameworks, 2) describes its basic usage, and 3) demonstrates its applicability for RL-based BEO through several representative examples. By integrating simulation, data, and control, Sinergym supports the development of intelligent, data-driven applicat...

## 与当前项目主线的关系

与当前主线相关信号：data center, MPC, EnergyPlus。需回到本项目模型和输入数据验证后才能写成当前模型事实。

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
