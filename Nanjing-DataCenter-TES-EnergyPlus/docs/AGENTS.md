# Model Documentation Rules

本目录保存当前 EnergyPlus 模型包的说明文档。文档必须服务于一个目标：让读者能审计当前模型、输入、运行方式、关键参数和验证状态。

## 当前文档分工

- `model_manifest.md`：文件清单、来源映射、模型事实和已移除范围。
- `nanjing_tes_pv_price_energyplus_model.md`：当前南京案例的模型说明、冷却系统逻辑、冷却塔修复、外部输入和验证结果。
- `physical_model_parameters.md`：预留的物理模型参数文档。如果尚不存在，下一次修改或系统性审计 epJSON 时必须创建。

## 文档边界

- 本目录只写当前 EnergyPlus 模型包相关内容。
- 不把旧 RL、Sinergym、MPC v2、W2/W3 实验过程材料写入这里，除非作为历史来源说明，并明确标注为历史背景。
- 不把 `out/` 中的临时运行结果写成长期事实，除非注明运行目录、日期、命令和对应模型版本。
- 不编造 PVGIS 参数、天气来源、设备参数或验证结果；未知信息写 `unknown` 或 `待确认`。
- 电价和 PV 必须写清楚是外部输入，不是 epJSON 内生物理对象。

## 物理模型参数文档要求

`physical_model_parameters.md` 用于记录 EnergyPlus 物理模型的详细参数。至少应覆盖：

- simulation timestep 和 run period
- weather file
- main zone 与 IT load
- chilled-water loop
- condenser-water loop
- chiller
- cooling tower
- TES tank
- pumps
- setpoint managers
- EMS sensors / actuators / programs
- output variables
- known warnings 和验证状态
- 修改历史

记录参数时应尽量包含：

- EnergyPlus object type
- object name
- field name
- value
- unit
- source
- last verified date

## 同步更新触发条件

以下内容变化时，必须检查并更新相关说明文档：

- `../model/Nanjing_DataCenter_TES.epJSON`
- `../run_energyplus_nanjing.ps1`
- `../inputs/` 中的电价、PV、PVGIS 数据或 schema
- `../weather/` 中的 EPW 文件
- EnergyPlus warning / severe error 状态
- timestep、TES、冷机、冷却塔、水泵、plant loop、setpoint manager、EMS sensor/actuator、output variable
- 默认案例不再是南京，或新增多地点场景

## 写作规则

- 文档必须区分：
  - 已由模型文件、运行日志或输出验证的事实
  - 基于证据的推断
  - 尚未验证的假设
- 如果参数来自 epJSON，优先写明对象类型、对象名、字段名和单位。
- 如果参数来自外部 CSV，优先写明文件名、列名、单位和时间分辨率。
- 如果参数来自 PVGIS，必须记录 PVGIS 参数；如果参数未知，明确写 `unknown`。
- 修改冷却塔、冷机、TES 或 plant loop 文档时，应同时说明对 warning/severe error 的影响。
- 文档表述要避免把当前南京默认案例写成永久唯一场景；后续允许扩展多地点实验。

## Agent 分工要求

- 涉及本目录文档新增、重写、参数同步或验证结果更新时，默认由显式 GPT-5.5 subagent 执行。
- 主 agent 默认只做只读核对、事实校验、diff 审查和最终验收。
- 文档修改 subagent 必须返回：
  - 修改文件清单
  - 主要新增/更新内容
  - 信息来源
  - 未确认项
  - 是否与当前模型、runner、输入文件一致
  - 是否需要创建或更新 `physical_model_parameters.md`
  - 是否需要同步更新论文 LaTeX

## 验收要求

文档更新后至少检查：

- 引用的文件路径是否存在。
- 引用的模型对象名是否能在 epJSON 中找到。
- 引用的输入文件名是否能在 `../inputs/` 或 `../weather/` 中找到。
- 当前验证状态是否和最新 `eplusout.err` 或 runner 输出一致。
- 没有把历史计划或临时输出误写成当前模型事实。
