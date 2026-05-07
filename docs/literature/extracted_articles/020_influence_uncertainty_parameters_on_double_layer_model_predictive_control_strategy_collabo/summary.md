# 文献简述

## 基本信息

- 编号：020
- 标题：The influence of uncertainty parameters on the double-layer model predictive control strategy for the collaborative operation of chiller and cold storage tank in data center
- 作者：Yiqun Zhu a, Quan Zhang a,*, Gongsheng Huang b, Jiaqiang Wang c , Sikai Zou d
- 年份：2024
- DOI/source：10.1016/j.energy.2024.133866
- 文献类别：other_references
- PDF 页数：16
- 可抽取文本字符数：60685
- 复制的 PDF：`2024_Zhu_The_influence_of_uncertainty_parameters_on_the_double_layer_model_predic.pdf`

## 原始路径与重复项

- `docs\literature\other_references\1-s2.0-S0360544224036442-main.pdf` | sha256 `1f9da36b7016` | other_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> Handling editor: X Zhao The inefficient operating states and parameter settings are important factors affecting the high energy con­ sumption of data center cooling systems. The double-layer model predictive control (DMPC) strategy is devel­ Keywords: oped to optimize the operating states and parameter settings of cooling system. The theoretical performance of Data center DMPC strategy is impressive. Meanwhile, the control performance is deeply affected by parameter uncertainties Free cooling in the model, sensors, and actuator in practical application. Therefore, the influence of uncertain parameters on Cold storage performance of DMPC strategy is quantified, and the key uncertain parameters (including the wet-bulb tem­ Double-layer model predictive control (DMPC) Uncertainty parameters perature, approaching temperature of cooling tower, cooling capacity of water tank, COP, water flow rates of cooling water pump and chilled water pump) are identified. The results show that the DMPC strategy can prevent the chillers from operating at very low loads and reduce the 24-h PUE by more than 0.01. However, compared to traditional control strategy, the DMPC strategy is more sensitive to uncertain parameters. Parameter uncertainty leads to 70 % mode prediction error rate of DMPC strategy. In mechanical cooling mode, the DMPC strategy is more sensitive to COP than approaching temperature...

## 与当前项目主线的关系

与当前主线相关信号：data center, TES/storage, MPC, MILP, PV。需回到本项目模型和输入数据验证后才能写成当前模型事实。

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
