# 文献简述

## 基本信息

- 编号：021
- 标题：Toward Physics-Guided Safe Deep Reinforcement Learning for Green Data Center Cooling Control
- 作者：Ruihang Wang Xinyi Zhang Xin Zhou
- 年份：2022
- DOI/source：unknown
- 文献类别：other_references
- PDF 页数：11
- 可抽取文本字符数：63001
- 复制的 PDF：`2022_Wang_Toward_Physics_Guided_Safe_Deep_Reinforcement_Learning_for_Green_Data_Ce.pdf`

## 原始路径与重复项

- `docs\literature\other_references\ICCPS22.pdf` | sha256 `f36a4b080e3d` | other_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> DC’s electricity supply [26]. Therefore, perpendicular to the design Deep reinforcement learning (DRL) has shown good performance and adoption of new energy-efficient IT equipment, proper con- in tackling Markov decision process (MDP) problems. As DRL opti- trol of the cooling system based on distributed sensing and cyber mizes a long-term reward, it is a promising approach to improving intelligence is critical to improving DC energy efficiency. the energy efficiency of data center cooling. However, enforcement In this paper, we consider the problem of DC cooling control of thermal safety constraint during DRL’s state exploration is a that aims at reducing the DC energy usage subject to the IT equip- main challenge. The widely adopted reward shaping approach adds ment’s thermal safety constraint. Any IT device specifies the highest negative reward when the exploratory action results in unsafety. temperature that it can tolerate (e.g., 32°C for ASHRAE Class A1 Thus, it needs to experience sufficient unsafe states before it learns servers [5]). Crossing the temperature upper limit may cause device how to prevent unsafety. In this paper, we propose a safety-aware shutdown and service disruption. Many DC operators adopt an op- DRL framework for single-hall data center cooling control. It applies eration scheme of maintaining the temperature in the hot zone of offline imitation lear...

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
