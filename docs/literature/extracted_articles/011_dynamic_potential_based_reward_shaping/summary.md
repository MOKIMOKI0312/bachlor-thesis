# 文献简述

## 基本信息

- 编号：011
- 标题：Dynamic Potential-Based Reward Shaping
- 作者：Sam Devlin Daniel Kudenko
- 年份：2012
- DOI/source：unknown
- 文献类别：other_references
- PDF 页数：8
- 可抽取文本字符数：36370
- 复制的 PDF：`2012_Devlin_Dynamic_Potential_Based_Reward_Shaping.pdf`

## 原始路径与重复项

- `docs\literature\other_references\2C_3.pdf` | sha256 `a66d8d5a7ed3` | other_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> static potential function based on states alone [15]. Contin- Potential-based reward shaping can significantly improve uing interest in this method has expanded its capabilities to the time needed to learn an optimal policy and, in multi- providing similar guarantees when potentials are based on agent systems, the performance of the final joint-policy. It states and actions [24] or the agent is not alone but acting has been proven to not alter the optimal policy of an agent in a common environment with other shaped or unshaped learning alone or the Nash equilibria of multiple agents learn- agents [8]. ing together. However, all existing proofs presume a static potential However, a limitation of existing proofs is the assumption function. A static potential function represents static knowl- that the potential of a state does not change dynamically edge and, therefore, can not be updated online whilst an during the learning. This assumption often is broken, espe- agent is learning. cially if the reward-shaping function is generated automati- Despite these limitations in the theoretical results, em- cally. pirical work has demonstrated the usefulness of a dynamic In this paper we prove and demonstrate a method of ex- potential function [10, 11, 12, 13]. When applying potential- tending potential-based reward shaping to allow dynamic based reward shaping, a common challenge is how ...

## 与当前项目主线的关系

背景参考；未从文本中发现与当前 TES/PV/电价/EnergyPlus 主线的强直接信号。

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
