# 文献简述

## 基本信息

- 编号：012
- 标题：Exploring the Preference for Discrete over Continuous Reinforcement Learning in Energy Storage Arbitrage
- 作者：Jaeik Jeong * , Tai-Yeon Ku and Wan-Ki Park
- 年份：2024
- DOI/source：10.3390/en17235876
- 文献类别：other_references
- PDF 页数：17
- 可抽取文本字符数：59248
- 复制的 PDF：`2024_Jeong_Exploring_the_Preference_for_Discrete_over_Continuous_Reinforcement_Lear.pdf`

## 原始路径与重复项

- `docs\literature\other_references\energies-17-05876 (1).pdf` | sha256 `226a6130c7d9` | other_references
- `docs\literature\other_references\energies-17-05876.pdf` | sha256 `226a6130c7d9` | other_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> : In recent research addressing energy arbitrage with energy storage systems (ESSs), dis- crete reinforcement learning (RL) has often been employed, while the underlying reasons for this preference have not been explicitly clarified. This paper aims to elucidate why discrete RL tends to be more suitable than continuous RL for energy arbitrage problems. When using continuous RL, the charging and discharging actions determined by the agent often exceed the physical limits of the ESS, necessitating clipping to the boundary values. This introduces a critical issue where the learned actions become stuck at the state of charge (SoC) boundaries, hindering effective learning. Although recent advancements in constrained RL offer potential solutions, their application often results in overly conservative policies, preventing the full utilization of ESS capabilities. In contrast, discrete RL, while lacking in granular control, successfully avoids these two key challenges, as demonstrated by simulation results showing superior performance. Additionally, it was found that, due to its characteristics, discrete RL more easily drives the ESS towards fully charged or fully discharged states, thereby increasing the utilization of the storage system. Our findings provide a solid justification for the prevalent use of discrete RL in recent studies involving energy arbitrage with ESSs, offering new...

## 与当前项目主线的关系

与当前主线相关信号：TES/storage, MPC, MILP, PV, tariff/TOU。需回到本项目模型和输入数据验证后才能写成当前模型事实。

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
