# Changelog

本文件用于项目版本管理，记录每个可复现版本的代码范围、提交、验证结果、结果目录、论文同步状态和已知限制。

## 版本规则

- 代码版本使用 `v主版本.次版本.修订版本-主题`。
- 结果目录使用 `results/主题_YYYYMMDD/`。
- 每个版本条目必须记录：
  - 日期
  - Git commit
  - 分支或合并状态
  - 主要变更
  - 验证命令与结果
  - 运行结果位置
  - 运行结果简述
  - 是否影响论文
  - 已知限制

## v0.7.0-phase3-real-epw-pvgis-sizing-matrix - 2026-05-13

### Git

- Commit: `TBD-after-commit`。
- 工作区：`C:\Users\18430\Desktop\毕业设计代码`。
- 分支：`codex/phase3-mpc-ep-real-weather-pvgis`。
- 分支或合并状态：准备推送并合并到 `master`。

### Scope

执行 Phase 3 PV--TES 技术容量推荐任务，将原先缺失的地点 profile 改为真实三地点输入：南京、广州、北京 EPW 对应的 EnergyPlus 年度 no-control 负荷/天气边界，PVGIS v5.3 20 MWp 光伏曲线，以及江苏 2025 TOU 电价。完成 `3 locations × 5 PV × 5 TES × 2 CP uplift = 150` 个全年矩阵场景，并生成审计、图表和推荐容量文档。

### Code, Data, and Docs Changes

- 新增 `mpc_v2/scripts/prepare_phase3_real_inputs.py`，可复现生成三地点 EnergyPlus-derived load/weather profile、下载/标准化 PVGIS 原始 JSON 与 20 MWp 本地时间 PV CSV，并写入输入 manifest。
- 更新 `mpc_v2/config/phase3_locations.yaml`，指向真实 EPW、EnergyPlus baseline、PVGIS 20 MWp 曲线和江苏 TOU 电价。
- 更新 `mpc_v2/scripts/run_phase3_pv_tes_matrix.py`，支持 `base_facility_kw`、`chiller_cooling_kw`、湿球温度和 zone temperature 等 EnergyPlus-derived profile 字段，并加入基线峰值保护、峰值高负荷放冷和 72 h terminal SOC 恢复逻辑。
- 更新 `mpc_v2/phase3_sizing/recommendation.py`，对年度峰值削减接近零的 EnergyPlus 边界给出明确推荐说明，避免把近零峰值指标误判为容量结论失败。
- 新增真实输入数据：`data/locations/{nanjing,guangzhou,beijing}/`，`Nanjing-DataCenter-TES-EnergyPlus/inputs/pvgis/raw/`，`Nanjing-DataCenter-TES-EnergyPlus/inputs/pvgis/processed/`。
- 更新 `docs/phase3_pv_tes_sizing_assumptions.md`，记录真实 EPW、PVGIS API 参数、江苏 TOU 电价和 EnergyPlus-derived matrix 边界。
- 更新论文草稿 `docs/project_management/毕业设计论文/thesis_draft.tex`，加入三地点全年 PV--TES 技术容量矩阵、核心结论和边界说明。

### Validation

Commands:

```powershell
python -m mpc_v2.scripts.prepare_phase3_real_inputs --force-download
python -m pytest -q tests/test_phase3_pv_scaling.py tests/test_phase3_tes_scaling.py tests/test_phase3_cp_metrics.py tests/test_phase3_recommendation.py tests/test_phase3_matrix_builder.py
python -m mpc_v2.scripts.run_phase3_pv_tes_matrix --config mpc_v2/config/phase3_pv_tes_sizing.yaml --locations mpc_v2/config/phase3_locations.yaml --location-filter nanjing --output-root results/phase3_pv_tes_sizing/pilot_nanjing_real_ep_pvgis
python -m mpc_v2.scripts.audit_phase3_pv_tes_results --summary results/phase3_pv_tes_sizing/pilot_nanjing_real_ep_pvgis/summary/phase3_summary.csv --output results/phase3_pv_tes_sizing/pilot_nanjing_real_ep_pvgis/summary/audit_report.md
python -m mpc_v2.scripts.run_phase3_pv_tes_matrix --config mpc_v2/config/phase3_pv_tes_sizing_full_year.yaml --locations mpc_v2/config/phase3_locations.yaml --output-root results/phase3_pv_tes_sizing/full_matrix_real_ep_pvgis --parallel 4
python -m mpc_v2.scripts.audit_phase3_pv_tes_results --summary results/phase3_pv_tes_sizing/full_matrix_real_ep_pvgis/summary/phase3_summary.csv --output results/phase3_pv_tes_sizing/full_matrix_real_ep_pvgis/summary/audit_report.md
python -m mpc_v2.scripts.plot_phase3_pv_tes_results --summary results/phase3_pv_tes_sizing/full_matrix_real_ep_pvgis/summary/phase3_summary.csv --output-dir results/phase3_pv_tes_sizing/full_matrix_real_ep_pvgis/figures
```

Result:

```text
pytest Phase 3 tests -> 12 passed
pilot_nanjing_real_ep_pvgis -> 50/50 scenarios completed, audit P0=0
full_matrix_real_ep_pvgis -> 150/150 scenarios completed, audit P0=0, P1=1
figures -> 5 PNG files generated
```

### 运行结果位置

- Pilot results: `results/phase3_pv_tes_sizing/pilot_nanjing_real_ep_pvgis/`
- Full matrix results: `results/phase3_pv_tes_sizing/full_matrix_real_ep_pvgis/`
- Full matrix summary: `results/phase3_pv_tes_sizing/full_matrix_real_ep_pvgis/summary/phase3_summary.csv`
- Recommendations: `results/phase3_pv_tes_sizing/full_matrix_real_ep_pvgis/summary/phase3_capacity_recommendations.csv`
- Audit report: `results/phase3_pv_tes_sizing/full_matrix_real_ep_pvgis/summary/audit_report.md`
- Figures: `results/phase3_pv_tes_sizing/full_matrix_real_ep_pvgis/figures/`
- Generated result docs: `results/phase3_pv_tes_sizing/full_matrix_real_ep_pvgis/docs/`

### 运行结果简述

| Location | Recommended PV MWp | Recommended TES MWh_th | Max CP suppression | Recommended CP suppression | Recommended PV self-consumption | Max peak reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Beijing | 20 | 72 | 0.587 | 0.439 | 0.829 | 0.000 |
| Guangzhou | 20 | 72 | 0.528 | 0.365 | 0.947 | 0.014 |
| Nanjing | 20 | 72 | 0.482 | 0.352 | 0.912 | 0.001 |

结论：在当前 EnergyPlus-derived 边界下，20 MWp PV 与 36--72 MWh_th TES 可作为运行层面的 technical recommended capacity range。72 MWh_th 在三地均更接近最大尖峰抑制效果；但年度绝对峰值削减接近零，说明主收益来自尖峰窗口购电抑制和 PV 自消纳改善，而不是年度峰值迁移。全量审计唯一 P1 为 15 个 `TES=9 MWh_th` 场景出现轻微负 `critical_peak_suppression_ratio`，该现象保留为弱容量/回充惩罚边界，不隐藏。

### Thesis Impact

- 已更新 `docs/project_management/毕业设计论文/thesis_draft.tex`。
- 未更新 `docs/project_management/毕业设计论文/references.bib`。
- 原因：本次新增真实 EPW/PVGIS/江苏 TOU 下的三地点全年容量矩阵，影响论文实验设计、结果、容量推荐和结论边界；未新增 BibTeX 引用。

### Known Limitations

- Phase 3 主矩阵是 EnergyPlus-derived 技术 sizing：EnergyPlus 提供年度负荷/天气边界，MPC-style TES dispatch 在该边界上回放；不是 150 个容量组合全部 EnergyPlus online co-simulation。
- 三地点仍共用南京数据中心建筑模型和江苏电价，不能解释为城市真实电价经济最优。
- 推荐是 technical recommended capacity range，不是 CAPEX/LCOE/NPV 经济最优。
- 年度峰值削减接近零；如论文需要削峰结论，应引入 demand charge、peak-cap 或更明确的峰值窗口定义。
- `TES=9 MWh_th` 小容量在部分场景中出现负尖峰抑制，说明容量过小可能被回充惩罚抵消。

## v0.6.3-energyplus-mpc-multicity-weather-validation - 2026-05-13

### Git

- Commit: `8a91d6e11dbe214f54f2bcbe04413a1c6ede9c4e`。
- 工作区：`C:\Users\18430\Desktop\epmpc_a484`。
- 分支：`codex/fix-energyplus-mpc-temp-safety`。
- 分支或合并状态：准备推送并合并到 `master`。

### Scope

