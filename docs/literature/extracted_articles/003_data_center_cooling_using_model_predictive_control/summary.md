# 文献简述

## 基本信息

- 编号：003
- 标题：Data center cooling using model-predictive control
- 作者：Nevena Lazic; Tyler Lu; Craig Boutilier; Moonkyung Ryu; Eehern Wong; Binz Roy; Greg Imwalle
- 年份：2018
- DOI/source：unknown
- 文献类别：core_references
- PDF 页数：10
- 可抽取文本字符数：35233
- 复制的 PDF：`2018_Lazic_Data_center_cooling_using_model_predictive_control.pdf`

## 原始路径与重复项

- `docs\literature\core_references\NeurIPS-2018-data-center-cooling-using-model-predictive-control-Paper.pdf` | sha256 `2ed89618deb9` | core_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> Despite the impressive recent advances in reinforcement learning (RL) algorithms, their deployment to real-world physical systems is often complicated by unexpected events, limited data, and the potential for expensive failures. In this paper, we describe an application of RL “in the wild” to the task of regulating temperatures and airflow inside a large-scale data center (DC). Adopting a data-driven, model- based approach, we demonstrate that an RL agent with little prior knowledge is able to effectively and safely regulate conditions on a server floor after just a few hours of exploration, while improving operational efficiency relative to existing PID controllers.

## 与当前项目主线的关系

与当前主线相关信号：data center, MPC。需回到本项目模型和输入数据验证后才能写成当前模型事实。

## 核心公式/伪代码页线索

p4 model predictive control; p4.1 model structure; p6 control optimization constraints.

补充判断：真实数据中心冷却 MPC/安全部署参考；不含 TES/PV/TOU，但支撑 MPC 论证。

## 可迁移判断

- 可直接迁移：文献中的变量定义、优化目标结构、控制流程、设备调度约束可以作为建模参考。
- 不可直接当作当前模型事实：节能率、设备规模、城市气象、负荷曲线和控制效果必须回到 `Nanjing-DataCenter-TES-EnergyPlus/` 或 `mpc_v2/` 的模型、输入、日志和验证结果复核。

## 论文同步影响

本次只创建文献整理 Markdown 和 PDF 副本，未新增或删除 BibTeX 条目，也未改变当前 EnergyPlus/TES/PV/电价模型事实。因此默认不直接修改 `references.bib` 或 `thesis_draft.tex`。如果后续把本文献结论写进论文正文，需要再补 citation key 并同步检查 LaTeX 引用。

## 不确定点

- 无明显抽取告警；仍需人工核对公式排版和表格含义。
- 标题、作者、DOI 由 PDF 文本启发式抽取；正式引用前应人工核对出版社页或 BibTeX。
- 公式和算法片段见 `core_algorithm.md`，其中换行和上下标可能受 PDF 排版影响。
