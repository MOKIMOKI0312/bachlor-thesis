# 文献简述

## 基本信息

- 编号：008
- 标题：State-of-the-art on thermal energy storage technologies in data center
- 作者：Lijun Liu; Quan Zhang; Zhiqiang Zhai; Chang Yue; Xiaowei Ma
- 年份：2020
- DOI/source：10.1016/j.enbuild.2020.110345
- 文献类别：core_references
- PDF 页数：20
- 可抽取文本字符数：113154
- 复制的 PDF：`2020_Liu_State_of_the_art_on_thermal_energy_storage_technologies_in_data_center.pdf`

## 原始路径与重复项

- `docs\literature\core_references\1-s2.0-S0378778819336771-main.pdf` | sha256 `e1f48667eba4` | core_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> Article history: Data center consumes a great amount of energy and accounts for an increasing proportion of global Received 4 December 2019 energy demand. Low efficiency of cooling systems leads to a cooling cost at about 40% of the total energy Revised 23 May 2020 consumption of a data center. Due to specific operation conditions, high security and high cooling load is Accepted 24 July 2020 required in data center. To achieve energy saving, cost saving and high security, novel cooling systems Available online 29 July 2020 integrated with thermal energy storage (TES) technologies have been proposed. This paper presents an extensive overview of the research advances and the applications of TES technologies in data centers. Keywords: Operating conditions, energy mismatch and requirement of high security in data center were overviewed. Thermal energy storage Data center Principles and characteristics of TES technologies were discussed. Applications of passive TES coupled air Energy saving flow and applications of active TES integrated cooling system are summarizes, and the design and perfor- Emergency cooling mance of these TES integrated thermal systems are analyzed, with a focus on energy saving, cost savings Cooling system design and high security. Ó 2020 Elsevier B.V. All rights reserved. Contents

## 与当前项目主线的关系

与当前主线相关信号：data center, TES/storage, PV, tariff/TOU。需回到本项目模型和输入数据验证后才能写成当前模型事实。

## 核心公式/伪代码页线索

p3-p5 TES principles; p10-p15 active TES; p17 operation strategies based on TES to reduce operation cost.

补充判断：核心支撑数据中心 TES 背景、蓄冷技术分类和运行策略，不是当前模型已实现事实。

## 可迁移判断

- 可直接迁移：文献中的变量定义、优化目标结构、控制流程、设备调度约束可以作为建模参考。
- 不可直接当作当前模型事实：节能率、设备规模、城市气象、负荷曲线和控制效果必须回到 `Nanjing-DataCenter-TES-EnergyPlus/` 或 `mpc_v2/` 的模型、输入、日志和验证结果复核。

## 论文同步影响

本次只创建文献整理 Markdown 和 PDF 副本，未新增或删除 BibTeX 条目，也未改变当前 EnergyPlus/TES/PV/电价模型事实。因此默认不直接修改 `references.bib` 或 `thesis_draft.tex`。如果后续把本文献结论写进论文正文，需要再补 citation key 并同步检查 LaTeX 引用。

## 不确定点

- 无明显抽取告警；仍需人工核对公式排版和表格含义。
- 标题、作者、DOI 由 PDF 文本启发式抽取；正式引用前应人工核对出版社页或 BibTeX。
- 公式和算法片段见 `core_algorithm.md`，其中换行和上下标可能受 PDF 排版影响。