在 `v0.6.2-energyplus-mpc-temp-safety-fix` 的温度安全修复基础上，新增北京和广州 EPW 天气输入，并运行两地全年 `no_control` 与 `mpc` 在线 EnergyPlus 仿真。每个城市先用自身 EPW 跑 `no_control`，再由该城市 `no_control` monitor 生成 15 分钟 baseline forecast CSV，供同城市 MPC 年度运行使用。

### Code and Data Changes

- 新增天气文件：`Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_BJ_Beijing-Capital.Intl.AP.545110_TMYx.2009-2023.epw`。
- 新增天气文件：`Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_GD_Guangzhou.592870_TMYx.2009-2023.epw`。
- 更新 `Nanjing-DataCenter-TES-EnergyPlus/docs/model_manifest.md`，记录北京/广州 EPW 作为多天气验证输入。
- 新增 `Nanjing-DataCenter-TES-EnergyPlus/docs/multicity_weather_validation_20260513.md`，记录天气来源、运行命令、结果和结论边界。
- 更新 `.gitignore`，忽略 `results/**/_run_logs/` 运行期进程日志。
- 新增北京/广州 no-control baseline forecast：`results/multicity_tempfix_baselines_20260513/`。
- 新增北京/广州年度运行结果：`results/multicity_tempfix_beijing_no_control_20260513/`、`results/multicity_tempfix_beijing_mpc_20260513/`、`results/multicity_tempfix_guangzhou_no_control_20260513/`、`results/multicity_tempfix_guangzhou_mpc_20260513/`。

### Weather Source

- Beijing: Climate.OneBuilding China TMYx 2009-2023，`Beijing-Capital.Intl.AP`，WMO `545110`。
- Guangzhou: Climate.OneBuilding China TMYx 2009-2023，`Guangzhou`，WMO `592870`。
- 下载日期：2026-05-13。

### Validation

Commands:

```powershell
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller no_control --max-steps 35040 --record-start-step 0 --weather Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_BJ_Beijing-Capital.Intl.AP.545110_TMYx.2009-2023.epw --selected-output-root results/multicity_tempfix_beijing_no_control_20260513 --raw-output-dir Nanjing-DataCenter-TES-EnergyPlus/out/multicity_tempfix_beijing_no_control_20260513
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller mpc --max-steps 35040 --record-start-step 0 --weather Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_BJ_Beijing-Capital.Intl.AP.545110_TMYx.2009-2023.epw --baseline-timeseries results/multicity_tempfix_baselines_20260513/beijing_no_control_timeseries_15min.csv --selected-output-root results/multicity_tempfix_beijing_mpc_20260513 --raw-output-dir Nanjing-DataCenter-TES-EnergyPlus/out/multicity_tempfix_beijing_mpc_20260513
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller no_control --max-steps 35040 --record-start-step 0 --weather Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_GD_Guangzhou.592870_TMYx.2009-2023.epw --selected-output-root results/multicity_tempfix_guangzhou_no_control_20260513 --raw-output-dir Nanjing-DataCenter-TES-EnergyPlus/out/multicity_tempfix_guangzhou_no_control_20260513
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller mpc --max-steps 35040 --record-start-step 0 --weather Nanjing-DataCenter-TES-EnergyPlus/weather/CHN_GD_Guangzhou.592870_TMYx.2009-2023.epw --baseline-timeseries results/multicity_tempfix_baselines_20260513/guangzhou_no_control_timeseries_15min.csv --selected-output-root results/multicity_tempfix_guangzhou_mpc_20260513 --raw-output-dir Nanjing-DataCenter-TES-EnergyPlus/out/multicity_tempfix_guangzhou_mpc_20260513
```

Result:

```text
Beijing no_control -> completed, 35040 rows, exit_code=0, severe_errors=0
Beijing mpc -> completed, 35040 rows, exit_code=0, fallback_count=0, severe_errors=0
Guangzhou no_control -> completed, 35040 rows, exit_code=0, severe_errors=0
Guangzhou mpc -> completed, 35040 rows, exit_code=0, fallback_count=0, severe_errors=0
```

### 运行结果位置

- Beijing no-control selected output: `results/multicity_tempfix_beijing_no_control_20260513/no_control/`
- Beijing MPC selected output: `results/multicity_tempfix_beijing_mpc_20260513/mpc/`
- Guangzhou no-control selected output: `results/multicity_tempfix_guangzhou_no_control_20260513/no_control/`
- Guangzhou MPC selected output: `results/multicity_tempfix_guangzhou_mpc_20260513/mpc/`
- City-specific MPC baseline forecasts: `results/multicity_tempfix_baselines_20260513/`
- Raw EnergyPlus outputs: `Nanjing-DataCenter-TES-EnergyPlus/out/multicity_tempfix_*_20260513/`

### 运行结果简述

| City | Controller | Facility GWh | Max zone temp C | >27C ratio | >27C hours | >30C hours | Warnings |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Beijing | no_control | 79.513 | 29.188 | 10.705% | 937.75 | 0.00 | 4 |
| Beijing | mpc | 79.472 | 29.643 | 0.731% | 64.00 | 0.00 | 22 |
| Guangzhou | no_control | 87.923 | 29.152 | 8.405% | 736.25 | 0.00 | 8 |
| Guangzhou | mpc | 88.205 | 29.470 | 1.652% | 144.75 | 0.00 | 25 |

结论：北京和广州 MPC 全年结果均满足当前温度安全验收口径，即全年 `>27C` timestep 比例低于 `5%`，且 `>30C` 为 `0 h`。广州全年能耗高于北京，符合更热湿天气边界下数据中心冷却能耗更高的方向性判断。

### Thesis Impact

- 未更新 `docs/project_management/毕业设计论文/thesis_draft.tex`。
- 未更新 `docs/project_management/毕业设计论文/references.bib`。
- 原因：本次新增的是多天气鲁棒性验证和温度安全证据；虽然可作为后续论文补充实验候选，但当前仍使用南京/江苏 PV 与电价输入，且未形成城市级 PV/电价同源经济结论，因此暂不直接写入论文正文。

### Known Limitations

- 北京/广州运行只切换 EPW，建筑模型仍是南京数据中心模型。
- 外部 PV 和电价仍沿用南京/江苏输入，不支持城市级经济收益结论。
- MPC 温度保护层仍是优化外层 safety guard，不是优化问题内部显式温度约束。
- MPC 运行仍存在 cooling tower warning：北京 `cooling_tower_air_flow_ratio_failed=3`、`tower_range_out_of_range=3`；广州 `cooling_tower_air_flow_ratio_failed=8`、`tower_range_out_of_range=3`。

## v0.6.2-energyplus-mpc-temp-safety-fix - 2026-05-13

### Git

- Base commit: `a484c5a9f6127fa284aea09c48359928f1cc4f22`。
- Commit: `8a91d6e11dbe214f54f2bcbe04413a1c6ede9c4e`。
- 工作区：`C:\Users\18430\Desktop\epmpc_a484`。
- 分支：`codex/fix-energyplus-mpc-temp-safety`。
- 分支或合并状态：本地修复与年度验证，准备随 `v0.6.3` 提交。

### Scope

修复恢复版 `v0.6.0-energyplus-mpc-coupling` 在全年 MPC+EnergyPlus 在线耦合中温度安全失败的问题。修复前年度诊断结果 `zone_temp_max_c=33.42`，`>27°C` 超温比例约 `30.71%`；根因是 EnergyPlus EMS 把 `TES_Set > 0` 解释为 TES 放冷并同时强制关闭 chiller，而 MPC proxy 只把 TES 当作辅助冷源，没有感知 chiller 被切除这一副作用。

### Code Changes

- 修改 `Nanjing-DataCenter-TES-EnergyPlus/model/Nanjing_DataCenter_TES.epJSON`：TES 放冷时不再强制关闭 chiller branch/component，不再把 chiller leaving setpoint 放宽到 `30.0°C`，并恢复 chiller flow 与 bypass availability，避免 `TES_Set > 0` 变成“TES 替代冷机”的控制语义。
- 修改 `Nanjing-DataCenter-TES-EnergyPlus/controller/energyplus_mpc/config/energyplus_mpc_params.yaml`：新增 Runtime API actuator 映射 `CRAH_Fan_Set`、`CRAH_T_Set`、`Chiller_T_Set`。
- 修改 `Nanjing-DataCenter-TES-EnergyPlus/controller/energyplus_mpc/run_energyplus_mpc.py`：新增温度保护层，记录 `tes_set_before_safety`、`safety_override`、`safety_reason`，在接近温度上限时提高 CRAH fan/冷却 setpoint 控制强度、阻止继续充冷、必要时强制 TES 放冷；同时新增 `>27°C` 和 `>30°C` 超温统计。

### Validation

Commands:

