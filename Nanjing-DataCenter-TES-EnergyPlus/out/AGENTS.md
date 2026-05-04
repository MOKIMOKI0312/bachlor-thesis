# Local Output Rules

本目录保存本地 EnergyPlus 运行输出、诊断图表、派生 CSV 和临时验证结果。默认不提交 Git，除非是本规则文件或用户明确要求保留的精选结果。

## 基本原则

- 本目录是运行输出区，不是源代码、模型、输入数据或长期文档区。
- 默认所有 EnergyPlus 输出、图表、临时 CSV、SQLite、ESO、ERR、HTML 表格和中间诊断文件都不入库。
- 不在本目录中手工修改模型、输入数据或 runner。
- 不把本目录中的单次输出直接写成论文事实，除非记录了运行命令、模型版本、输入文件、运行日期和输出目录。

## 运行目录命名

每次重要运行应使用独立子目录，避免覆盖：

```text
energyplus_<scenario>_<YYYYMMDD_HHMMSS>/
```

或对已知阶段性验证使用清晰名称：

```text
energyplus_nanjing_final_range3/
energyplus_nanjing_timestep4_validation/
```

目录名应体现：

- 场景或目的
- 关键模型变更
- 时间戳或唯一标识

## 必须保留的最小证据

如果某次运行用于论文、答辩或模型验收，至少保留：

- `eplusout.err`
- `eplusout.audit`
- `eplusout.sql` 或可复核的 timeseries CSV
- `warning_summary.json` 或 warning 统计
- `plot_summary.json` 或图表生成说明
- 关键图表
- 运行命令或 README/manifest

如果这些文件缺失，则该运行只能视为临时调试输出。

## 论文级输出要求

用于论文或答辩的输出目录必须包含 `RUN_MANIFEST.md` 或 `run_manifest.json`，记录运行命令、Git commit、模型路径、天气路径、输入路径、EnergyPlus 版本和关键结果摘要。

## 清理规则

- 可以清理明显重复、失败、过时或被新结果替代的输出目录。
- 删除前先确认该目录没有被论文、README、manifest、进度文档或提交说明引用。
- 不批量删除输出目录，除非用户明确要求。
- 清理时优先保留最近一次成功验证目录和任何被文档引用的目录。
- 大文件如 `.eso`、`.sql`、`.mtr` 可按需要清理，但如果该运行用于论文，应保留至少一种可复核数据源。

## 与论文和文档同步

当某次输出被用于论文或模型说明时，必须同步记录到：

```text
../docs/
../../docs/project_management/毕业设计论文/
```

记录内容至少包括：

- 运行目录
- 运行日期
- EnergyPlus 版本
- 模型文件
- 天气文件
- 输入文件
- 关键 warning/severe error 统计
- 关键图表或表格来源

## Agent 分工要求

- 涉及输出整理、结果筛选、图表生成、论文结果引用或清理输出目录时，默认由显式 GPT-5.5 subagent 执行。
- 主 agent 默认只做只读核对、结果验收、引用关系检查和最终汇报。
- 输出处理 subagent 必须返回：
  - 处理目录清单
  - 保留文件清单
  - 删除或忽略内容说明
  - 是否有论文/文档引用
  - 是否需要同步更新 `../docs/` 或论文 LaTeX
