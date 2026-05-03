# M2-F1 MPC-lite Feasibility Check

Date: 2026-05-02

## Checks Run

```powershell
python -m py_compile tools\m2_tes_mpc_oracle.py tools\evaluate_m2_mpc_lite.py tools\m2_validate_tes_failure_modes.py tools\m2_tes_bc.py
python tools\m2_tes_mpc_oracle.py --tag m2f1_mpc_oracle_96 --eval-design trainlike --max-steps 96 --out-dir runs\m2_tes_mpc_oracle
python tools\m2_tes_mpc_oracle.py --tag m2f1_mpc_oracle_672 --eval-design trainlike --max-steps 672 --out-dir runs\m2_tes_mpc_oracle
python tools\evaluate_m2_mpc_lite.py --tag m2f1_mpc_lite_672 --eval-design trainlike --max-steps 672 --horizon-hours 24 --solver heuristic
```

The first oracle run initially exposed a missing `pyenergyplus` path in the active shell. The new oracle script now auto-discovers local EnergyPlus installs under the user home and sets `EPLUS_PATH`/`ENERGYPLUS_PATH` for this process only.

## Result Files

| Artifact | Path |
|---|---|
| Oracle 96 result | `runs/m2_tes_mpc_oracle/m2f1_mpc_oracle_96/result.json` |
| Oracle 96 monitor | `runs/m2_tes_mpc_oracle/m2f1_mpc_oracle_96/monitor.csv` |
| Oracle 672 result | `runs/m2_tes_mpc_oracle/m2f1_mpc_oracle_672/result.json` |
| Oracle 672 monitor | `runs/m2_tes_mpc_oracle/m2f1_mpc_oracle_672/monitor.csv` |
| MPC-lite 672 result | `runs/m2_mpc_lite/m2f1_mpc_lite_672/result.json` |
| MPC-lite 672 monitor | `runs/m2_mpc_lite/m2f1_mpc_lite_672/monitor.csv` |
| Summary CSV | `analysis/m2f1_mpc_oracle_summary_202605.csv` |
| Summary JSON | `analysis/m2f1_mpc_oracle_summary_202605.json` |

## Gate Results

| Metric | Gate | Oracle 672 | MPC-lite 672 |
|---|---:|---:|---:|
| `comfort` | `< 3%` | 0.8929 | 0.8929 |
| `guard` | `< 5%` | 0.0 | 0.0 |
| `charge_window_sign_rate` | `>= 0.80` | 1.0 | 1.0 |
| `low_price_discharge_fraction` | `<= 0.10` | 0.0 | 0.0 |
| `charge_window_valve_mean` | `< -0.05` | -0.5446 | -0.5446 |
| `discharge_window_valve_mean` | `> 0.05` | 0.5252 | 0.5252 |
| `delta_soc_prepeak` | `> 0` | 0.2503 | 0.2503 |
| `delta_soc_peak` | `< 0` | -0.1766 | -0.1766 |

Both 672-step runs pass the M2-F1 mechanism gate.

## Interpretation

The unchanged trainlike EnergyPlus/TES plant can execute the desired TES inventory behavior when given an explicit anticipatory controller. This removes the main ambiguity from the previous pure-RL failures: the mechanism is reachable; the problem was learning/credit assignment, not an impossible EMS/TES sign or guard configuration.

The first-pass MPC-lite controller is intentionally heuristic. Its scientific value is that it is transparent, auditable, and bounded:

- it records intended target and actual valve separately;
- it records infeasible charge/discharge opportunities instead of hiding them;
- it uses fixed non-TES controls so the TES mechanism is isolated;
- it provides a baseline for later RL/BC comparison.

## Risks

- The solver interface is not yet a real LP/MILP optimizer. `scipy-highs` is an explicit fallback/future hook.
- The 96-step window starts with full SOC, so charge-window metrics are not meaningful there; 672-step gate is the main validation.
- P1c BC integration was intentionally not implemented to avoid changing training behavior in the same milestone as the new controller baseline.
