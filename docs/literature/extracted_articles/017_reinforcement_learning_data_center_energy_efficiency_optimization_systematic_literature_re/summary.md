# 文献简述

## 基本信息

- 编号：017
- 标题：Reinforcement learning for data center energy efficiency optimization: A systematic literature review and research roadmap
- 作者：Hussain Kahil a,∗ , Shiva Sharma b , Petri Välisuo a , Mohammed Elmusrati a
- 年份：2025
- DOI/source：10.1016/j.apenergy.2025.125734
- 文献类别：other_references
- PDF 页数：27
- 可抽取文本字符数：173853
- 复制的 PDF：`2025_Kahil_Reinforcement_learning_for_data_center_energy_efficiency_optimization_A.pdf`

## 原始路径与重复项

- `docs\literature\other_references\1-s2.0-S0306261925004647-main (1).pdf` | sha256 `43275c6131c2` | other_references
- `docs\literature\other_references\1-s2.0-S0306261925004647-main.pdf` | sha256 `0be7508a1eb1` | other_references

## 摘要依据

以下内容来自 PDF 可抽取文本的 Abstract/首页区域，可能包含排版噪声：

> s were screened to eliminate • RQ2: Which RL/DRL algorithms are utilized for energy optimization irrelevant studies and duplicates. in data centers? 3. Eligibility: Full-text articles were reviewed against the inclusion • RQ3: What experimental setups and dataset sources (e.g., real-world and exclusion criteria. deployments or simulations) are commonly used? 4. Inclusion: The final set of studies that met all quality assessment • RQ4: What specific research problems are addressed using RL/DRL criteria was selected for detailed analysis. algorithms? • RQ5: What are the primary objectives addressed in the identified studies? A PRISMA flow diagram (Fig. 6) illustrates the selection process, • RQ6: What benchmarks are used to evaluate the achieved results in documenting the number of studies identified, screened, excluded, and terms of energy efficiency? included. Fig. 5. Search strategy to get relevant papers. 7 H. Kahil, S. Sharma, P. Välisuo et al. Applied Energy 389 (2025) 125734 Search phase Selection phase Second search and selection IEEE 25 Exc 12 Xplore new 18 Inc 59 Additional Inclusion relevant from 100 criteria Scopus references Sum 77 Inc 71 Science 14 Quality Exc Direct Abstract & Exc check 12 keywords 40 Web of 20 Science Inc 111 Finally selected 65 ACM Digital 5 Remove Exc library Total=164 duplicates 53 Fig. 6. Systematic literature review process stages: Removals o...

## 与当前项目主线的关系

与当前主线相关信号：data center, TES/storage, MPC, MILP, EnergyPlus。需回到本项目模型和输入数据验证后才能写成当前模型事实。

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
