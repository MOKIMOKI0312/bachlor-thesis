# PV 信号端到端验收（Phase B）

- Generated: by `tools/m1/verify_pv.py`
- CSV path: `C:\Users\18430\Desktop\毕业设计代码\.claude\worktrees\integrate-all-fixes\AI-Data-Center-Analysis_migration_bundle_20260311\Data\pv\CHN_Nanjing_PV_6MWp_hourly.csv`
- 计数：PASS=4, WARN=0, FAIL=0, SKIP=0

| Check | Status | Threshold | Evidence |
|-------|--------|-----------|----------|
| B1_csv_exists | PASS | CSV file exists at expected path | `{"path": "C:\\Users\\18430\\Desktop\\毕业设计代码\\.claude\\worktrees\\integrate-all-fixes\\AI-Data-Center-Analysis_migration_bundle_20260311\\Data\\pv\\CHN_Nanjing_PV_6MWp_hourly.csv", "size_bytes": 232984}` |
| B2_csv_schema | PASS | 8760 rows, power_kw column, nightly≈0, summer>winter | `{"rows": 8760, "columns": ["timestamp", "power_kw"], "peak_kw": 5060.16, "annual_kwh": 7143351.9, "yield_kwh_per_kwp": 1190.5586500000002, "night_mean_kw_0_5h": 0.0, "monthly_peaks_kw": [4751.5, 5060.2, 5001.3, 5006.6, 4629.2, 4218.7, 3833....` |
| B3_wrapper_instantiation | PASS | signals in spec range, 3-dim tail correctly attached | `{"obs_shape": [6], "n_steps_swept": 24, "pv_ratio_range": [0.0, 0.6582800149917603], "pv_slope_range": [-0.7603557109832764, 0.7481871247291565], "pv_ttp_range": [0.0, 1.0], "info_pv_kw_range": [0.0, 3949.679931640625], "obs_var_tail": ["pv...` |
| B4_yearlong_peak_alignment | PASS | median peak hour ∈ [9, 14]; hour 12 in top quartile ≥ 70% of days | `{"valid_days": 365, "peak_hour_mean": 11.476712328767123, "peak_hour_median": 11.0, "hour12_in_top_quartile_ratio": 0.9808219178082191, "issues": []}` |
