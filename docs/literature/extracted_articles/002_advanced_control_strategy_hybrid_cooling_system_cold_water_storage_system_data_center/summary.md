# 文献简述

## 基本信息

- 编号：002
- 标题：An advanced control strategy of hybrid cooling system with cold water storage system in data center
- 作者：Yiqun Zhu; Quan Zhang; Liping Zeng; Jiaqiang Wang; Sikai Zou
- 年份：2024
- DOI/source：10.1016/j.energy.2024.130304
- 文献类别：core_references
- PDF 页数：15
- 可抽取文本字符数：56286
- 复制的 PDF：`2024_Zhu_An_advanced_control_strategy_of_hybrid_cooling_system_with_cold_water_st.pdf`

## 原始路径与重复项

- `docs\literature\core_references\1-s2.0-S0360544224000756-main (2).pdf` | sha256 `139084859b76` | core_references
- `docs\literature\other_references\1-s2.0-S0360544224000756-main (1).pdf` | sha256 `15e0cb194719` | other_references
- `docs\literature\other_references\1-s2.0-S0360544224000756-main.pdf` | sha256 `987c73c30c32` | other_references
- `docs\literature\other_references\Zhu 等 - 2024 - An advanced control strategy of hybrid cooling system with cold water storage system in data center.pdf` | sha256 `86ce4c2c012f` | other_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> Handling Editor: X Zhao The inefficient operation of cooling equipment is a significant impact factor to the high energy consumption of cooling system in data center. This study proposes an advanced model predictive control (MPC) strategy for a Keywords: hybrid cooling with water storage system to improve energy efficiency and reduce the accumulation of cold Data center storage losses. Mixed integer linear programming (MILP) in MPC strategy is used to optimize the operating Free cooling parameters under free cooling, hybrid cooling, and mechanical cooling modes, further solving the problem of Cold storage tank volume precise optimization for different modes. Taking Guangzhou city as an example, the equipment scheduling and Model predictive control (MPC) Mixed integer linear programming (MILP) the appropriate volume of cold water storage tank for MPC strategy are analyzed. The results indicate that, the emergency cold water storage tank 500 m3 only supports the efficient operation of cooling system under the maximum 60 % IT load rate, meanwhile, the optimal tank volume 1400 m3 could meet the 60–100 % IT load rate. Compared to Baseline strategy, the biggest reduction of annual energy consumption using MPC strategy would be attained by 12.19 % under free cooling mode, by 4.04 % under hybrid cooling mode, and by 22.15 % under mechanical cooling conditions at the 55 % IT load rate. ...

## 与当前项目主线的关系

与当前主线相关信号：data center, TES/storage, MPC, MILP, tariff/TOU。需回到本项目模型和输入数据验证后才能写成当前模型事实。

## 核心公式/伪代码页线索

p3 MPC strategy; p6 objective function/MILP; p7 constraint conditions; p10-p14 case and results.

补充判断：核心直连数据中心冷水蓄冷、MPC、MILP 和冷却模式调度；Zhu 2024 在本地有多份副本，已按 DOI 合并。

## 可迁移判断

- 可直接迁移：文献中的变量定义、优化目标结构、控制流程、设备调度约束可以作为建模参考。
- 不可直接当作当前模型事实：节能率、设备规模、城市气象、负荷曲线和控制效果必须回到 `Nanjing-DataCenter-TES-EnergyPlus/` 或 `mpc_v2/` 的模型、输入、日志和验证结果复核。

## 论文同步影响

本次只创建文献整理 Markdown 和 PDF 副本，未新增或删除 BibTeX 条目，也未改变当前 EnergyPlus/TES/PV/电价模型事实。因此默认不直接修改 `references.bib` 或 `thesis_draft.tex`。如果后续把本文献结论写进论文正文，需要再补 citation key 并同步检查 LaTeX 引用。

## 不确定点

- 无明显抽取告警；仍需人工核对公式排版和表格含义。
- 标题、作者、DOI 由 PDF 文本启发式抽取；正式引用前应人工核对出版社页或 BibTeX。
- 公式和算法片段见 `core_algorithm.md`，其中换行和上下标可能受 PDF 排版影响。
