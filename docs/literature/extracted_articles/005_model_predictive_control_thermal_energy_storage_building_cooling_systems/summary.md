# 文献简述

## 基本信息

- 编号：005
- 标题：Model Predictive Control of Thermal Energy Storage in Building Cooling Systems
- 作者：Yudong Ma; Francesco Borrelli; Brandon Hencey; Andrew Packard; Scott Bortoff
- 年份：2009
- DOI/source：unknown
- 文献类别：core_references
- PDF 页数：8
- 可抽取文本字符数：31984
- 复制的 PDF：`2009_Ma_Model_Predictive_Control_of_Thermal_Energy_Storage_in_Building_Cooling_S.pdf`

## 原始路径与重复项

- `docs\literature\core_references\Ma_09_Proc-CDC09_WeA12.1.pdf` | sha256 `d5e1c8278c90` | core_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> — A preliminary study on the application of a model- storage tank enables load shifting to off-peak hours to reduce based predictive control (MPC) of thermal energy storage in peak demand, the lack of an optimized operation results building cooling systems is presented. We focus on buildings in conservatively over-charging the tank where conductive equipped with a water tank used for actively storing cold water produced by a series of chillers. Typically the chillers losses erode efficiency. The objective of this paper is to are operated each night to recharge the storage tank in order design a predictive controller in order to minimize energy to meet the buildings demand on the following day. A MPC for consumption while satisfying the unknown but bounded the chillers operation is designed in order to optimally store the cooling demand of the campus buildings and operational thermal energy in the tank by using predictive knowledge of constraints. building loads and weather conditions. This paper addresses real-time implementation and feasibility issues of the MPC The main idea of predictive control is to use the model of scheme by using a (1) simplified hybrid model of the system, the plant to predict the future evolution of the system [7], (2) periodic robust invariant sets as terminal constraints and [8], [13]. At each sampling time, starting at the current (3) a moving windo...

## 与当前项目主线的关系

与当前主线相关信号：TES/storage, MPC, EnergyPlus, tariff/TOU。需回到本项目模型和输入数据验证后才能写成当前模型事实。

## 核心公式/伪代码页线索

p2-p4 hybrid/TES tank model; p5 MPC problem formulation; p6 Algorithm 1 Moving Window Blocking and invariant set.

补充判断：TES-MPC 经典建模与终端可行性参考；非数据中心但高度支撑 MILP/MPC 叙事。

## 可迁移判断

- 可直接迁移：文献中的变量定义、优化目标结构、控制流程、设备调度约束可以作为建模参考。
- 不可直接当作当前模型事实：节能率、设备规模、城市气象、负荷曲线和控制效果必须回到 `Nanjing-DataCenter-TES-EnergyPlus/` 或 `mpc_v2/` 的模型、输入、日志和验证结果复核。

## 论文同步影响

本次只创建文献整理 Markdown 和 PDF 副本，未新增或删除 BibTeX 条目，也未改变当前 EnergyPlus/TES/PV/电价模型事实。因此默认不直接修改 `references.bib` 或 `thesis_draft.tex`。如果后续把本文献结论写进论文正文，需要再补 citation key 并同步检查 LaTeX 引用。

## 不确定点

- 无明显抽取告警；仍需人工核对公式排版和表格含义。
- 标题、作者、DOI 由 PDF 文本启发式抽取；正式引用前应人工核对出版社页或 BibTeX。
- 公式和算法片段见 `core_algorithm.md`，其中换行和上下标可能受 PDF 排版影响。
