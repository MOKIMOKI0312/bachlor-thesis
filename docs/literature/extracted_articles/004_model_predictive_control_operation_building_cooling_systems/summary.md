# 文献简述

## 基本信息

- 编号：004
- 标题：Model Predictive Control for the Operation of Building Cooling Systems
- 作者：Yudong Ma; Francesco Borrelli; Brandon Hencey; Brian Coffey; Sorin Bengea; Philip Haves
- 年份：2009
- DOI/source：unknown
- 文献类别：core_references
- PDF 页数：6
- 可抽取文本字符数：28540
- 复制的 PDF：`2009_Ma_Model_Predictive_Control_for_the_Operation_of_Building_Cooling_Systems.pdf`

## 原始路径与重复项

- `docs\literature\core_references\988176.pdf` | sha256 `588860140cee` | core_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> — A model-based predictive control (MPC) is de- uses an oversimplified campus load model and presents signed for optimal thermal energy storage in building cooling simulation results. In this paper a more detailed campus load systems. We focus on buildings equipped with a water tank model is developed and validated with measured historical used for actively storing cold water produced by a series of chillers. Typically the chillers are operated at night to recharge data. Moreover experimental results with the MPC scheme the storage tank in order to meet the building demands on the are reported. following day. In this paper, we build on our previous work, Although this paper focuses on the specific architecture of improve the building load model, and present experimental the UC Merced Campus, the main ideas and methodologies results. The experiments show that MPC can achieve reduction can be applied to a wider class of building systems which in the central plant electricity cost and improvement of its efficiency. use thermal energy storage. In particular the contributions of this paper and our previous work [10] include: (i) the

## 与当前项目主线的关系

与当前主线相关信号：TES/storage, MPC, EnergyPlus。需回到本项目模型和输入数据验证后才能写成当前模型事实。

## 核心公式/伪代码页线索

p2 system model; p4 control variables and constraints; p5 MPC problem formulation; p6 algorithm/move blocking.

补充判断：建筑冷站和冷水罐 TES-MPC 方法参考，适合迁移控制变量、约束和滚动优化结构。

## 可迁移判断

- 可直接迁移：文献中的变量定义、优化目标结构、控制流程、设备调度约束可以作为建模参考。
- 不可直接当作当前模型事实：节能率、设备规模、城市气象、负荷曲线和控制效果必须回到 `Nanjing-DataCenter-TES-EnergyPlus/` 或 `mpc_v2/` 的模型、输入、日志和验证结果复核。

## 论文同步影响

本次只创建文献整理 Markdown 和 PDF 副本，未新增或删除 BibTeX 条目，也未改变当前 EnergyPlus/TES/PV/电价模型事实。因此默认不直接修改 `references.bib` 或 `thesis_draft.tex`。如果后续把本文献结论写进论文正文，需要再补 citation key 并同步检查 LaTeX 引用。

## 不确定点

- 无明显抽取告警；仍需人工核对公式排版和表格含义。
- 标题、作者、DOI 由 PDF 文本启发式抽取；正式引用前应人工核对出版社页或 BibTeX。
- 公式和算法片段见 `core_algorithm.md`，其中换行和上下标可能受 PDF 排版影响。
