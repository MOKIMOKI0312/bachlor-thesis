# 毕业设计 handoff README

## 项目目标

本项目是基于 EnergyPlus + Sinergym 的数据中心冷却、TES 蓄冷与 PV 自消纳 MPC 控制系统毕业设计，目标是在可复现实验中评估 no-TES baseline、规则式 TES 与 MILP-MPC 的能耗、成本、comfort 和鲁棒性边界。

## 环境配置

- Python: `D:/Anaconda/Scripts/conda.exe run -n aidc-py310 python` 用于 Sinergym / EnergyPlus 仿真；`D:/Anaconda/python.exe` 可用于轻量 pandas/matplotlib 后处理
- EnergyPlus: 23.1；`evaluate_m2_rule_baseline.py` 和 batch 脚本含 `PYTHONPATH` fallback
- Sinergym: Xiao & You 修改版 fork，核心目录为 `AI-Data-Center-Analysis_migration_bundle_20260311/`
- 主要 Python 依赖：`gymnasium`、`numpy`、`pandas`、`scipy`（>=1.11 for HiGHS MILP）、`matplotlib`、`pyomo`

## 仓库布局

- `AI-Data-Center-Analysis_migration_bundle_20260311/`：核心代码，含 Sinergym fork、自定义 wrapper、tools、analysis、runs
- `项目目标/`：技术路线、W2-W3 plan、决策树和任务包文档
- `毕业设计项目进度/`：进度管理文档
- `agent_comms/`：Claude ↔ Codex 协议运行时，一般复现实验不需要阅读
- `AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_*`：W1 / W2 / W3 数据产物，含 csv / md / json / png
- `AI-Data-Center-Analysis_migration_bundle_20260311/runs/m2_tes_mpc_oracle/`：MPC oracle 全部 cell run

## 关键工具入口

- `AI-Data-Center-Analysis_migration_bundle_20260311/tools/m2_tes_mpc_oracle.py`：主 oracle，支持 `--solver milp/lp_highs/heuristic` 和 `--eval-design trainlike/official_ood`
- `AI-Data-Center-Analysis_migration_bundle_20260311/tools/evaluate_m2_rule_baseline.py`：no-TES baseline，`--policy neutral` 用作对照基线
- `AI-Data-Center-Analysis_migration_bundle_20260311/tools/build_w2_scenario_summary.py`：聚合 3 cells 节能 + PV 自消纳指标，`--tag-prefix w2/w2b`
- `AI-Data-Center-Analysis_migration_bundle_20260311/tools/m2_mpc_plots.py`：论文 4 张图生成脚本，matplotlib 300 DPI
- `AI-Data-Center-Analysis_migration_bundle_20260311/tools/m2_mpc_demo.ps1`：答辩现场演示脚本，当前机器实测 4.76 分钟生成 96-step SOC + valve sign-rate demo 图
- `AI-Data-Center-Analysis_migration_bundle_20260311/tools/run_w2_scenario_batch.ps1` / `run_w2b_scenario_batch.ps1`：全年 batch runner

## 复现核心数据

从仓库根目录 `C:\Users\18430\Desktop\毕业设计代码` 执行。全年 batch 脚本内部使用相对路径，建议先进入核心代码目录。

W2 trainlike 全年 batch：

```powershell
Set-Location AI-Data-Center-Analysis_migration_bundle_20260311
powershell -ExecutionPolicy Bypass -File tools/run_w2_scenario_batch.ps1
$TS = Get-Content -Encoding utf8 tools/_w2_batch_ts.txt | Select-Object -First 1
& D:/Anaconda/python.exe tools/build_w2_scenario_summary.py --ts $TS --tag-prefix w2 --skip-validation
Set-Location ..
```

W2-B official_ood 全年 batch：

```powershell
Set-Location AI-Data-Center-Analysis_migration_bundle_20260311
powershell -ExecutionPolicy Bypass -File tools/run_w2b_scenario_batch.ps1
$TS = Get-Content -Encoding utf8 tools/_w2b_batch_ts.txt | Select-Object -First 1
& D:/Anaconda/python.exe tools/build_w2_scenario_summary.py --ts $TS --tag-prefix w2b --skip-validation
Set-Location ..
```

W3 论文图：

```powershell
$TS_W3 = Get-Date -Format "yyyyMMdd_HHmmss"
$out_dir = "AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2_figures_$TS_W3"
& D:/Anaconda/python.exe AI-Data-Center-Analysis_migration_bundle_20260311/tools/m2_mpc_plots.py --out-dir $out_dir
```

答辩 demo：

```powershell
powershell -ExecutionPolicy Bypass -File AI-Data-Center-Analysis_migration_bundle_20260311/tools/m2_mpc_demo.ps1
```

## 论文章节素材定位

- §4.1 工况边界讨论：`AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2_negative_finding_summary.md` + `fig1_w2_head_to_head.png`
- §4.2 MPC robustness 优势：`AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w1_3_robustness_curve_20260503_194137.md` + `fig2_w1_robustness_curve.png`
- §4.3 future work：`AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_w2_negative_finding_summary.md` 第 5 段
- 主表汇总：`AI-Data-Center-Analysis_migration_bundle_20260311/analysis/m2f1_thesis_main_table.md`

## 已知 limitations

- MPC 在 Jiangsu TOU + 当前 chiller 部分负载效率假设下不展现 cost saving；W2 trainlike 与 W2-B official_ood 双 batch 均验证 baseline 在 cost / PUE / comfort 三维全胜
- PV 6 MWp 峰值小于数据中心负载，SCR 100% 是物理饱和；TES 不能进一步提升 PV 自消纳率
- W1 robustness curve 显示 MILP 在 σ ≤ 0.10 基本鲁棒，σ=0.20 出现拐点失守

## future work hooks

- BC warm-start：`AI-Data-Center-Analysis_migration_bundle_20260311/tools/m2_tes_bc.py` 已有 BC head loss 框架，M2-G1~G3 当前暂停
- 多站点：调整 `evaluate_m2_rule_baseline.py` 的 `--epw` / `--price-csv` / `--pv-csv` 即可扩展
- chance-constrained MPC：`tools/m2_tes_mpc_oracle.py:plan_tes_action_milp` 是当前 deterministic LP/MILP 扩展点，后续可加入 stochastic MPC + chance constraint

## 协议运行时清理（毕业后）

- MCP scheduled task: `w2-w3-orchestrator-wake`（跨会话）
- Windows Task Scheduler: `ClaudeCodexPoll`（`poll_codex.ps1`）
- 删除命令见 `agent_comms/README.md`
