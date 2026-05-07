# 文献简述

## 基本信息

- 编号：010
- 标题：Buildings-to-grid with generalized energy storage: A multi-agent decomposed deep reinforcement learning approach for delayed rewards
- 作者：Jiahui Jin a , Guoqiang Sun a , Sheng Chen a,∗ iD, Yaping Li b , Hong Zhu c , Wenbo Mao b , Wenlu Ji c
- 年份：2026
- DOI/source：10.1016/j.apenergy.2025.127181
- 文献类别：other_references
- PDF 页数：11
- 可抽取文本字符数：54746
- 复制的 PDF：`2026_Jin_Buildings_to_grid_with_generalized_energy_storage_A_multi_agent_decompos.pdf`

## 原始路径与重复项

- `docs\literature\other_references\1-s2.0-S0306261925019117-main.pdf` | sha256 `5271b1f60392` | other_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> unknown

## 与当前项目主线的关系

与当前主线相关信号：TES/storage, MPC, EnergyPlus, PV, tariff/TOU。需回到本项目模型和输入数据验证后才能写成当前模型事实。

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
