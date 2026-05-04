# External Input Rules

本目录保存当前 EnergyPlus 模型包使用的外部时序输入数据。

## 当前输入文件

- `Jiangsu_TOU_2025_hourly.csv`：当前默认案例使用的江苏/南京 TOU 电价输入。
- `CHN_Nanjing_PV_6MWp_hourly.csv`：当前默认案例使用的 PV 小时级预期出力曲线。
- `pvgis/`：PVGIS 原始导出、参数说明或后续派生数据的预留目录。

## 数据口径

- 电价和 PV 是 EnergyPlus 外部输入，不是 epJSON 内生物理对象。
- 电价是外生 TOU 价格，不是优化决策变量。
- PV 当前作为外部预期出力/发电曲线，用于后续控制、成本核算或自消纳分析；不要假设 EnergyPlus 本体会自动消纳 PV。
- PV 预期出力默认由天气数据输入到 PVGIS 生成。新增或替换 PV 文件时，必须记录 PVGIS 参数、天气数据库、装机容量、倾角/方位角、系统损失等关键假设。
- 默认时间分辨率为小时级；如 runner 或控制器需要 15 分钟输入，应由脚本显式重采样，并记录方法。

## Schema 要求

电价 CSV 必须至少包含：

```text
timestamp,price_usd_per_mwh
```

PV CSV 必须至少包含：

```text
timestamp,power_kw
```

默认要求：

- 每个年度小时级文件通常应包含 8760 条数据行，不含表头则为错误。
- `timestamp` 应可被常规 CSV/时间序列工具解析。
- `price_usd_per_mwh` 单位为 USD/MWh。
- `power_kw` 单位为 kW，表示该时间步平均 PV 功率。
- 非年度、闰年、短期周实验或多地点场景可以使用其它行数，但必须在文件名或配套说明中标清楚。

## PVGIS 数据目录

- `pvgis/` 中应保存 PVGIS 原始下载文件、参数说明或后续派生数据。
- PVGIS 数据说明至少记录：
  - location / latitude / longitude
  - weather database
  - installed peak power
  - system loss
  - slope
  - azimuth
  - output time resolution
  - download/generation date
- 如果 PVGIS 参数未知，明确写 `unknown`，不要猜测。

## 多地点/多场景规则

- 本目录允许后续保存不同地点、不同电价市场、不同 PV 场站或不同年份的外部输入。
- 新增场景数据时，文件名应包含地点、数据类型、容量或年份等关键信息，避免覆盖默认案例。
- 多地点实验必须有一份说明文件记录每个场景对应的：
  - 天气文件
  - 电价文件
  - PV 文件
  - 时间范围
  - 单位
  - 生成或下载来源
- 不同地点的数据不能混用；如果 weather、price、PV 的地点或年份不一致，必须在说明里明确这是实验假设还是数据缺口。

## 修改规则

- 修改或替换输入文件时，必须说明来源、年份、单位、时区/时间口径和是否经过重采样。
- 不直接覆盖原始数据，除非用户明确要求；优先新增带来源或日期的文件。
- 不把临时生成的中间数据长期留在本目录；临时输出应进入 `out/` 或明确的运行输出目录。

## Agent 分工要求

- 涉及 CSV 数据清洗、替换、重采样、schema 调整或多地点场景扩展时，默认由显式 GPT-5.5 subagent 执行。
- 主 agent 默认只做只读核对、数据摘要、diff 核查和最终验收。
- 修改后必须返回：
  - 修改文件清单
  - 数据来源和单位说明
  - 行数和列名检查结果
  - 地点、年份、天气/价格/PV 是否匹配
  - 是否仍满足 runner 或后续控制器的输入校验
  - 是否需要同步更新说明文档或论文 LaTeX