```powershell
python -m py_compile Nanjing-DataCenter-TES-EnergyPlus/controller/energyplus_mpc/run_energyplus_mpc.py
python -m json.tool Nanjing-DataCenter-TES-EnergyPlus/model/Nanjing_DataCenter_TES.epJSON
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller mpc --max-steps 4 --record-start-step 0 --selected-output-root results/tempfix_hvac_smoke_20260513 --raw-output-dir Nanjing-DataCenter-TES-EnergyPlus/out/tempfix_hvac_smoke_20260513
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller mpc --max-steps 12000 --record-start-step 0 --selected-output-root results/tempfix_hvac_pilot_12000_20260513 --raw-output-dir Nanjing-DataCenter-TES-EnergyPlus/out/tempfix_hvac_pilot_12000_20260513
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller mpc --max-steps 35040 --record-start-step 0 --selected-output-root results/tempfix_hvac_annual_20260513 --raw-output-dir Nanjing-DataCenter-TES-EnergyPlus/out/tempfix_hvac_annual_20260513
```

Result:

```text
py_compile -> passed
epJSON json.tool -> passed
4-step smoke -> completed, exit_code=0, fallback_count=0, severe_errors=0
12000-step pilot -> completed, >27°C ratio=0.0070, max_temp=28.28°C, >30°C hours=0
Annual MPC+EnergyPlus run -> completed, exit_code=0, 35040 rows, fallback_count=0, severe_errors=0
```

### 运行结果位置

- Selected annual results: `results/tempfix_hvac_annual_20260513/mpc/`
- Raw EnergyPlus output: `Nanjing-DataCenter-TES-EnergyPlus/out/tempfix_hvac_annual_20260513/`
- Run logs: `results/tempfix_hvac_annual_20260513/_run_logs/`

### 运行结果简述

- 时间范围：`2024-01-01 00:00:00` 到 `2024-12-31 23:45:00`。
- 步数：`35040`，15 min timestep，`record_start_step=0`。
- `exit_code=0`，`fallback_count=0`，`TES_Set` echo mismatch count `0`。
- `zone_temp_max_c=28.54`。
- `>27°C`：`386` 个 timestep，`96.5 h`，全年比例 `1.1016%`，满足“超温控制在 5% 以下”的当前验收目标。
- `>30°C`：`0` 个 timestep，`0 h`。
- `safety_override_count=1485`，`crah_fan_assist_count=14208`。
- Warning summary：`severe_errors=0`，`total_warning=19`，`cooling_tower_air_flow_ratio_failed=3`，`tower_range_out_of_range=3`。

### Thesis Impact

- 未更新 `docs/project_management/毕业设计论文/thesis_draft.tex`。
- 未更新 `docs/project_management/毕业设计论文/references.bib`。
- 原因：本次是在恢复版工作区中修复并验证温度安全 bug，结果证明在线耦合链路可通过当前温度安全目标；但尚未形成同版本同口径 `no_control`/`rbc` 年度对照和节能收益结论，且 cooling tower warning 仍需单独排查，因此暂不直接写入论文正文。

### Known Limitations

- 本次只验证 `mpc` 单 case 的温度安全修复，不包含年度 `no_control`/`rbc` 对照，不能据此声明节能率。
- 温度保护层是 MPC 外层安全 guard，不是 MPC 优化问题内部显式温度约束；后续若要论文级控制律，应把温度约束纳入优化模型或明确说明 safety override。
- 年度输出仍有 cooling tower warning：`cooling_tower_air_flow_ratio_failed=3`，`tower_range_out_of_range=3`。

## v0.6.1-energyplus-mpc-annual-diagnostic - 2026-05-13

### Git

- Commit: `a484c5a9f6127fa284aea09c48359928f1cc4f22`。
- 工作区：`C:\Users\18430\Desktop\epmpc_a484`，detached HEAD 恢复 `v0.6.0-energyplus-mpc-coupling` 实现。
- 分支或合并状态：未新建提交；本条目记录本地年度诊断运行。

### Scope

本次不修改 EnergyPlus 模型、controller 代码或输入 CSV，仅在恢复版上运行一次全年 `mpc` + EnergyPlus Runtime API 在线耦合仿真。由于 `out/energyplus_nanjing/timeseries_15min.csv` 未随 `a484c5a9` 入库，本次将当前本机已有同模型基准输出复制到恢复版默认路径，作为 `ForecastProvider` 的 baseline forecast 输入。

### Code Changes

- 无代码变更。
- 新增本地 baseline forecast 文件：`Nanjing-DataCenter-TES-EnergyPlus/out/energyplus_nanjing/timeseries_15min.csv`。
- 新增 smoke 结果：`results/energyplus_mpc_smoke_20260513/`。
- 新增全年 MPC+EnergyPlus 结果：`results/energyplus_mpc_annual_20260513/`。

### Validation

Commands:

```powershell
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller mpc --max-steps 4 --record-start-step 0 --selected-output-root results/energyplus_mpc_smoke_20260513 --raw-output-dir Nanjing-DataCenter-TES-EnergyPlus/out/energyplus_mpc_mpc_smoke_20260513
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller mpc --max-steps 35040 --record-start-step 0 --selected-output-root results/energyplus_mpc_annual_20260513 --raw-output-dir Nanjing-DataCenter-TES-EnergyPlus/out/energyplus_mpc_mpc_annual_20260513
```

Result:

```text
4-step smoke -> completed, exit_code=0, fallback_count=0, severe_errors=0
Annual MPC+EnergyPlus run -> completed, exit_code=0, 35040 rows, fallback_count=0, severe_errors=0
```

### 运行结果位置

- Selected results: `results/energyplus_mpc_annual_20260513/mpc/`
- Raw EnergyPlus output: `Nanjing-DataCenter-TES-EnergyPlus/out/energyplus_mpc_mpc_annual_20260513/`
- Run logs: `results/energyplus_mpc_annual_20260513/_run_logs/`

### 运行结果简述

- 时间范围：`2024-01-01 00:00:00` 到 `2024-12-31 23:45:00`。
- 步数：`35040`，15 min timestep，`record_start_step=0`。
- EnergyPlus elapsed：`1407.09 s`，EnergyPlus log runtime 约 `00hr 23min 27.09sec`。
- `facility_energy_kwh=80551590.40`。
- `pv_adjusted_grid_kwh=78765752.42`。
- `pv_adjusted_cost=3265989.14`。
- `peak_facility_kw=10895.75`，`peak_grid_kw=10895.75`。
- `fallback_count=0`。
- `TES_Set` echo mismatch count `0`。
- `tes_use_response_count=8375`，`tes_source_response_count=24049`。
- `soc_min=0.0`，`soc_max=1.0`，`soc_final=0.9497`。
- `zone_temp_max_c=33.42`，未满足温度安全结论口径。
- Warning summary：`severe_errors=0`，`total_warning=12`，`cooling_tower_air_flow_ratio_failed=2`，`tower_range_out_of_range=3`。

### Thesis Impact

- 未更新 `docs/project_management/毕业设计论文/thesis_draft.tex`。
- 未更新 `docs/project_management/毕业设计论文/references.bib`。
- 原因：本次为恢复版年度在线耦合诊断运行，证明 `a484c5a9` 的 MPC+EnergyPlus runtime chain 可跑完整年；但只包含 `mpc` 单 case，没有同版本同口径 `no_control`/`rbc` 年度对照，且温度安全和 cooling tower warning 仍未通过最终结论口径，因此不应直接作为论文节能收益结论。

### Known Limitations

- 年度结果是 `mpc` 单 case，不包含同年度 no-control baseline 对照，不能计算可信节能率。
- MPC 优化层仍是 Kim-lite proxy，EnergyPlus 是物理响应模型；这不是完整白盒 plant MPC。
- 当前 controller 只直接写 `TES_Set`，不控制 chiller availability、pump mass flow、CRAH fan 或 setpoint。
- `zone_temp_max_c=33.42`，说明全年在线控制仍有温度安全风险。
- `tower_range_out_of_range=3`，年度输出存在冷却塔 warning，需要后续单独排查。

## v0.6.0-energyplus-mpc-coupling - 2026-05-07

### Git

- Commit: `待本次实现提交后回填`。
- 分支：`codex/energyplus-mpc-coupling`
- 基线：从 `codex/kim-lite-hardening` 的 `a6f10591` 创建。

### Scope

本版本将 Kim-lite MPC 从 synthetic/replay 验证推进到南京 EnergyPlus 模型的在线闭环 co-simulation 第一版。在线 runner 放在 `Nanjing-DataCenter-TES-EnergyPlus/controller/energyplus_mpc/`，不污染 `mpc_v2/` 的算法验证边界。

### Code Changes

