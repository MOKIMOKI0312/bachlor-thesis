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

## Unreleased

后续版本建议优先处理：

- 加强温度约束满足能力。
- 降低 TES 短周期切换。
- 构造能体现 PV 弃光与 TES 吸纳价值的场景。
- 增加 rule-based TES baseline。
- 扩展到 7 天或典型周仿真。
- 生成论文用图表和表格。
