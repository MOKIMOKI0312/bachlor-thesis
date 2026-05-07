# 文献简述

## 基本信息

- 编号：016
- 标题：Physics-guided deep reinforcement learning for optimized data center cooling and waste heat recovery utilizing aquifer thermal energy storage
- 作者：Yingbo Zhang a , Zixuan Wang a, Konstantin Filonenko c , Dominik Franjo Dominković c ,; Shengwei Wang a,b,*
- 年份：2026
- DOI/source：10.1016/j.apenergy.2025.126984
- 文献类别：other_references
- PDF 页数：14
- 可抽取文本字符数：59846
- 复制的 PDF：`2026_Zhang_Physics_guided_deep_reinforcement_learning_for_optimized_data_center_coo.pdf`

## 原始路径与重复项

- `docs\literature\other_references\1-s2.0-S0306261925017143-main.pdf` | sha256 `ac37ada494e8` | other_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> Keywords: A critical challenge in sustainable data center operations lies in resolving the mismatch between escalating Data center cooling cooling demands and waste heat utilization potential. Conventional approaches address cooling and heat re­ Waste heat recovery covery as separate processes, incurring systemic inefficiencies. This study develops a physics-guided deep Aquifer thermal energy storage reinforcement learning (DRL) framework that synergistically optimizes Aquifer Thermal Energy Storage (ATES) Deep reinforcement learning for data center cooling and waste heat recovery for nearby office buildings via heat pumps. By incorporating Control optimization domain knowledge into the reward function design, the proposed approach effectively addresses delayed re­ wards in long-term ATES thermal balance and enables effective agent training with limited datasets. Multiple advanced DRL agents, such as DQN and D3QN, are trained to control the operation of the integrated energy systems, with dual objectives of minimizing energy consumption and maintaining annual ATES thermal balance. Results demonstrate that the both D3QN and Double DQN algorithms perform well, reducing annual energy consumption by approximately 53 % while also maintaining ATES balance within 4 %. Furthermore, the system achieves a remarkable power usage effectiveness (PUE) of 1.177, representing a 9.5 % improveme...

## 与当前项目主线的关系

与当前主线相关信号：data center, TES/storage, MPC, tariff/TOU。需回到本项目模型和输入数据验证后才能写成当前模型事实。

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
