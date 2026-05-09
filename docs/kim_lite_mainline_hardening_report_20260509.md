# Kim-lite Mainline Hardening Report

Date: 2026-05-09  
Branch: `codex/kim-lite-mainline-hardening`  
Result root: `results/kim_lite_mainline_hardening_20260509/`

## Summary

This run promotes signed valve ramp control into the Kim-lite proxy mainline. Phase B/C/D `paper_like_mpc_tes` cases now enforce the signed ramp constraint, and Phase D peak-cap evaluation is reported with slack-first metrics rather than energy cost alone.

EnergyPlus online results remain a feasibility and risk diagnostic layer. The existing I/O-coupling matrix proves `TES_Set` and `Chiller_T_Set` can be written with zero echo mismatch, but it still fails the temperature-safety criterion and is not used as a thesis-grade energy-saving result.

## Validation

Commands executed:

```powershell
python -m pytest -q
python -m mpc_v2.scripts.run_kim_lite_matrix --phase phase_b_attribution --output-root results/kim_lite_mainline_hardening_20260509
python -m mpc_v2.scripts.run_kim_lite_matrix --phase phase_c_tou --output-root results/kim_lite_mainline_hardening_20260509
python -m mpc_v2.scripts.run_kim_lite_matrix --phase phase_d_peakcap --output-root results/kim_lite_mainline_hardening_20260509
python -m mpc_v2.scripts.run_kim_lite_matrix --phase phase_e_signed_valve --output-root results/kim_lite_mainline_hardening_20260509
python -m mpc_v2.scripts.audit_kim_lite_results --root results/kim_lite_mainline_hardening_20260509
```

Result:

```text
pytest -> 51 passed
Phase B/C/D/E generation -> completed
Kim-lite audit -> passed
```

## Phase B Attribution

| Controller | Cost | Signed ramp violations | Max signed du | TES arbitrage spread |
| --- | ---: | ---: | ---: | ---: |
| direct_no_tes | 39049.67 | 0 | 0.00 | 0.000 |
| mpc_no_tes | 39049.67 | 0 | 0.00 | 0.000 |
| storage_priority_tes | 38666.16 | 8 | 1.00 | 0.117 |
| storage_priority_neutral_tes | 38734.12 | 11 | 1.00 | 0.101 |
| paper_like_mpc_tes | 38712.05 | 0 | 0.25 | 0.064 |

Interpretation:

- The Kim-lite proxy still shows TES value under the external-load boundary.
- Signed ramp is now enforced in the `paper_like_mpc_tes` mainline.
- The rule baselines remain useful diagnostics, but they violate the signed valve ramp limit and should not be described as actuator-smooth MPC-equivalent controls.

## Phase C TOU / Critical Peak

The Phase C `paper_like_mpc_tes` rows use relaxed single-mode optimization because the horizon's feasible chiller-output range makes only one plant mode reachable. Signed ramp remains enforced and all `paper_like_mpc_tes` rows have zero ramp violations.

| Scenario | no-TES cost | TES-MPC cost | TES saving | TES arbitrage spread | TES discharge during CP |
| --- | ---: | ---: | ---: | ---: | ---: |
| flat | 39092.39 | 38947.76 | 144.62 | ~0.000 | 0.00 |
| base | 39049.67 | 38672.60 | 377.07 | 0.064 | 578.59 |
| base_cp20 | 39558.14 | 39181.83 | 376.32 | 0.064 | 1274.31 |
| high_spread | 40517.53 | 39911.94 | 605.59 | 0.125 | 578.59 |
| high_spread_cp20 | 40903.85 | 40297.18 | 606.67 | 0.128 | 613.13 |

Interpretation:

- Larger TOU spread increases TES value.
- Critical peak uplift changes dispatch behavior: `base_cp20` roughly doubles CP-window TES discharge compared with `base`.
- The CP uplift does not strongly increase total saving because the configured CP window is short and TES also arbitrages broader TOU differences.

## Phase D Peak-Cap

Peak-cap success is now evaluated by slack:

```text
peak_cap_success_flag = peak_slack_max_kw <= 1e-6
TES_peak_cap_help_kwh = peak_slack_kwh(mpc_no_tes) - peak_slack_kwh(paper_like_mpc_tes)
```

Strict-track result:

| Cap ratio | no-TES slack kWh | TES slack kWh | TES help kWh | no-TES max slack | TES max slack | TES max help |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 0.99 | 1910.37 | 119.22 | 1791.14 | 183.84 | 106.55 | 77.29 |
| 0.97 | 6773.37 | 3589.54 | 3183.83 | 551.52 | 973.33 | -421.82 |
| 0.95 | 12110.52 | 8868.05 | 3242.47 | 919.20 | 1407.45 | -488.25 |

Interpretation:

- TES helps reduce total slack energy under all tight strict caps shown above.
- TES reduces max slack for the mild 0.99 cap.
- Under tighter 0.97 and 0.95 caps, TES lowers total slack energy but worsens max slack. This should be reported as a tradeoff, not a universal peak-cap success.
- Energy cost remains a secondary metric and must not be used alone to claim peak-cap success.

## EnergyPlus I/O Coupling Position

The existing EnergyPlus I/O matrix remains useful for interface verification:

- `TES_Set` echo mismatch: 0
- `Chiller_T_Set` echo mismatch: 0
- `fallback_count`: 0
- 16/16 cases completed

However, all MPC rows still have:

```text
cost_comparison_valid = false
```

because temperature degree-hours or maximum zone temperature worsen relative to same-season `no_mpc`. Therefore, EnergyPlus online results should be described as:

```text
I/O coupling feasibility and temperature-risk diagnostic.
```

They should not be described as:

```text
validated EnergyPlus online MPC energy-saving results.
```

## Thesis Impact

No thesis draft or bibliography file was updated in this run.

Recommended thesis positioning after user approval:

- Main result layer: Kim-lite proxy, signed-ramp TES-MPC, TOU sensitivity, and peak-cap slack diagnostics.
- Verification layer: EnergyPlus Runtime API I/O coupling feasibility plus unresolved comfort-safety limitation.

## Review Package

The GPT Pro review package generated for this run is:

```text
_review_packages/kim_lite_mainline_hardening_review_20260509.zip
```

It includes complete Kim-lite source/config/tests/results and EnergyPlus summary-level I/O coupling artifacts. It intentionally excludes EnergyPlus timestep-level `monitor.csv`, `observation.csv`, `mpc_action.csv`, and `solver_log.csv`.