- 新增 EnergyPlus-MPC coupling package，包含静态 epJSON 参数提取、baseline timeseries 参数识别、forecast adapter、Kim-lite MPC adapter、Runtime API runner、TES perturbation runner 和结果 audit。
- 新增参数产物 `Nanjing-DataCenter-TES-EnergyPlus/controller/energyplus_mpc/config/energyplus_mpc_params.yaml`。
- 新增物理参数说明 `Nanjing-DataCenter-TES-EnergyPlus/docs/physical_model_parameters.md`。
- 新增耦合报告 `docs/energyplus_mpc_coupling_report_20260507.md` 和任务执行记录 `docs/project_management/energyplus_mpc_coupling_execution_20260507.md`。
- 在线 runner 只控制 `TES_Set`，通过 Runtime API 读取 SOC、TES heat transfer、chiller、facility electricity、zone temperature 和天气状态。
- 默认 `--record-start-step auto`，从 baseline 中选择 chiller 已活跃的 96 步窗口，避免 January 1 前 96 步无法验证 TES 物理响应。
- 未修改 `Nanjing_DataCenter_TES.epJSON`。

### Validation

Commands:

```powershell
python -m pytest -q
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.extract_params --model Nanjing-DataCenter-TES-EnergyPlus/model/Nanjing_DataCenter_TES.epJSON
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.identify_params --timeseries Nanjing-DataCenter-TES-EnergyPlus/out/energyplus_nanjing/timeseries_15min.csv
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller no_control --max-steps 96
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller rbc --max-steps 96
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_energyplus_mpc --controller mpc --max-steps 96
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_perturbation_profile --max-steps 96
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.audit_results --root results/energyplus_mpc_20260507
git diff --check
```

Result:

```text
extract_params -> passed
identify_params -> passed
no_control/rbc/mpc EnergyPlus Runtime API runs -> completed, 0 Severe Errors
perturbation EnergyPlus Runtime API run -> completed, both TES use/source responses observed
audit_results -> passed
```

`python -m pytest -q` 和 `git diff --check` 在提交前最终复核。

### 运行结果位置

`results/energyplus_mpc_20260507/`

### 运行结果简述

- 记录窗口：simulation step `142` 到 `237`，`2024-01-02 11:30:00` 到 `2024-01-03 11:15:00`。
- `no_control`：facility energy `184392.28 kWh`，PV-adjusted cost `8189.44`，peak facility `9571.20 kW`。
- `rbc`：facility energy `181918.29 kWh`，PV-adjusted cost `7994.71`，TES use response count `2`。
- `mpc`：facility energy `171517.75 kWh`，PV-adjusted cost `7583.33`，peak facility `7336.20 kW`，fallback count `0`，TES use response count `26`。
- `perturbation`：positive and negative `TES_Set` pulses both produced EnergyPlus TES physical response; use response count `10`，source response count `31`。
- 所有 case 的 `TES_Set` echo mismatch count 为 `0`。

### Thesis Impact

- 未更新 `docs/project_management/毕业设计论文/thesis_draft.tex`。
- 未更新 `docs/project_management/毕业设计论文/references.bib`。
- 原因：本版本生成了 EnergyPlus 在线闭环证据，但尚未由用户确认作为论文主结论；若采用，论文必须区分 EnergyPlus facility electricity、PV-adjusted grid/cost、EnergyPlus 物理响应和 MPC proxy prediction。

### Known Limitations

- MPC 优化层仍是 Kim-lite proxy，EnergyPlus 负责物理响应；这不是完整白盒 plant MPC。
- 当前 MPC 96-step case 主要执行放冷，未在经济 MPC case 内触发 source-side 充冷；source-side 响应由 perturbation case 验证。
- 第一版只控制 `TES_Set`，不直接控制 chiller availability、pump mass flow、CRAH fan 或 setpoint。
- `--record-start-step auto` 是为了获得可验证 TES 物理响应窗口；不应把 January 1 前 96 步无 TES 响应误判为耦合失效。

## v0.5.1-kim-lite-hardening - 2026-05-07

### Git

- Commit: `49495482`（Kim-lite hardening 实现与结果提交；本条目的 hash 回填由后续 metadata commit 完成）。
- 分支：`codex/kim-lite-hardening`
- 基线：从 `codex/kim-lite-paper-mpc` 的 `a77baf8d` 创建。

### Scope

本版本加严 Kim-lite 结果口径，不引入 split charge/discharge efficiency、不接入 EnergyPlus、不修改 PPT。

### Code Changes

- 新增 `storage_priority_neutral_tes`，保留非 neutral `storage_priority_tes` 作为诊断。
- 新增显式 `mode_integrality=strict|relaxed` 接口，peak-cap 不再自动 relaxed。
- Phase D 同时输出 strict 主结果和 relaxed reference；strict 失败只写诊断，不静默替换。
- Kim-lite MILP SOC bounds 改为硬约束，terminal SOC error 单独报告。
- 新增 `mpc_v2/scripts/audit_kim_lite_results.py`，审计 final SOC、grid balance、SOC bounds、mode integrality 和 attribution 字段。
- 新增 hardening 报告和执行记录。

### Validation

Commands:

```powershell
python -m pytest -q
python -m mpc_v2.scripts.run_kim_lite_matrix --phase phase_b_attribution --output-root results/kim_lite_hardened_20260507
python -m mpc_v2.scripts.run_kim_lite_matrix --phase phase_d_peakcap --output-root results/kim_lite_hardened_20260507
python -m mpc_v2.scripts.audit_kim_lite_results --root results/kim_lite_hardened_20260507
git diff --check
```

Result:

```text
python -m pytest -q -> 28 passed
Phase B matrix -> completed
Phase D matrix -> completed with strict timeout diagnostics for TES cap 0.97 and 0.95
Audit -> passed
git diff --check -> passed, CRLF warnings only
```

### 运行结果位置

`results/kim_lite_hardened_20260507/`

### 运行结果简述

- Phase B hardened attribution：`MPC_value=0.0000`，`TES_value=182.1120`，`RBC_gap_non_neutral=56.8614`，`RBC_gap_neutral=26.3821`。
- `storage_priority_neutral_tes` final SOC error 约 `4.44e-16`，满足 SOC-neutral 口径。
- Phase D strict rows：TES cap `1.00` 和 `0.99` 成功；TES cap `0.97` 和 `0.95` 触发 solver time limit 并记录 `fallback_reason`。
- Relaxed Phase D rows 仅作为 reference，明确标记 `mode_integrality=relaxed` 和 `solver_status=optimal_relaxed_modes`。

### Thesis Impact

- 未更新 `docs/project_management/毕业设计论文/thesis_draft.tex`。
- 未更新 `docs/project_management/毕业设计论文/references.bib`。
- 原因：本版本是 Kim-lite 结果加严和诊断，不直接把 hardened 结果写入论文正文。
- 如果后续采用 hardened Kim-lite 结果作为论文结论，必须同步说明：这是 Kim-style 结构复现，不是 Kim et al. 2022 数值复现。

### Known Limitations

- TES 仍是 signed net LTI proxy，split charge/discharge efficiency 尚未加入。
- Phase D strict TES peak-cap 在 cap ratio `0.97` 和 `0.95` 下达到 solver time limit。
- Relaxed mode rows 不能支持最终整数 plant-mode 结论。

## v0.5.0-kim-lite-paper-mpc - 2026-05-07

### Git

- Commit: `32cbd576`（Kim-lite 实现与结果提交；本条目的 hash 回填由后续 metadata commit 完成）。
- 分支：`codex/kim-lite-paper-mpc`
- 基线：从 `codex/mpc-rebuild` 的 `20398c7a` 创建。

### Scope

本版本新增独立 Kim-style paper-like MPC 主线，不替换当前 rebuilt minimal MPC v1：

```text
mpc_v2/kim_lite/
mpc_v2/scripts/run_kim_lite_closed_loop.py
mpc_v2/scripts/run_kim_lite_matrix.py
mpc_v2/scripts/plot_kim_lite_results.py
```

### Code Changes

- 新增 Kim-lite typed config、输入构造、signed-net TES proxy、cold plant mode MILP、baseline、metrics 和 plotting。
- 新增 `direct_no_tes`、`mpc_no_tes`、`storage_priority_tes`、`paper_like_mpc_tes` 归因路径。
- 新增中国 TOU/尖峰电价工程近似和 peak-cap screening。
- 新增 signed valve ramp 指标与约束。
- 新增 Phase 0 inventory、final report、PPT storyboard 和结果 figures。
- Phase D peak-cap 为防止 solver time-limit 卡死，显式使用 relaxed mode binaries，`solver_status` 记录为 `optimal_relaxed_modes`。

### Validation

Commands:

```powershell
python -m pytest -q
python -m mpc_v2.scripts.run_kim_lite_matrix --phase all --output-root results/kim_lite_repro_20260507
```

Result:

```text
python -m pytest -q -> 24 passed
Kim-lite Phase A-E matrix -> completed
figures -> 8 PNG generated
PPT storyboard -> generated, no PPTX modified
```

### 运行结果位置

`results/kim_lite_repro_20260507/`

### 运行结果简述

