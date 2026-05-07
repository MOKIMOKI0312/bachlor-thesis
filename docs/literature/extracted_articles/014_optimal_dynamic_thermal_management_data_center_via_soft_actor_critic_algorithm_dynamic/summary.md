# 文献简述

## 基本信息

- 编号：014
- 标题：Optimal dynamic thermal management for data center via soft actor-critic algorithm with dynamic control interval and combined-value state space
- 作者：Yuxiang Guo a , Shengli Qu a , Chuang Wang a, * , Ziwen Xing a , Kaiwen Duan b
- 年份：2024
- DOI/source：10.1016/j.apenergy.2024.123815
- 文献类别：other_references
- PDF 页数：25
- 可抽取文本字符数：95372
- 复制的 PDF：`2024_Guo_Optimal_dynamic_thermal_management_for_data_center_via_soft_actor_critic.pdf`

## 原始路径与重复项

- `docs\literature\other_references\1-s2.0-S030626192401198X-main.pdf` | sha256 `9b81cca05850` | other_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> Keywords: As the scale of data centers continues to expand, the environmental impact of their energy consumption has Data centers become a major concern, highlighting the increasing importance of thermal management in data centers. In this Thermal management study, we address these challenges by adopting the Soft Actor-Critic (SAC) algorithm of reinforcement learning to Reinforcement learning enhance energy management efficiency. To further improve adaptability to environmental changes and provide a Soft actor-critic Dynamic control interval more comprehensive representation of the current state information, we introduce the Dynamic Control Interval Combined-value state space SAC (DCI-SAC) structure and combined-value state space. We conducted two groups of simulation experiments to evaluate the performance of SAC and its variants. The first group of experiments showed that in a simulated data center model, SAC achieved energy savings of 32.23%, 9.86%, 10.77%, 6.95%, and 1.83% compared to PID, MPC, DQN, TRPO, and PPO, respectively, demonstrating SAC’s superior algorithmic performance. The second group of experiments shows that DCI-SAC with a combined-value state space achieves up to a 6.25% reduction in energy consumption compared to SAC with the same state space. Additionally, it achieves up to a 9.48% reduction in energy consumption to SAC with a final-value state space. Thes...

## 与当前项目主线的关系

与当前主线相关信号：data center, TES/storage, MPC, EnergyPlus。需回到本项目模型和输入数据验证后才能写成当前模型事实。

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
