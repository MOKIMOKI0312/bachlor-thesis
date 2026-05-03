# M2-F1 Method Takeaways from Local MPC/TES Literature

Date: 2026-05-03

## Gate Decision

The local PDF gate supports a TES-only rolling optimizer before further RL work. The core reason is structural: TES arbitrage is an inventory problem with delayed value, SOC bounds, charge/discharge mode constraints, and forecasted tariff/load conditions. A one-step reward or unconstrained continuous policy can discharge at attractive moments but still miss the required pre-peak low-price charging behavior.

## Evidence-To-Implementation Mapping

| Evidence group | Method takeaway | M2-F1 implementation decision |
|---|---|---|
| Zhu 2023 chiller + cold storage MPC/MILP | Use rolling horizon and execute only the first action; report model mismatch and storage feasibility. | `scipy-highs` runs a 24 h rolling LP at 15 min steps and executes only the first TES target. |
| Zhu 2024 hybrid cooling MPC/MILP | Cold storage needs daily inventory recovery and explicit storage/release constraints. | Optimizer includes terminal SOC penalty, SOC schedule penalty, bounds, rate limit, and charge/discharge relaxation. |
| Zhu 2024 DMPC uncertainty | Separate operating-state decisions from parameter uncertainty and expose sensitivity/mismatch. | M2-F1 keeps the EnergyPlus plant fixed and records SOC dynamics source, slack, predicted SOC, and solver status. |
| Gao 2025 data-corrected LHTES MPC | TES model parameters must be traceable or corrected from data; do not hand-fill efficiency. | SOC gains are calibrated from existing oracle monitor, or supplied by CLI; fallback is explicit and recorded. |
| Xiang 2025 free cooling + CTES MPC | Forecast horizon and objective must be explicit; PUE/TOU optimization is controller-side, not plant-side. | Forecasted price windows are generated inside the controller; no EnergyPlus, weather, TOU, PV, or workload change. |
| Tarragona 2021 TES MPC review | Common TES MPC horizons are often 12-24 h; objectives are cost/peak/CO2 and constraints are central. | Default `--horizon-hours 24`; result JSON lists objective terms and constraints. |
| Jeong 2024 ESS arbitrage RL | Storage actions are mode-like; continuous control can stick at SOC boundaries and clipping must be visible. | Monitor records charge/hold/discharge labels, actual valve, guard clipping, actual SOC violation, and slack diagnostics. |
| Wang et al. ICCPS22 safe DRL | Safety/feasibility wrappers and post-hoc correction should be explicitly reported. | M2-F1 keeps wrapper guard as final plant feasibility layer and reports whether controller created infeasible requests. |
| Kahil 2025 RL review and Sinergym 2025 | Benchmark clarity and reproducible monitor/result artifacts are necessary. | `controller_family`, `controller_type_detail`, `solver_used`, `solver_status_counts`, monitor CSV, and result JSON are required outputs. |
| Guo 2024 DCI-SAC, Li 2019 DRL, ATES/GESS delayed-reward, PBRS | RL remains relevant, but delayed storage behavior needs physics/inventory guidance first. | No RL training in this milestone; optimizer/oracle can later provide labels for BC or comparison. |

## Adopted MPC Shape

The selected controller is not a full data-center chiller/free-cooling MILP. It is a scoped TES-only rolling LP because the current thesis blocker is whether the unchanged M2-F1 plant can execute a TES mechanism gate:

- charge or at least hold in low-price windows, especially low-price pre-peak windows;
- discharge in high-price windows while respecting SOC lower reserve;
- keep non-TES HVAC actions fixed so TES behavior is isolated;
- expose both optimizer prediction and EnergyPlus actual response.

## Constraints Added After Review

The review found the first LP was real but not gate-aligned because it could discharge in low-price windows. The controller now adds:

- low-price windows: TES discharge upper bound is zero;
- low-price pre-peak with SOC headroom: current action has a minimum charge bound only when SOC and rate limits make it feasible;
- high-price windows: TES charge upper bound is zero;
- high-price with SOC inventory: current action has a minimum discharge bound only when SOC and rate limits make it feasible;
- SOC schedule: lower target during high-price discharge, headroom target before future pre-peak charging, higher target during low-price pre-peak charging;
- high-penalty SOC bound slack, reported rather than hidden, to keep rolling LP feasible when the EnergyPlus plant starts outside preferred bounds.
- actual SOC safety feedback: conservative planning bounds protect SOC before strict wrapper bounds are reached, and strict out-of-bound recovery is labeled as `safety_recovery` so raw and economic low-price discharge are reported separately.

## What Is Not Adopted

- Full chiller sequencing, free-cooling mode optimization, pump/fan setpoint optimization, or workload action.
- ATES/waste heat recovery, multi-agent BtG decomposition, or data-corrected LHTES EKF model.
- Any EnergyPlus physics, water-tank, site, weather, TOU/PV, or workload modification.
- Any claim that comfort risk is already modeled in the LP. It remains a zero-weight placeholder unless a traceable thermal risk model is added.

## Reporting Requirements

Every optimizer run must report:

- whether `scipy-highs` truly ran or failed;
- SOC dynamics source and calibration samples;
- objective terms, constraints, and fixed non-TES actions;
- actual SOC bound violation count/fraction/first step;
- rolling LP slack diagnostics: `soc_hi_slack_sum/max/first_step`, `soc_lo_slack_sum/max/first_step`, `terminal_abs_slack`, `predicted_soc_1/n_min/max`, and `solver_status_counts`.