- Phase A：`paper_like_mpc` cost `19162.4750`，final SOC `0.5000`；`storage_priority` cost `19219.3182`，final SOC `0.8496`。
- Phase B attribution：`MPC_value=0.0000`，`TES_value=182.0938`，`RBC_gap=56.8432`。
- Phase C：flat/base/base_cp20/high_spread/high_spread_cp20 TOU 场景完成。
- Phase D：cap ratio `1.00/0.99/0.97/0.95` peak-cap screening 完成；此阶段为 relaxed mode binary screening。
- Phase E：signed valve run 完成，`max_signed_du=0.25`，`signed_valve_violation_count=0`。

### Thesis Impact

- 未更新 `docs/project_management/毕业设计论文/thesis_draft.tex`。
- 未更新 `docs/project_management/毕业设计论文/references.bib`。
- 原因：本版本生成 Kim-lite 结构复现代码、结果和报告，但尚未把这些结果写入论文正文，也未新增正式引用。
- 如果后续把 Kim-lite 结果作为论文主结果，必须同步更新 thesis draft，并明确这是 Kim et al. 2022 风格结构复现，不是数值复现。

### Known Limitations

- Kim-lite TES 是 signed net LTI proxy，尚不是 split charge/discharge efficiency model。
- Phase D peak-cap 是 relaxed mode binary screening，不等同于完整整数 plant-mode proof。
- `direct_no_tes` 与 `mpc_no_tes` 在当前简化 plant setup 下 cost 相同，说明无 TES 时暂未体现独立 MPC value。
- `storage_priority_tes` 非 SOC-neutral，和 `paper_like_mpc_tes` 比较时必须显式报告 final SOC。

## v0.4.0-mpc-rebuild-minimal - 2026-05-07

### Git

- Commit: `03d4f609`（实现提交；本 changelog 条目如被后续 metadata-only commit 更新，以分支历史为准）。
- 分支：`codex/mpc-rebuild`
- 备份：重建前未提交 MPC 状态已保存到本地分支 `codex/mpc-before-rebuild-backup-20260507`，commit `8f942ad0`。

### Scope

本版本删除旧 MPC 大矩阵/归因/DR/peak-cap 实现路径，重建 `mpc_v2/` 为 deterministic/replay 最小闭环 MPC v1，同时保留前后数据流：

- 输入仍以 `mpc_v2/config/base.yaml` 为默认配置入口。
- 单场景入口仍为 `mpc_v2/scripts/run_closed_loop.py`。
- 批量验证入口仍为 `mpc_v2/scripts/run_validation_matrix.py`。
- 每次 run 仍输出 `monitor.csv`、`timeseries.csv`、`solver_log.csv`、`events.csv`、`episode_summary.json`、`summary.csv` 和 `config_effective.yaml`。

### Code Changes

- 新增 `mpc_v2/contracts/`，冻结输入配置、CLI 参数和输出文件/字段契约。
- 新增最小 plant、forecast、controller、metrics 实现；支持 `no_tes`、`rbc`、`mpc` 和兼容别名 `mpc_no_tes`。
- MPC v1 使用确定性线性优化，支持 horizon、SOC bounds、terminal SOC target、PV/grid/spill 平衡和价格驱动充放冷。
- 删除旧 China TOU/DR generated matrix YAML；旧矩阵生成和高级报告脚本改为明确抛出 unsupported feature。
- 新增 `mpc_v2/AGENTS.md`，明确 v1 支持范围和 deferred features。
- 更新根目录 `AGENTS.md`，将 MPC 算法验证默认路由到 `mpc_v2/`。

### Validation

Commands:

```powershell
python -m pytest -q
python -m mpc_v2.scripts.run_closed_loop --controller-mode no_tes --steps 96 --case-id smoke_no_tes --output-root results/mpc_rebuild_v0_4_0_20260507
python -m mpc_v2.scripts.run_closed_loop --controller-mode rbc --steps 96 --case-id smoke_rbc --output-root results/mpc_rebuild_v0_4_0_20260507
python -m mpc_v2.scripts.run_closed_loop --controller-mode mpc --steps 96 --case-id smoke_mpc --output-root results/mpc_rebuild_v0_4_0_20260507 --truncate-horizon-to-episode --initial-soc 0.5 --soc-target 0.5
python -m mpc_v2.scripts.run_validation_matrix --output-root results/mpc_rebuild_v0_4_0_20260507/matrix
```

Result:

```text
python -m pytest -q -> 17 passed
no_tes smoke -> fallback_count 0, SOC violation 0, final SOC 0.5000
rbc smoke -> fallback_count 0, SOC violation 0, final SOC 0.14947
mpc smoke -> fallback_count 0, SOC violation 0, physical consistency violation 0, final SOC 0.5000
minimal validation matrix -> 3/3 scenarios completed
```

### 运行结果位置

`results/mpc_rebuild_v0_4_0_20260507/`

### 运行结果简述

- `smoke_mpc` 24h：total_cost `38780.2913`，grid_import_kwh `422240.5176`，peak_grid_kw `19280.7692`。
- `smoke_mpc` SOC-neutral 验收通过：`initial_soc=0.5`，`final_soc_after_last_update=0.5`，`soc_min=0.15`，`soc_max=0.85`。
- `smoke_mpc` 价格移峰行为可见：charge weighted avg price `0.0530`，discharge weighted avg price `0.17375`。
- 结论边界：该结果只证明重建后的最小 deterministic/replay MPC 数据流和固定 24h smoke 可复核，不证明旧 China TOU/DR 矩阵、peak-cap、demand-charge 或 attribution 结论。

### Thesis Impact

- 未更新 `docs/project_management/毕业设计论文/thesis_draft.tex`。
- 未更新 `docs/project_management/毕业设计论文/references.bib`。
- 原因：本版本重建代码和验证数据流，但没有把新 MPC 结果写入论文，也没有新增或删除引用。
- 注意：旧 MPC 矩阵和归因结果不再代表当前 `mpc_v2/` 实现；如果论文正文引用旧结果，后续必须用新系统重新跑验证后再同步论文。

### Known Limitations

- MPC v1 只支持 deterministic/replay fixed scenario，不支持旧 China TOU/DR 大矩阵。
- DR、peak-cap、demand-charge 和 attribution/report generation 已延后，调用时会明确报 unsupported。
- 当前 plant/room 是可复核 proxy，不是 EnergyPlus 在线耦合模型。
- `rbc` 是规则基线，不强制 SOC-neutral；论文对比前需要定义公平终端 SOC 口径。

## v0.3.2-literature-extracted-index - 2026-05-07

### Git

- Commit: 本条目随本次文献索引提交一起生成；云端提交 hash 以 `git log -1 --oneline` 和最终推送结果为准。
- 状态：整理 `docs/literature/extracted_articles/` 文献索引、PDF 副本、摘要和核心公式/算法 Markdown；未新增仿真、验证矩阵或实验结论。

### Scope

本版本将本地文献 PDF 整理为低 token 文献索引：

```text
docs/literature/core_references + docs/literature/other_references
-> docs/literature/extracted_articles
```

### Changes

- 新增 `docs/literature/extracted_articles/README.md` 和 `manifest.json`，记录 27 个来源 PDF 去重后的 22 篇文章。
- 为每篇文章创建独立文件夹，包含重命名后的 PDF 副本、`summary.md` 和 `core_algorithm.md`。
- PDF 副本命名为 `YYYY_FirstAuthor_Short_Title.pdf`，并在 Markdown 与 manifest 中同步记录。
- 新增 `docs/literature/extracted_articles/AGENTS.md`，定义该低 token 文献索引目录的维护、去重、命名、验证和论文同步规则。
- 保留上层 `core_references/` 和 `other_references/` 原始 PDF，不移动、不重命名、不删除原始文献。

### Validation

Document-level validation commands:

```powershell
Get-ChildItem -Path "docs\literature\extracted_articles" -Directory
python - <<'PY'
from pathlib import Path
root = Path('docs/literature/extracted_articles')
assert len(list(root.glob('*/summary.md'))) == 22
assert len(list(root.glob('*/core_algorithm.md'))) == 22
assert len(list(root.glob('*/*.pdf'))) == 22
PY
```

Result:

```text
22 个文献文件夹均包含 1 个 PDF 副本、summary.md 和 core_algorithm.md。
PDF 副本 SHA256 与 manifest.json 中记录一致。
summary.md、core_algorithm.md、README.md 和 manifest.json 中的 PDF 文件名已同步。
```

未运行 `python -m pytest -q`，因为本版本不修改代码、模型、输入或测试。

### 运行结果位置

运行结果位置：无新增结果

原因：本版本只整理文献索引和 PDF/Markdown 证据材料，未执行 EnergyPlus 仿真或 MPC 验证矩阵。

### 运行结果简述

- 无新增仿真结果。
- 无新增验证矩阵。
- 无新增实验结论。
- 新增文献索引目录可用于后续论文引用核对、公式回查和算法复现准备。

### Thesis Impact

