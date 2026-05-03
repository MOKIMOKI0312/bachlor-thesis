# M2-F1 TES MPC-lite Technical Route

Date: 2026-05-02

## Route Change

M2-F1 mainline changes from pure RL exploration to a two-step MPC-lite route:

1. M1 TES-only MPC oracle proves the unchanged EnergyPlus TES plant can execute charge/discharge inventory behavior under trainlike evaluation.
2. M2 supervisory MPC-lite packages that controller as a reportable baseline with stable monitor/result artifacts.

RL is downgraded to comparison and optional auxiliary training. It can still be used later for BC/IL warm-start or a learned-policy comparison, but it is not the main mechanism proof.

## Implementation Boundary

The implementation keeps:

- `DRL_DC_training.epJSON` and trainlike `ITE_Set=0.45` by default;
- fixed fan `CRAH_Fan_DRL=1.0`;
- fixed non-TES agent actions `[CT_Pump_DRL=1.0, CRAH_T_DRL=0.0, Chiller_T_DRL=0.0]`;
- fixed-fan 4D exposed action;
- `TESTargetValveWrapper` sign convention: negative means charge cold storage, positive means discharge;
- wrapper-level valve rate limit and SOC guard as final actuator feasibility layer.

It does not:

- train RL;
- run full-year or official OOD main evaluation;
- change EnergyPlus physics, EMS sign convention, weather, TOU price, or PV data;
- delete previous analysis/runs/training_jobs evidence.

## Tools

### `tools/m2_tes_mpc_oracle.py`

Purpose: M1 oracle and shared implementation core.

Default output:

- `runs/m2_tes_mpc_oracle/<tag>/monitor.csv`
- `runs/m2_tes_mpc_oracle/<tag>/result.json`
- `analysis/m2f1_mpc_oracle_summary_202605.csv`
- `analysis/m2f1_mpc_oracle_summary_202605.json`

Key CLI:

```powershell
python tools\m2_tes_mpc_oracle.py --tag m2f1_mpc_oracle_672 --eval-design trainlike --max-steps 672 --out-dir runs\m2_tes_mpc_oracle
```

### `tools/evaluate_m2_mpc_lite.py`

Purpose: M2 supervisory MPC-lite reportable controller.

Default output:

- `runs/m2_mpc_lite/<tag>/monitor.csv`
- `runs/m2_mpc_lite/<tag>/result.json`

Key CLI:

```powershell
python tools\evaluate_m2_mpc_lite.py --tag m2f1_mpc_lite_672 --eval-design trainlike --max-steps 672 --horizon-hours 24 --solver heuristic
```

`--solver scipy-highs` is accepted as an interface but records explicit fallback to heuristic in this first pass.

## Planner Logic

The first-pass deterministic rolling heuristic is deliberately simple:

- high normalized price and sufficient SOC inventory -> discharge;
- low normalized price, near next peak, and SOC has headroom -> charge;
- neutral windows -> hold, with small terminal-SOC correction when far from target;
- infeasible inventory windows are labeled with `tes_mpc_feasible=False` and a reason;
- all commands still pass through `TESTargetValveWrapper` rate limits and SOC guards.

The result is not claimed as optimal MPC. It is a controller-shaped MPC-lite/oracle that proves the mechanism and creates a stable reportable baseline.

## Gate

The M2-F1 trainlike 672-step gate is:

- `comfort < 3%`
- `guard < 5%`
- `charge_window_sign_rate >= 0.80`
- `low_price_discharge_fraction <= 0.10`
- `charge_window_valve_mean < -0.05`
- `discharge_window_valve_mean > 0.05`
- `delta_soc_prepeak > 0`
- `delta_soc_peak < 0`

The charge-window sign and pre-peak SOC delta are scoped to feasible low-price pre-peak windows, because a full TES tank at episode start is not a physically valid charge opportunity. The monitor preserves infeasible rows and reasons for auditability.

## Current Validation Results

| Run | Controller | Steps | Gate | Comfort % | Guard % | Charge sign | Low-price discharge | Charge valve | Discharge valve | Delta pre-peak | Delta peak | PUE | Cost USD |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `m2f1_mpc_oracle_96` | `mpc_oracle` | 96 | expected fail on charge-window due initial full SOC | 1.0417 | 0.0 | null | 0.0 | 0.0 | 0.8061 | null | 0.0943 | 1.1874 | 17826.90 |
| `m2f1_mpc_oracle_672` | `mpc_oracle` | 672 | PASS | 0.8929 | 0.0 | 1.0 | 0.0 | -0.5446 | 0.5252 | 0.2503 | -0.1766 | 1.2596 | 129267.72 |
| `m2f1_mpc_lite_672` | `mpc_lite` | 672 | PASS | 0.8929 | 0.0 | 1.0 | 0.0 | -0.5446 | 0.5252 | 0.2503 | -0.1766 | 1.2596 | 129267.72 |

## Next Stage

P1c is not implemented in this milestone. The low-risk next step is to extend `m2_tes_bc.py` to accept `tes_mpc` label source using the oracle monitor schema, while keeping default behavior unchanged and requiring final learned-policy evaluation without runtime planner calls.
