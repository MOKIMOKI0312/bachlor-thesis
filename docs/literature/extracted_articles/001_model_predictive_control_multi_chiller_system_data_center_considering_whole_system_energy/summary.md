# 文献简述

## 基本信息

- 编号：001
- 标题：A model predictive control for a multi-chiller system in data center considering whole system energy conservation
- 作者：Jing Zhao; Ziyi Chen; Haonan Li; Dehan Liu
- 年份：2024
- DOI/source：10.1016/j.enbuild.2024.114919
- 文献类别：core_references
- PDF 页数：21
- 可抽取文本字符数：81733
- 复制的 PDF：`2024_Zhao_A_model_predictive_control_for_a_multi_chiller_system_in_data_center_con.pdf`

## 原始路径与重复项

- `docs\literature\core_references\1-s2.0-S0378778824010351-main.pdf` | sha256 `5f07d0c7930a` | core_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> Keywords: To meet the thermal environment requirements for the continuous and stable operation of information tech- Data center energy-saving nology (IT) equipment in data rooms, the cooling system needs to operate all day, which has become the second Long and short-term memory largest energy-consuming system in data centers. The absence of an effective operational control strategy in the Multi-chiller intelligent control data center cooling process results in high energy consumption and poor power usage effectiveness (PUE) of the Model predictive control data center. This study proposes a model predictive control (MPC) strategy considering the constraint of whole system energy conservation for a multi-chiller system in a data center. This strategy aims to maintain the data center server room temperature stable in the IT equipment working environment, and at the same time, the energy consumption of the cooling system is significantly reduced, thus the PUE of the data center is lowered. The long and short-term memory (LSTM) neural network prediction models for data center cooling load and server room temperature were constructed using the mechanism-coupled data law method. The MPC algorithmic structure coupled with cooling load prediction model and server room temperature prediction model. It takes the balance between supply and demand of cooling capacity as a constraint. The co...

## 与当前项目主线的关系

与当前主线相关信号：data center, TES/storage, MPC, PV, tariff/TOU。需回到本项目模型和输入数据验证后才能写成当前模型事实。

## 核心公式/伪代码页线索

p2-p4 method route; p4-p7 LSTM prediction; p14-p17 control effect; keywords: MPC, PSO, constraint, TRNSYS.

补充判断：支撑数据中心多冷机 MPC、温度约束和系统节能；不直接覆盖 PV/TOU/TES。

## 可迁移判断

- 可直接迁移：文献中的变量定义、优化目标结构、控制流程、设备调度约束可以作为建模参考。
- 不可直接当作当前模型事实：节能率、设备规模、城市气象、负荷曲线和控制效果必须回到 `Nanjing-DataCenter-TES-EnergyPlus/` 或 `mpc_v2/` 的模型、输入、日志和验证结果复核。

## 论文同步影响

本次只创建文献整理 Markdown 和 PDF 副本，未新增或删除 BibTeX 条目，也未改变当前 EnergyPlus/TES/PV/电价模型事实。因此默认不直接修改 `references.bib` 或 `thesis_draft.tex`。如果后续把本文献结论写进论文正文，需要再补 citation key 并同步检查 LaTeX 引用。

## 不确定点

- 无明显抽取告警；仍需人工核对公式排版和表格含义。
- 标题、作者、DOI 由 PDF 文本启发式抽取；正式引用前应人工核对出版社页或 BibTeX。
- 公式和算法片段见 `core_algorithm.md`，其中换行和上下标可能受 PDF 排版影响。