- 未更新 `docs/project_management/毕业设计论文/thesis_draft.tex`。
- 未更新 `docs/project_management/毕业设计论文/references.bib`。
- 原因：本版本没有新增或删除正式引用，也没有把文献结论写入论文正文；只是建立文献整理索引和来源证据。
- 注意：抽查发现部分核心文献的 BibTeX 作者信息可能与 PDF 首页不一致，后续若修正引用库，应单独更新 `references.bib` 并检查正文 citation key。

### Known Limitations

- `core_algorithm.md` 中的公式来自 PDF 文本抽取，可能丢失上下标、分式和跨栏顺序；正式写入论文前必须回到 PDF 页面人工核对。
- 本目录中的文献结论只能作为设计依据或复现入口，不能直接等同于当前 EnergyPlus/TES/PV/电价模型已经实现或验证。
- `_archive/` 下外部项目自带 PDF 未纳入本次整理范围。

## v0.3.0-china-tou-dr-matrix - 2026-05-07

### Git

- Commit: `e86779bf` 为当前工作树基线；本版本变更尚未提交。
- 状态：本地已完成代码、测试、138-run pilot、138-run 30 天正式矩阵和结果冻结。

### Scope

本版本完成中国 TOU/尖峰电价、DR event、peak-cap 和稳健性矩阵的 1 个月 synthetic/replay MILP-MPC 仿真：

```text
tariff service with gamma/cp uplift/float share
+ single-event DR service
+ generated 138-run China TOU/DR matrix
+ derived peak-cap baseline
+ 30-day closed-loop validation
+ frozen result package
```

### Code Changes

- `mpc_v2/core/tariff_service.py`：新增中国 TOU/尖峰电价服务；`actual_at` 使用全序列参考均值，避免 1-step settlement 下 `gamma/cp_uplift` 失效。
- `mpc_v2/core/dr_service.py`：新增单次 DR 事件定位参数，支持 `event_day_index` 和 `event_start_timestamp`，避免 30 天 run 中每日重复触发。
- `mpc_v2/scripts/generate_china_matrix.py`：生成 pilot 和正式矩阵 YAML。
- `mpc_v2/scripts/run_validation_matrix.py`：支持由 no-cap baseline 自动推导 peak cap，支持 `--max-workers` 和 `--resume-existing`。
- `mpc_v2/scripts/analyze_results.py`：新增 TOU cost curve、TOU arbitrage spread、DR event profile、peak-cap tradeoff 和 solver time 图。
- `mpc_v2/scripts/generate_result_reports.py`：为每个正式 run 生成 4 张 MATLAB 风格图和一份 Markdown 报告，并生成总报告。
- `tests/`：新增 tariff、DR 单次事件、矩阵生成和 derived peak-cap 测试。
- 同步更新 `README.md`、任务文件和论文草稿。

### Validation

Final test command:

```powershell
python -m pytest -q
```

Result:

```text
32 passed
```

Pilot command:

```powershell
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenarios mpc_v2/config/generated_china_matrix_pilot.yaml --scenario-set china_all_full --output-dir runs/china_tou_dr_pilot_20260506
```

Formal matrix command:

```powershell
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenarios mpc_v2/config/generated_china_matrix_month.yaml --scenario-set china_all_full --output-dir runs/china_tou_dr_month_20260506 --max-workers 8 --resume-existing
```

Analysis command:

```powershell
python -m mpc_v2.scripts.analyze_results --input-dir runs/china_tou_dr_month_20260506 --output-dir runs/china_tou_dr_month_20260506/analysis
python -m mpc_v2.scripts.generate_result_reports --result-dir results/china_tou_dr_matrices_20260506
```

### 运行结果位置

- Frozen result directory: `results/china_tou_dr_matrices_20260506/`
- Formal raw runs: `results/china_tou_dr_matrices_20260506/raw/`
- Formal summary: `results/china_tou_dr_matrices_20260506/validation_summary.csv`
- Analysis outputs: `results/china_tou_dr_matrices_20260506/analysis/`
- Per-case reports and figures: `results/china_tou_dr_matrices_20260506/reports/`
- Result README: `results/china_tou_dr_matrices_20260506/README.md`

### 运行结果简述

- Matrix size: 138 / 138 runs completed, each 30 days = 2880 steps.
- Categories: TOU screening 40, TOU full compare 32, peak-cap 24, DR event 18, robustness 24.
- Reports: 138 per-case Markdown reports and 552 MATLAB-style PNG figures generated under `results/china_tou_dr_matrices_20260506/reports/`.
- Feasibility: total `fallback_count = 1`; minimum `feasible_rate = 1.0`; minimum `optimal_rate = 0.999653`.
- Solver time: maximum `solve_time_p95_s = 3.7692 s`.
- Paired TES-MPC benefit: `mpc_no_tes` to `mpc` mean monthly saving = 518.81 CNY, bootstrap CI = 313.84 to 737.38 CNY, `n_pairs = 61`.
- TOU screening: `mpc` mean monthly cost = 1,291,919.83 CNY; `mpc_no_tes` = 1,292,366.36 CNY; paired mean saving = 446.52 CNY.
- TOU full compare: mean monthly cost is 1,296,598.71 CNY for `mpc`, 1,297,248.94 CNY for `mpc_no_tes`, 1,347,132.29 CNY for `rbc`, and 1,348,448.17 CNY for `no_tes`.
- Peak-cap: derived caps achieved mean peaks of 21090.0, 20879.1, 20457.3, 20035.5 kW for `r_cap = 1.00, 0.99, 0.97, 0.95`; `peak_slack_max_kw` is numerically zero.
- DR event: each scenario triggers one event; requested reductions are 1900, 3800, 5700 kWh for `r_DR = 0.05, 0.10, 0.15`; served reduction is 2060.78 kWh in the current proxy setting.

### Thesis Impact

- `docs/project_management/毕业设计论文/thesis_draft.tex` 已同步更新，加入 1 个月中国 TOU/DR synthetic/replay 矩阵结果和结论边界。
- `references.bib` 未更新，因为本版本未把政策或论文依据作为正式引用写入论文。

### Known Limitations

- 本版本仍是 `mpc_v2` synthetic/replay closed loop，不是 EnergyPlus online co-simulation。
- DR baseline 与收益是情景估算，不能表述为真实市场结算。
- 严格 `r_cap=0.95` peak-cap 场景出现约 415-431 degree-hours 温度违约，应作为约束压力测试。
- TES 增量收益只能按 `mpc_no_tes` 到 `mpc` 报告，不能把 direct baseline 到 MPC 的全部收益归因于 TES。

## v0.1.0-mpc-v2 - 2026-05-05

### Git

- Commit: `50534ddc feat(mpc): add deterministic TES MPC v2`
- Branch status:
  - `master`
  - `origin/master`
  - `codex/folder-cleanup-20260504`
  - `origin/codex/folder-cleanup-20260504`
- 状态：上述分支均已指向同一提交。

### Scope

本版本将项目从“南京 EnergyPlus 最小模型包”推进到：

```text
Nanjing EnergyPlus input/model package
+ top-level deterministic TES-PV-TOU MILP-MPC package
+ no-TES baseline
+ closed-loop smoke validation
+ thesis_core validation matrix
+ saved reproducible results
```

不包含：

```text
RL training
stochastic MPC
new EnergyPlus deep coupling
rule-based TES baseline
```

### Code Changes

- 新增 `mpc_v2/`
  - `config/base.yaml`
  - `config/scenario_sets.yaml`
  - `core/` typed schemas, TES dynamics, room proxy, facility/PV/grid balance, MILP, controller, metrics
  - `scripts/run_closed_loop.py`
  - `scripts/run_validation_matrix.py`
- 新增 `tests/`
  - schema
  - TES dynamics
  - room model
  - power balance
  - MILP single-step solve
  - closed-loop smoke
  - scenario matrix
- 新增 `results/mpc_v2_20260505/`
  - no-TES smoke output
  - TES-MPC smoke output
  - full `thesis_core` validation matrix output
  - result summary
- 更新 `README.md`
- 更新 `docs/project_management/毕业设计论文/thesis_draft.tex`
- 新增实施文档：
  - `docs/codex_repo_state_20260504.md`
  - `docs/final_mpc_implementation_spec.md`
  - `docs/codex_final_implementation_report_20260504.md`

### Validation

Final test command:

```powershell
python -m pytest -q
```

Result:

```text
12 passed
```

Smoke commands:

```powershell
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_no_tes --controller-mode no_tes --steps 96 --output-root runs/smoke
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_tes_mpc --controller-mode mpc --steps 96 --output-root runs/smoke
```

Validation matrix command:

```powershell
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenario-set thesis_core --output-dir runs/final_mpc_validation
```

### 运行结果位置

- Frozen result directory: `results/mpc_v2_20260505/`
- Smoke outputs:
  - `results/mpc_v2_20260505/smoke/smoke_no_tes/`
  - `results/mpc_v2_20260505/smoke/smoke_tes_mpc/`
