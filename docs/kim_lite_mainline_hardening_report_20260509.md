# Kim-lite Relaxed Mainline Report

Date: 2026-05-09  
Branch: `codex/kim-lite-mainline-hardening`  
Result root: `results/kim_lite_mainline_hardening_20260509/`

## Summary

This report fixes the thesis-facing interpretation of the Kim-lite work. The main paper result is now explicitly:

```text
paper_like_mpc_tes_relaxed
```

The main Kim-lite experiments use LP-relaxed plant dispatch to represent an aggregated continuously modulating chiller plant. These results are suitable for explaining TES scheduling mechanisms under TOU, critical peak, signed valve ramp, and peak-cap scenarios. They are not strict binary chiller-start/stop MILP results.

EnergyPlus online results are retained as I/O coupling diagnostics. They verify `TES_Set` and `Chiller_T_Set` actuator writes and echo checks, but they are not final energy-saving evidence because current MPC rows fail the temperature-safety comparison.

## Validation

Commands executed:

```powershell
python -m mpc_v2.scripts.run_kim_lite_matrix --phase phase_b_attribution --output-root results/kim_lite_mainline_hardening_20260509
python -m mpc_v2.scripts.run_kim_lite_matrix --phase phase_c_tou --output-root results/kim_lite_mainline_hardening_20260509
python -m mpc_v2.scripts.run_kim_lite_matrix --phase phase_d_peakcap --output-root results/kim_lite_mainline_hardening_20260509
python -m mpc_v2.scripts.run_kim_lite_matrix --phase phase_e_signed_valve --output-root results/kim_lite_mainline_hardening_20260509
python -m Nanjing-DataCenter-TES-EnergyPlus.controller.energyplus_mpc.run_io_coupling_matrix --output-root results/energyplus_mpc_io_coupling_matrix_20260509 --seasons winter,spring,summer,autumn --days 30
```

Final validation status is recorded in `CHANGELOG.md`.

## Phase B Attribution

| Controller | Cost | Mode integrality | Fractionality hours | Signed ramp violations | Max signed du | TES arbitrage spread |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| direct_no_tes | 39049.67 | fixed | 0.00 | 0 | 0.00 | 0.000 |
| mpc_no_tes | 38903.67 | relaxed | 24.00 | 0 | 0.00 | 0.000 |
| storage_priority_tes | 38666.16 | fixed | 0.00 | 8 | 1.00 | 0.117 |
| storage_priority_neutral_tes | 38734.12 | fixed | 0.00 | 11 | 1.00 | 0.101 |
| paper_like_mpc_tes_relaxed | 38672.60 | relaxed | 13.25 | 0 | 0.25 | 0.064 |

Interpretation:

- `paper_like_mpc_tes_relaxed` produces `231.07` CNY saving relative to relaxed `mpc_no_tes`.
- Signed ramp is part of the main method and has zero violations.
- The relaxed fractionality diagnostics are intentionally reported because they bound the interpretation: results represent continuous plant dispatch, not strict unit commitment.

## Phase C TOU / Critical Peak

| Scenario | no-TES relaxed cost | TES-MPC relaxed cost | TES saving | TES arbitrage spread | TES discharge during CP | Fractionality hours |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| flat | 38945.74 | 38947.76 | -2.02 | ~0.000 | 0.00 | 21.50 |
| base | 38903.67 | 38672.60 | 231.07 | 0.064 | 578.59 | 13.25 |
| base_cp20 | 39410.09 | 39181.83 | 228.26 | 0.064 | 1274.31 | 13.50 |
| high_spread | 40366.55 | 39911.94 | 454.61 | 0.125 | 578.59 | 6.75 |
| high_spread_cp20 | 40751.33 | 40297.18 | 454.15 | 0.128 | 613.13 | 7.00 |

Interpretation:

- TES value increases when TOU spread increases.
- `base_cp20` increases CP-window discharge relative to `base`, but total saving changes little because the configured CP window is short and broader TOU arbitrage already dominates dispatch.
- The flat case has near-zero arbitrage spread, so the relaxed TES-MPC result should not be described as economically beneficial there.

## Phase D Peak-Cap

Peak-cap success is evaluated by slack, not by energy cost:

```text
peak_cap_success_flag = peak_slack_max_kw <= 1e-6
TES_peak_cap_help_kwh = peak_slack_kwh(mpc_no_tes) - peak_slack_kwh(paper_like_mpc_tes_relaxed)
```

| Cap ratio | no-TES slack kWh | TES relaxed slack kWh | TES help kWh | no-TES max slack | TES max slack | TES max help |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 0.99 | 1887.23 | 31.64 | 1855.60 | 183.20 | 99.71 | 83.50 |
| 0.97 | 6726.95 | 4157.36 | 2569.59 | 549.61 | 543.40 | 6.21 |
| 0.95 | 12035.20 | 9468.50 | 2566.70 | 916.01 | 911.85 | 4.16 |

Interpretation:

- Under relaxed dispatch, TES reduces both slack energy and max slack in the shown cap cases.
- These results still do not prove strict binary peak-cap success.
- Peak-cap conclusions should be written as relaxed proxy sensitivity results.

## EnergyPlus I/O Coupling Diagnostic

The EnergyPlus I/O matrix has:

```text
result_role = io_coupling_diagnostic
```

Observed diagnostic status:

- `TES_Set` echo mismatch: 0
- `Chiller_T_Set` echo mismatch: 0
- `fallback_count`: 0
- `io_success_flag`: true for all controller rows
- `temperature_safe_flag`: false for MPC rows
- `cost_comparison_valid`: false for MPC rows

Therefore EnergyPlus online rows should only be used to state:

```text
I/O coupling works, but the current online control surface is not yet temperature-safe economic control.
```

They should not be used to claim validated online MPC cost saving.

## Thesis Impact

The thesis draft was updated in this stage because the relaxed plant dispatch and EnergyPlus diagnostic role affect the method and result interpretation. Bibliography was not updated because no new citation was added.
