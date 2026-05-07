# 文献简述

## 基本信息

- 编号：022
- 标题：Transforming Cooling Optimization for Green Data Center via Deep Reinforcement Learning
- 作者：Yuanlong Li, Yonggang Wen, Kyle Guan, and Dacheng Tao; data center (DC). Developing an optimal control policy for DC cooling energy.; cooling system is a challenging task. The prevailing approaches Cooling energy optimization involves the control of a so-
- 年份：2017
- DOI/source：unknown
- 文献类别：other_references
- PDF 页数：11
- 可抽取文本字符数：59508
- 复制的 PDF：`2017_Li_Transforming_Cooling_Optimization_for_Green_Data_Center_via_Deep_Reinfor.pdf`

## 原始路径与重复项

- `docs\literature\other_references\1709.05077v4.pdf` | sha256 `23a75b39e60f` | other_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> —Cooling system plays a critical role in a modern sources of energy consumption in DC (about 38% [3]), the data center (DC). Developing an optimal control policy for DC cooling energy. cooling system is a challenging task. The prevailing approaches Cooling energy optimization involves the control of a so- often rely on approximating system models that are built upon the knowledge of mechanical cooling, electrical and thermal phisticated cooling system, which consists of multiple compo- arXiv:1709.05077v4 [cs.AI] 18 Jul 2018 management, which is difficult to design and may lead to sub- nents, such as cooling tower, chiller, and ventilation system, optimal or unstable performances. In this paper, we propose etc. A common practice of DC cooling system control is to utilizing the large amount of monitoring data in DC to optimize adjust the set-points, i.e., the target values of different control the control policy. To do so, we cast the cooling control policy variables. For example, by setting the temperature control design into an energy cost minimization problem with tempera- ture constraints, and tap it into the emerging deep reinforcement variable at the outlet of an air conditioner to the desired value, learning (DRL) framework. Specifically, we propose an end-to- the air conditioner can adjust its internal state to meet the set- end cooling control algorithm (CCA) that is bas...

## 与当前项目主线的关系

与当前主线相关信号：data center, EnergyPlus, tariff/TOU。需回到本项目模型和输入数据验证后才能写成当前模型事实。

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
