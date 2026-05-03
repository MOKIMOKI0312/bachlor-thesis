# M2 F1 RL-Cost 30ep Stochastic Diagnostic - 2026-04-28

## Implementation
- No tracked source/model files were modified; training was not started.
- Temporary script: `tmp/m2_stochastic_eval_diag_20260428.py`.
- It imports `tools.evaluate_m2.evaluate()` and monkeypatches `DSAC_T.load` in-process so the existing evaluation loop calls a proxy whose `predict()` forces `deterministic=False`.
- Python: `C:\Users\18430\.conda\envs\aidc-py310\python.exe`. Env vars were set only in the launched PowerShell process: `EPLUS_PATH`, `PYTHONPATH`, `PATH`, `KMP_DUPLICATE_LIB_OK`.

## Metric Comparison
| seed | policy | price_response | soc_daily_amp | valve_sat | comfort_pct | valve_low_mean | valve_high_mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| seed1 | det | 0.045230 | 0.042924 | 0.876545 | 0.059930 | -0.963424 | -0.918194 |
| seed1 | stoch | 0.045897 | 0.053651 | 0.875746 | 0.074199 | -0.962482 | -0.916584 |
| seed3 | det | 0.000313 | 0.000605 | 0.998944 | 0.019977 | -0.999605 | -0.999291 |
| seed3 | stoch | 0.000321 | 0.000605 | 0.998944 | 0.019977 | -0.999605 | -0.999283 |
| seed4 | det | -0.371014 | 0.717016 | 0.450786 | 100.000000 | 0.095764 | -0.275250 |
| seed4 | stoch | -0.400147 | 0.725046 | 0.444422 | 100.000000 | 0.115119 | -0.285028 |

## Action / HVAC Abnormal Summary
- seed1: monitor `C:\Users\18430\Desktop\毕业设计代码\AI-Data-Center-Analysis_migration_bundle_20260311\runs\eval\run-017\episode-001\monitor.csv`
  - HVAC near-bound fractions: CRAH_Fan_DRL=0.999971, CT_Pump_DRL=0.000000, CRAH_T_DRL=0.000000, Chiller_T_DRL=0.328929
  - TES abs>=0.95=0.875746, TES mean=-0.941002, guard_clipped=0.027882
  - action_nan=True (monitor first-row artifact), temp>25 frac=0.000742, temp>35 count=2
- seed3: monitor `C:\Users\18430\Desktop\毕业设计代码\AI-Data-Center-Analysis_migration_bundle_20260311\runs\eval\run-018\episode-001\monitor.csv`
  - HVAC near-bound fractions: CRAH_Fan_DRL=0.629805, CT_Pump_DRL=0.000000, CRAH_T_DRL=0.000000, Chiller_T_DRL=0.690562
  - TES abs>=0.95=0.998944, TES mean=-0.999597, guard_clipped=0.000029
  - action_nan=True (monitor first-row artifact), temp>25 frac=0.000200, temp>35 count=2
- seed4: monitor `C:\Users\18430\Desktop\毕业设计代码\AI-Data-Center-Analysis_migration_bundle_20260311\runs\eval\run-019\episode-001\monitor.csv`
  - HVAC near-bound fractions: CRAH_Fan_DRL=0.000000, CT_Pump_DRL=0.954168, CRAH_T_DRL=0.010274, Chiller_T_DRL=0.000029
  - TES abs>=0.95=0.444422, TES mean=-0.127963, guard_clipped=0.178163
  - action_nan=True (monitor first-row artifact), temp>25 frac=1.000000, temp>35 count=35041

## Conclusion
- Stochastic eval does not materially diverge from deterministic eval for seed1/seed3; seed3 is effectively identical.
- seed4 stochastic eval still has 100% comfort violation. Stochastic sampling does not rescue the catastrophic policy.
- Therefore the stochastic-vs-deterministic evaluation mismatch hypothesis is not confirmed as the primary failure. What is confirmed is policy/action saturation: deterministic means are saturated, and stochastic samples are concentrated enough that the same saturated behavior remains.

## Next Steps
- Do not switch reported evaluation to stochastic as a fix; it would not change pass/fail materially and would add variance.
- Add model selection gates using deterministic validation: comfort constraint, valve saturation ceiling, minimum SOC daily amplitude, and price-response sign/magnitude.
- For retraining, prioritize TES teacher/valve shaping and valve saturation penalty; seed1/seed3 show persistent charge saturation with negligible SOC amplitude.
- For seed4-style failures, add stronger comfort safety/beta handling or action safety constraints before optimizing arbitrage metrics.
