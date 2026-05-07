# China TOU/DR 1-Month Matrix Results

冻结日期：2026-05-07
代码口径：`mpc_v2` synthetic/replay MILP-MPC，不是 EnergyPlus online co-simulation。
episode 长度：30 days = 2880 steps，15 min/step，起点 `2025-07-01 00:00:00`。

## Contents

- `raw/`：正式矩阵 138 个 run 的原始输出，每个目录包含 `config_effective.yaml`、`monitor.csv`、`timeseries.csv`、`events.csv`、`solver_log.csv`、`summary.csv`、`episode_summary.json`。
- `validation_summary.csv/json`：正式矩阵汇总。
- `analysis/summary.csv/json`：分析脚本汇总副本。
- `analysis/paired_comparisons.csv`：`mpc_no_tes` vs `mpc` paired episode 对比。
- `analysis/total_cost_by_scenario.png`
- `analysis/solver_time_p95_by_scenario.png`
- `analysis/tou_cost_curve.png`
- `analysis/tou_arbitrage_spread_curve.png`
- `analysis/dr_event_profile.png`
- `analysis/peak_reduction_cost_tradeoff.png`
- `reports/summary_report.md`：总报告，含全矩阵统计、分类汇总、控制器汇总、高温度违约 case 和 138 个 case 报告索引。
- `reports/cases/<scenario_id>/report.md`：每个结果的单独报告。
- `reports/cases/<scenario_id>/*.png`：每个结果 4 张 MATLAB 风格图，分别为 grid/PV/power、TES/SOC、temperature constraints、tariff/solver trace。
- `config/`：生成矩阵 YAML 和基线配置快照。
- `pilot/`：138 个 24h pilot 的汇总与分析，用于正式运行前检查。

## Commands

```powershell
python -m pytest -q
python -m mpc_v2.scripts.generate_china_matrix --profile pilot --output mpc_v2/config/generated_china_matrix_pilot.yaml
python -m mpc_v2.scripts.generate_china_matrix --profile month --output mpc_v2/config/generated_china_matrix_month.yaml
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenarios mpc_v2/config/generated_china_matrix_pilot.yaml --scenario-set china_all_full --output-dir runs/china_tou_dr_pilot_20260506
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenarios mpc_v2/config/generated_china_matrix_month.yaml --scenario-set china_all_full --output-dir runs/china_tou_dr_month_20260506 --max-workers 8 --resume-existing
python -m mpc_v2.scripts.analyze_results --input-dir runs/china_tou_dr_month_20260506 --output-dir runs/china_tou_dr_month_20260506/analysis
python -m mpc_v2.scripts.generate_result_reports --result-dir results/china_tou_dr_matrices_20260506
```

## Matrix

- TOU screening：40 runs。
- TOU full compare：32 runs。
- Peak-cap：24 runs。
- DR event：18 runs。
- Robustness：24 runs。
- Total：138 runs。
- Per-case reports：138。
- MATLAB-style figures：552。

## Validation Summary

- Completed runs：138 / 138。
- `fallback_count` total：1；唯一 fallback case 为 `robust_dr_day_ahead_10_h24_mpc_tes`，`feasible_rate = 1.0`。
- Minimum `feasible_rate`：1.0。
- Minimum `optimal_rate`：0.999653。
- Maximum `solve_time_p95_s`：3.7692 s。
- Maximum temperature violation：430.664 degree-hours，来自最严 `peakcap_r0p95_eta20_mpc_no_tes`；对应 TES-MPC peak-cap cases 的温度违约略低但仍较高。

## Main Results

Paired comparison uses matched scenario IDs and reports `Cost(mpc_no_tes) - Cost(mpc)`:

- `n_pairs = 61`
- mean saving：518.81 CNY/month
- median saving：152.74 CNY/month
- bootstrap CI：313.84 to 737.38 CNY/month

TOU screening:

- `mpc` mean total cost：1,291,919.83 CNY/month。
- `mpc_no_tes` mean total cost：1,292,366.36 CNY/month。
- paired mean saving：446.52 CNY/month；range：-741.55 to 2,447.99 CNY/month。
- `mpc` mean TES arbitrage price spread：148.81 CNY/MWh。

TOU full compare:

- `mpc` mean total cost：1,296,598.71 CNY/month。
- `mpc_no_tes` mean total cost：1,297,248.94 CNY/month。
- `rbc` mean total cost：1,347,132.29 CNY/month。
- `no_tes` mean total cost：1,348,448.17 CNY/month。

Peak-cap:

- Baseline cap was derived from no-cap `mpc_no_tes` peak, then scaled by `r_cap`。
- Achieved mean peak follows the cap exactly in the tested cases: 21090.0, 20879.1, 20457.3, 20035.5 kW for `r_cap = 1.00, 0.99, 0.97, 0.95`。
- `peak_slack_max_kw` is numerically zero in all peak-cap cases.
- Strict `r_cap = 0.95` causes large temperature violation in both `mpc_no_tes` and `mpc`; this is a feasibility/comfort tradeoff boundary, not a recommended operating point.

DR event:

- Each DR scenario triggers one event only.
- Requested reduction per event: 1900, 3800, 5700 kWh for `r_DR = 0.05, 0.10, 0.15`。
- Served reduction is 2060.78 kWh in the current proxy setting.
- Response rate: 1.0846, 0.5423, 0.3615 for `r_DR = 0.05, 0.10, 0.15`。
- DR revenue is reported as scenario-estimated value only; real market settlement rules are not verified.

## Thesis Boundary

- These results can support a synthetic/replay MILP-MPC chapter for China TOU/DR scenarios.
- They cannot be described as EnergyPlus co-simulation or as verified market settlement.
- TES incremental benefit must be reported as `mpc_no_tes` to `mpc`, separate from the direct baseline to MPC benefit.
- Strict peak-cap cases show comfort tradeoff and should be discussed as constrained stress tests.