- Validation matrix outputs:
  - `results/mpc_v2_20260505/final_mpc_validation/`
- Result summary:
  - `results/mpc_v2_20260505/summary.md`

### 运行结果简述

Single smoke run duration:

```text
96 steps * 0.25 h = 24 h
```

MPC prediction horizon:

```text
192 steps * 0.25 h = 48 h
```

Key no-TES vs TES-MPC smoke results:

| Metric | no-TES | TES-MPC | Interpretation |
|---|---:|---:|---|
| Total cost | 46221.61 | 45641.42 | Cost reduced by about 1.26%. |
| Grid import kWh | 496328.40 | 496357.23 | Electricity use did not decrease. |
| Facility energy kWh | 516672.00 | 516700.83 | Facility energy did not decrease. |
| PV spill kWh | 0.00 | 0.00 | No PV self-consumption improvement was possible in this case. |
| Avg PUE | 1.1960 | 1.1961 | PUE was effectively unchanged and slightly higher. |
| Temp violation degree-hours | 10.38 | 5.68 | Thermal violations improved but were not eliminated. |
| Max room temp C | 29.48 | 28.74 | Still above the 27 C upper bound. |
| TES discharge kWh_th | 0.00 | 51173.66 | TES was actively used. |
| TES equivalent cycles | 0.00 | 2.84 | TES was heavily cycled in 24 h. |
| Fallback count | 0 | 0 | No solver fallback. |

Conclusion boundary:

- TES operation objective was reached: MPC actively charged/discharged TES and kept SOC inside physical bounds.
- Cost objective was partially reached: TES-MPC reduced total cost by about 1.26% versus no-TES.
- Energy-saving objective was not reached in this run: grid import and facility energy did not decrease.
- PV-utilization improvement was not demonstrated: no-TES already had zero PV spill.
- Thermal behavior improved but remained imperfect: temperature violation degree-hours fell, but the maximum room temperature still exceeded 27 C.

### Thesis Impact

- `thesis_draft.tex` 已同步更新，说明本地 `mpc_v2` 控制层已经存在。
- `references.bib` 未更新，因为本版本未新增或删除文献引用。
- 当前结果可用于说明：
  - deterministic MILP-MPC 框架已可运行；
  - TES 能被 MPC 调用并完成充放冷；
  - 当前 synthetic/replay 场景中成本下降、温度越界改善。
- 当前结果不能用于声称：
  - 显著节能；
  - PV 消纳提升；
  - 温度约束完全满足；
  - 充放冷时序已满足工程部署要求。

### Known Limitations

- 当前闭环是 synthetic/replay validation，不是 EnergyPlus co-simulation。
- no-TES baseline 已经没有 PV spill，因此无法验证 TES 提升 PV 消纳。
- TES-MPC 降低成本但没有降低总电耗。
- TES 充放冷存在 15 min 级短周期切换，需要后续增加切换惩罚、ramp 约束或最小持续时间约束。
- 每个 smoke 和 validation 场景当前只运行 24 h；后续论文结果建议扩展到典型周或更长时段。

### Artifacts

- Code: `mpc_v2/`
- Tests: `tests/`
- Results: `results/mpc_v2_20260505/`
- Result summary: `results/mpc_v2_20260505/summary.md`
- Review archive: `exports/mpc_v2_code_results_review_20260505.zip`

## v0.2.2-chiller-tes-attribution - 2026-05-06

### Git

- Commit: not committed yet
- Branch: `codex/55TES-MPC`

### Changed Scope

- 新增 `mpc_no_tes` baseline，用同一 MILP、温度约束、冷机 mode、TOU/PV/grid 目标运行，但禁用 TES 充放冷并保持 SOC 不变。
- 主 PV/grid 口径改为全设施 behind-the-meter：`grid = max(0, IT + cold station - PV)`；冷站侧 proxy cost/grid/PV 指标保留为辅助归因指标。
- 默认 MPC horizon 改为 48 steps，即 12 h receding horizon；192-step / 48 h horizon 只作为 slow/manual 扩展。
- 新增 `attribution_core` 结果矩阵：direct no-TES、MPC no-TES、RBC TES、MPC TES、SOC-neutral attempt。
- 更新 README 和论文草稿事实口径。

### Validation

```powershell
pytest -q
git diff --check
```

结果：

```text
23 passed
git diff --check passed with line-ending warnings only
```

### 运行结果位置

- `results/chiller_tes_mpc_attribution_20260505/`
- 核心文件：
  - `summary.md`
  - `attribution_matrix.csv`
  - `README_REVIEW.md`
  - 每个 case 的 `monitor.csv`、`solver_log.csv`、`episode_summary.json`、`config_effective.yaml`

### 运行结果简述

- 5 个 7-day case 均为 672 steps、12 h horizon，且均满足 fallback=0、温度 degree-hour=0、物理一致性违约=0、signed-valve 违约=0。
- 全设施侧主成本下，`mpc_no_tes` 相比 direct no-TES 降本约 4.56%，说明价格感知冷机调度、热惯性和 mode 优化解释了主要收益。
- `mpc_tes` 相比 `mpc_no_tes` 额外降本约 0.09%，这才是当前结果中 TES 的增量经济贡献。
- `mpc_tes` 出现 TES 双向行为：充冷约 21676.87 kWh_th，放冷约 22821.69 kWh_th，放冷加权电价高于充冷加权电价。
- nominal 全设施侧 PV spill 为 0，因为 IT 负荷显著大于 6 MWp PV；当前不能声称 TES 显著提高 PV 消纳。
- `mpc_tes_soc_neutral` 是库存中性尝试，但 final SOC 仍为 0.15，未达到 `abs(final SOC - initial SOC) <= 0.03`，说明当前滚动 horizon 终端惩罚不能保证 episode-end SOC neutral。

### Thesis Impact

- `thesis_draft.tex` 已同步更新：新增 `mpc_no_tes` attribution baseline、全设施 PV/grid 口径、12 h horizon、TES 增量贡献和 SOC-neutral 未达标边界。
- `references.bib` 未更新，因为未新增或删除文献引用。
- 论文中不能写 TES 单独带来 direct baseline 到 MPC 的全部降本；应写冷机经济 MPC 与 TES 的共同贡献，并用 `mpc_tes - mpc_no_tes` 表示 TES 增量贡献。

### Known Limitations

- SOC-neutral 仍未实现，需要 episode-end terminal constraint 或截断末端 horizon 才能严格闭合库存。
- nominal 全设施 PV spill 为 0，不能用于证明 TES 吸收 PV surplus。
- 48 h prediction horizon 未作为最终候选运行，只保留为慢速扩展。

## Unreleased

### 2026-05-06 - China TOU/DR scenario services and task plan

#### Git

- Commit: not committed yet
- Branch: current working branch

#### Scope

- 从 `C:\Users\18430\Downloads\deep-research-report (10).md` 提取审查报告任务，生成：
  - `docs/project_management/中国TOU_DR控制对比任务执行计划_20260506.md`
- 新增中国分时电价/尖峰电价服务：
  - `mpc_v2/core/tariff_service.py`
  - 支持 `beijing`、`guangdong_cold_storage` 和既有 CSV 价格模板
  - 支持 `gamma`、`cp_uplift`、`float_share`
- 新增 DR/peak-cap 服务：
  - `mpc_v2/core/dr_service.py`
  - 支持 DR 事件窗口、baseline、请求削减、动态 cap、响应率和事件收益估算
- 扩展闭环输出：
  - `timeseries.csv`
  - `events.csv`
  - `summary.csv`
  - 保留 `monitor.csv`、`solver_log.csv`、`episode_summary.json`
- 新增统计和结果汇总工具：
  - `mpc_v2/core/statistics.py`
  - `mpc_v2/scripts/analyze_results.py`
- 扩展 `scenario_sets.yaml`：
  - `china_tou_screening_smoke`
  - `china_tou_full_compare`
  - `china_dr_peakcap_core`
  - `china_robustness_core`

#### Validation

```powershell
python -m pytest -q
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenario-set china_tou_screening_smoke --steps 4 --output-dir runs/china_tou_screening_smoke_20260506
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenario-set china_tou_full_compare --steps 4 --output-dir runs/china_tou_full_compare_smoke_20260506
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenario-set china_dr_peakcap_core --steps 4 --output-dir runs/china_dr_peakcap_core_20260506
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenario-set china_robustness_core --steps 4 --output-dir runs/china_robustness_core_smoke_20260506
python -m mpc_v2.scripts.analyze_results --input-dir runs/china_tou_screening_smoke_20260506 --output-dir runs/china_tou_screening_smoke_20260506/analysis
python -m mpc_v2.scripts.analyze_results --input-dir runs/china_tou_full_compare_smoke_20260506 --output-dir runs/china_tou_full_compare_smoke_20260506/analysis
python -m mpc_v2.scripts.analyze_results --input-dir runs/china_dr_peakcap_core_20260506 --output-dir runs/china_dr_peakcap_core_20260506/analysis
python -m mpc_v2.scripts.analyze_results --input-dir runs/china_robustness_core_smoke_20260506 --output-dir runs/china_robustness_core_smoke_20260506/analysis
```

