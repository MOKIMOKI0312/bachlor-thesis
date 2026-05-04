# EnergyPlus Model Rules

本目录只保存当前 EnergyPlus 主线模型。

## 当前模型

- 默认模型文件：`Nanjing_DataCenter_TES.epJSON`
- 该模型应保持为当前唯一主线 epJSON。
- 不新增旧 baseline、旧 evaluation、旧 DRL、旧 W2/W3 模型副本，除非用户明确要求。

## Agent 分工要求

- 涉及 epJSON 修改时，默认由显式 GPT-5.5 subagent 执行。
- 主 agent 默认不直接编辑 epJSON，只做目标澄清、diff 核对、日志核对和最终验收。
- 修改后优先再使用显式 GPT-5.5 审查 subagent 检查 diff。
- 审查重点：
  - EnergyPlus 对象名和字段名是否正确
  - 单位是否一致
  - plant loop、TES、EMS、冷却塔、冷机、水泵之间是否保持连通
  - 是否引入新的 Severe Error 或核心 warning
  - 说明文档和论文 LaTeX 是否需要同步更新

## 修改边界

- 修改前先确认对象名、字段名、单位和当前值，不要用猜测替换大段 epJSON。
- 大范围格式化 epJSON 默认禁止，避免 diff 失去审查价值。
- 不手工删除模型对象，除非已经确认该对象没有被 branch、loop、node、schedule、EMS 或 output 引用。
- 不把电价/PV 直接硬编码进 epJSON。当前电价/PV 是外部输入，由 runner 或后续控制器读取。
- 不把本目录当作实验模型仓库；实验副本如确有必要，应放入明确命名的临时目录且默认不提交。

## 物理模型说明文档

- agent 必须自动维护和更新 `../docs/physical_model_parameters.md`，用于记录 EnergyPlus 物理模型的详细参数、对象名、关键字段、单位、来源和修改历史。
- 每次修改 epJSON 中的 timestep、TES、冷机、冷却塔、水泵、plant loop、setpoint manager、EMS actuator/sensor、output variable 或关键 schedule 时，都必须同步更新该文档。
- 如果某次修改不影响物理模型参数，也应在最终回复中明确说明无需更新该文档的原因。

## 必须保持的关键口径

- `Timestep.number_of_timesteps_per_hour = 4`，即 15 分钟。
- 模型应包含 TES 物理对象和 EMS 观测/控制接口。
- 模型应包含冷却系统的完整 plant loop，包括冷冻水侧、冷凝水侧、冷机、冷却塔、水泵和相关 setpoint manager。
- 当前冷却塔核心 warning 已被修复，后续修改不能让以下 warning 回归：
  - `Cooling tower air flow rate ratio calculation failed`
  - `Tower approach temperature is outside model boundaries`
  - `Tower range temperature is outside model boundaries`

## 修改后验证

修改 epJSON 后，默认运行：

```powershell
& ..\run_energyplus_nanjing.ps1 -EnergyPlusExe "<path-to-energyplus.exe>"
```

最低验收：

- EnergyPlus completed successfully。
- 0 Severe Errors。
- `eplusout.err` 中无冷却塔核心 warning 回归。
- 如 warning 数量变化，说明新增/减少的 warning 类型和原因。