结果：

```text
28 passed
TOU smoke matrix completed
DR/peak-cap smoke matrix completed
analysis summaries completed
```

#### 运行结果位置

- Smoke output:
  - `runs/china_tou_screening_smoke_20260506/`
  - `runs/china_tou_full_compare_smoke_20260506/`
  - `runs/china_dr_peakcap_core_20260506/`
  - `runs/china_robustness_core_smoke_20260506/`
- Analysis output:
  - `runs/china_tou_screening_smoke_20260506/analysis/`
  - `runs/china_tou_full_compare_smoke_20260506/analysis/`
  - `runs/china_dr_peakcap_core_20260506/analysis/`
  - `runs/china_robustness_core_smoke_20260506/analysis/`
- Frozen result directory: 无新增冻结结果；本次只生成 ignored `runs/` 下的短步长配置 smoke。

#### 运行结果简述

- `china_tou_screening_smoke` 以 `--steps 4` 跑通 6 个短场景，验证北京 TOU 参数、`gamma/cp_uplift/float_share`、批量场景和新增输出文件链路。
- `china_tou_full_compare` 以 `--steps 4` 跑通 8 个短场景，验证 direct no-TES、MPC no-TES、RBC TES 和 TES-MPC 在代表性 TOU 配置中的批量入口。
- `china_dr_peakcap_core` 以 `--steps 4` 跑通 8 个短场景，验证 DR/peak-cap 配置可被 runner 消化；默认 DR 场景事件窗口在 18:00，4-step 午夜 smoke 不触发事件，事件触发由单元测试覆盖。
- `china_robustness_core` 以 `--steps 4` 跑通 4 个短场景，验证 `initial_soc`、horizon 和 forecast disturbance 配置入口。
- 这些 smoke 只验证配置和日志链路，不能作为论文统计结果。

#### Thesis Impact

- `thesis_draft.tex` 已同步补充：当前 `mpc_v2` 已包含中国 TOU/尖峰电价、DR/peak-cap 场景服务和事件日志，但仍属于 synthetic/replay closed-loop validation，不是 EnergyPlus co-simulation。
- `references.bib` 未更新，因为本次未新增正式文献或政策引用；后续若把政策依据写入论文正文，需要先核验原文并补引用。

#### Known Limitations

- 完整 72-run TOU 矩阵和 DR/peak-cap 主线矩阵尚未运行。
- DR baseline 和补偿当前是情景估算，不等于真实市场结算。
- `peak_cap_reference_kw` 当前为工程设定；正式论文建议从 no-cap baseline 自动推导。
- `guangdong_cold_storage` 模板是附录接口，尚未完成正式政策核验。

后续版本建议优先处理：

- 加强温度约束满足能力。
- 降低 TES 短周期切换。
- 构造能体现 PV 弃光与 TES 吸纳价值的场景。
- 增加 rule-based TES baseline。
- 扩展到 7 天或典型周仿真。
- 生成论文用图表和表格。

## v0.2.0-chiller-tes-mpc-v1 - 2026-05-05

### Git

- Implementation commit: `2a75e93e feat(mpc): add chiller tes mpc v1`
- Branch: `codex/55TES-MPC`
- 状态：待提交；当前版本结果已冻结到本地 `results/`。

### Scope

本版本将 `mpc_v2` 从 TES-only 代理模型升级为冷机 + TES 联合 MILP-MPC：

```text
mode-based chiller plant
+ chilled-water TES
+ room-temperature proxy
+ PV/grid cold-station balance
+ no-TES / RBC / MPC controllers
+ thesis_chiller_tes validation matrix
```

### Code Changes

- `mpc_v2/core/` 新增冷机 mode 仿射功率模型、阀门开度代理、需求峰值变量、低 PLR 惩罚和 chiller+TES MILP 冷量平衡。
- `mpc_v2/scripts/run_closed_loop.py` 支持 `no_tes`、`rbc`、`mpc` 三类控制器，并输出 chiller、mode、valve、plant power 和 cold-station metrics。
- `mpc_v2/config/scenario_sets.yaml` 新增 `thesis_chiller_tes` 场景矩阵。
- `tests/` 扩展到 chiller dispatch、valve bounds、mode one-hot、no-TES chiller solve、RBC smoke 和新场景矩阵。
- 更新 `README.md`、论文草稿和实施计划状态。

### Validation

Final test command:

```powershell
python -m pytest -q
```

Result:

```text
16 passed
```

Smoke commands:

```powershell
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_chiller_no_tes --controller-mode no_tes --steps 96 --output-root runs/chiller_tes_v1_final_smoke
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_chiller_rbc --controller-mode rbc --steps 96 --output-root runs/chiller_tes_v1_final_smoke
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_chiller_tes_mpc --controller-mode mpc --steps 96 --output-root runs/chiller_tes_v1_final_smoke
```

Validation matrix command:

```powershell
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenario-set thesis_chiller_tes --steps 96 --output-dir runs/chiller_tes_v1_final_validation
```

### 运行结果位置

- Frozen result directory: `results/chiller_tes_mpc_v1_20260505/`
- Smoke outputs:
  - `results/chiller_tes_mpc_v1_20260505/smoke/smoke_chiller_no_tes/`
  - `results/chiller_tes_mpc_v1_20260505/smoke/smoke_chiller_rbc/`
  - `results/chiller_tes_mpc_v1_20260505/smoke/smoke_chiller_tes_mpc/`
- Validation matrix outputs:
  - `results/chiller_tes_mpc_v1_20260505/final_validation/`
- Result summary:
  - `results/chiller_tes_mpc_v1_20260505/summary.md`

### 运行结果简述

Smoke run duration:

```text
96 steps * 0.25 h = 24 h
```

MPC prediction horizon:

```text
192 steps * 0.25 h = 48 h
```

Key no-TES vs RBC vs MPC smoke results:

| Metric | no-TES | RBC | MPC |
|---|---:|---:|---:|
| Total cost | 4073.02 | 3973.24 | 3627.88 |
| Grid import kWh | 49648.43 | 33907.68 | 47442.19 |
| Peak grid kW | 3090.00 | 3090.00 | 3090.00 |
| PV spill kWh | 342.96 | 1742.03 | 342.96 |
| Cold-station energy kWh | 69649.07 | 52509.26 | 67442.83 |
| Facility energy kWh | 501649.07 | 484509.26 | 499442.83 |
| Temp violation degree-hours | 0.00 | 0.00 | 0.00 |
| TES charge kWh_th | 0.00 | 8054.70 | 7458.63 |
| TES discharge kWh_th | 0.00 | 12395.65 | 0.00 |
| TES equivalent cycles | 0.00 | 0.69 | 0.00 |
| Fallback count | 0 | 0 | 0 |

Conclusion boundary:

- Chiller+TES MPC implementation objective was reached: the MILP now contains explicit chiller load, mode binaries, plant power, valve variables, TES dynamics, room-temperature constraints, and cold-station PV/grid balance.
- Cost objective was reached in the nominal smoke case: MPC total cost fell by about 10.93% versus fair no-TES.
- Cold-station energy objective was partially reached: MPC cold-station energy fell by about 3.17% versus fair no-TES.
- Peak shaving was not reached: peak grid demand remained about 3090 kW.
- PV spill improvement was not reached in the nominal smoke case: MPC and no-TES both spilled 342.96 kWh.
- TES use was only partially reached: MPC charged TES in the nominal case but did not discharge it; the hot validation case did show discharge of 5067.20 kWh_th but had one fallback and 0.19 degree-hours of temperature violation.

### Thesis Impact

- `thesis_draft.tex` 已同步更新，加入 chiller+TES v1.0 的实际结果和局限性。
- `references.bib` 未更新，因为本版本未新增正式引用。
- 当前结果可用于论文说明：
  - 冷机 + TES MILP-MPC 闭环已可复现运行；
  - 相比公平 no-TES baseline，nominal MPC 降低成本和冷站能耗；
  - 当前代理模型尚不能支持 nominal case 下“TES 高价放冷、削峰、提高 PV 消纳”的强结论。

### Known Limitations

- 当前仍是 synthetic/replay closed loop，不是 EnergyPlus co-simulation。
- 湿球温度使用 `outdoor_temp_c - 4.0` 代理。
- 冷机 mode 参数采用 Kim 型量级初始化，未由南京实测冷站数据辨识。
- Nominal MPC 仍存在 SOC hoarding：会充 TES，但不在 24 h nominal smoke 内放冷。
- Demand charge 场景尚未形成 peak reduction。
