# China TOU/DR Matrix Full Result Report

- Result root: `results\china_tou_dr_matrices_20260506`
- Report root: `results\china_tou_dr_matrices_20260506\reports`
- Case reports: 138
- Figures generated: 552
- Plot style: MATLAB-like color order, white axes, grid lines, compact time axis.

## Overall

- Completed runs: 138
- Fallback count total: 1
- Minimum feasible rate: 1.000000
- Minimum optimal rate: 0.999653
- Maximum solve time p95: 3.7692 s
- Maximum temperature violation: 430.6639 degree-hours

## Paired TES-MPC Result

| metric     | baseline   | candidate   |   n_pairs |   mean_difference |   median_difference |   ci_low |   ci_high |
|:-----------|:-----------|:------------|----------:|------------------:|--------------------:|---------:|----------:|
| total_cost | mpc_no_tes | mpc         |        61 |           518.814 |             152.736 |  313.837 |   737.383 |

## Category Summary

| category         |   runs |   total_cost_mean |   peak_grid_mean |   temp_violation_max |   fallback_sum |
|:-----------------|-------:|------------------:|-----------------:|---------------------:|---------------:|
| DR event         |     18 |       1303119.713 |        21090.000 |                0.000 |              0 |
| Peak-cap         |     24 |       1321198.954 |        20615.475 |              430.664 |              0 |
| Robustness       |     24 |       1304331.440 |        21090.000 |                0.568 |              1 |
| TOU full compare |     32 |       1322357.028 |        20847.450 |                0.010 |              0 |
| TOU screening    |     40 |       1292143.096 |        21090.000 |                0.010 |              0 |

## Controller Summary

| controller_type   |   runs |   total_cost_mean |   peak_grid_mean |   temp_violation_mean |   fallback_sum |
|:------------------|-------:|------------------:|-----------------:|----------------------:|---------------:|
| mpc               |     61 |       1302243.785 |        20996.651 |                20.492 |              1 |
| mpc_no_tes        |     61 |       1302762.598 |        20996.651 |                21.142 |              0 |
| no_tes            |      8 |       1348448.169 |        20633.250 |                 0.000 |              0 |
| rbc               |      8 |       1347132.293 |        20576.550 |                 0.000 |              0 |

## Highest Temperature-Violation Cases

| scenario_id                          | controller_type   |   temp_violation_degree_hours |   fallback_count |   total_cost |
|:-------------------------------------|:------------------|------------------------------:|-----------------:|-------------:|
| peakcap_r0p95_eta20_mpc_no_tes       | mpc_no_tes        |                       430.664 |                0 |  1344849.247 |
| peakcap_r0p95_eta5_mpc_no_tes        | mpc_no_tes        |                       429.404 |                0 |  1344903.769 |
| peakcap_r0p95_eta10_mpc_no_tes       | mpc_no_tes        |                       428.999 |                0 |  1344961.857 |
| peakcap_r0p95_eta5_mpc_tes           | mpc               |                       418.004 |                0 |  1344939.353 |
| peakcap_r0p95_eta10_mpc_tes          | mpc               |                       416.337 |                0 |  1345060.583 |
| peakcap_r0p95_eta20_mpc_tes          | mpc               |                       415.577 |                0 |  1345057.862 |
| robust_dr_day_ahead_10_h6_mpc_no_tes | mpc_no_tes        |                         0.568 |                0 |  1314286.410 |
| robust_dr_day_ahead_10_h6_mpc_tes    | mpc               |                         0.095 |                0 |  1311239.861 |
| tou_screen_g1_cp0p2_mild_mpc_no_tes  | mpc_no_tes        |                         0.010 |                0 |  1243001.656 |
| tou_full_base_cp20_mild_mpc_no_tes   | mpc_no_tes        |                         0.010 |                0 |  1243001.656 |

## Case Report Index

| Scenario | Category | Controller | Report |
|---|---|---|---|
| `dr_day_ahead_r0p05_mpc_no_tes` | DR event | mpc_no_tes | [cases/dr_day_ahead_r0p05_mpc_no_tes/report.md](cases/dr_day_ahead_r0p05_mpc_no_tes/report.md) |
| `dr_day_ahead_r0p05_mpc_tes` | DR event | mpc | [cases/dr_day_ahead_r0p05_mpc_tes/report.md](cases/dr_day_ahead_r0p05_mpc_tes/report.md) |
| `dr_day_ahead_r0p15_mpc_no_tes` | DR event | mpc_no_tes | [cases/dr_day_ahead_r0p15_mpc_no_tes/report.md](cases/dr_day_ahead_r0p15_mpc_no_tes/report.md) |
| `dr_day_ahead_r0p15_mpc_tes` | DR event | mpc | [cases/dr_day_ahead_r0p15_mpc_tes/report.md](cases/dr_day_ahead_r0p15_mpc_tes/report.md) |
| `dr_day_ahead_r0p1_mpc_no_tes` | DR event | mpc_no_tes | [cases/dr_day_ahead_r0p1_mpc_no_tes/report.md](cases/dr_day_ahead_r0p1_mpc_no_tes/report.md) |
| `dr_day_ahead_r0p1_mpc_tes` | DR event | mpc | [cases/dr_day_ahead_r0p1_mpc_tes/report.md](cases/dr_day_ahead_r0p1_mpc_tes/report.md) |
| `dr_fast_r0p05_mpc_no_tes` | DR event | mpc_no_tes | [cases/dr_fast_r0p05_mpc_no_tes/report.md](cases/dr_fast_r0p05_mpc_no_tes/report.md) |
| `dr_fast_r0p05_mpc_tes` | DR event | mpc | [cases/dr_fast_r0p05_mpc_tes/report.md](cases/dr_fast_r0p05_mpc_tes/report.md) |
| `dr_fast_r0p15_mpc_no_tes` | DR event | mpc_no_tes | [cases/dr_fast_r0p15_mpc_no_tes/report.md](cases/dr_fast_r0p15_mpc_no_tes/report.md) |
| `dr_fast_r0p15_mpc_tes` | DR event | mpc | [cases/dr_fast_r0p15_mpc_tes/report.md](cases/dr_fast_r0p15_mpc_tes/report.md) |
| `dr_fast_r0p1_mpc_no_tes` | DR event | mpc_no_tes | [cases/dr_fast_r0p1_mpc_no_tes/report.md](cases/dr_fast_r0p1_mpc_no_tes/report.md) |
| `dr_fast_r0p1_mpc_tes` | DR event | mpc | [cases/dr_fast_r0p1_mpc_tes/report.md](cases/dr_fast_r0p1_mpc_tes/report.md) |
| `dr_realtime_r0p05_mpc_no_tes` | DR event | mpc_no_tes | [cases/dr_realtime_r0p05_mpc_no_tes/report.md](cases/dr_realtime_r0p05_mpc_no_tes/report.md) |
| `dr_realtime_r0p05_mpc_tes` | DR event | mpc | [cases/dr_realtime_r0p05_mpc_tes/report.md](cases/dr_realtime_r0p05_mpc_tes/report.md) |
| `dr_realtime_r0p15_mpc_no_tes` | DR event | mpc_no_tes | [cases/dr_realtime_r0p15_mpc_no_tes/report.md](cases/dr_realtime_r0p15_mpc_no_tes/report.md) |
| `dr_realtime_r0p15_mpc_tes` | DR event | mpc | [cases/dr_realtime_r0p15_mpc_tes/report.md](cases/dr_realtime_r0p15_mpc_tes/report.md) |
| `dr_realtime_r0p1_mpc_no_tes` | DR event | mpc_no_tes | [cases/dr_realtime_r0p1_mpc_no_tes/report.md](cases/dr_realtime_r0p1_mpc_no_tes/report.md) |
| `dr_realtime_r0p1_mpc_tes` | DR event | mpc | [cases/dr_realtime_r0p1_mpc_tes/report.md](cases/dr_realtime_r0p1_mpc_tes/report.md) |
| `peakcap_r0p95_eta10_mpc_no_tes` | Peak-cap | mpc_no_tes | [cases/peakcap_r0p95_eta10_mpc_no_tes/report.md](cases/peakcap_r0p95_eta10_mpc_no_tes/report.md) |
| `peakcap_r0p95_eta10_mpc_tes` | Peak-cap | mpc | [cases/peakcap_r0p95_eta10_mpc_tes/report.md](cases/peakcap_r0p95_eta10_mpc_tes/report.md) |
| `peakcap_r0p95_eta20_mpc_no_tes` | Peak-cap | mpc_no_tes | [cases/peakcap_r0p95_eta20_mpc_no_tes/report.md](cases/peakcap_r0p95_eta20_mpc_no_tes/report.md) |
| `peakcap_r0p95_eta20_mpc_tes` | Peak-cap | mpc | [cases/peakcap_r0p95_eta20_mpc_tes/report.md](cases/peakcap_r0p95_eta20_mpc_tes/report.md) |
| `peakcap_r0p95_eta5_mpc_no_tes` | Peak-cap | mpc_no_tes | [cases/peakcap_r0p95_eta5_mpc_no_tes/report.md](cases/peakcap_r0p95_eta5_mpc_no_tes/report.md) |
| `peakcap_r0p95_eta5_mpc_tes` | Peak-cap | mpc | [cases/peakcap_r0p95_eta5_mpc_tes/report.md](cases/peakcap_r0p95_eta5_mpc_tes/report.md) |
| `peakcap_r0p97_eta10_mpc_no_tes` | Peak-cap | mpc_no_tes | [cases/peakcap_r0p97_eta10_mpc_no_tes/report.md](cases/peakcap_r0p97_eta10_mpc_no_tes/report.md) |
| `peakcap_r0p97_eta10_mpc_tes` | Peak-cap | mpc | [cases/peakcap_r0p97_eta10_mpc_tes/report.md](cases/peakcap_r0p97_eta10_mpc_tes/report.md) |
| `peakcap_r0p97_eta20_mpc_no_tes` | Peak-cap | mpc_no_tes | [cases/peakcap_r0p97_eta20_mpc_no_tes/report.md](cases/peakcap_r0p97_eta20_mpc_no_tes/report.md) |
| `peakcap_r0p97_eta20_mpc_tes` | Peak-cap | mpc | [cases/peakcap_r0p97_eta20_mpc_tes/report.md](cases/peakcap_r0p97_eta20_mpc_tes/report.md) |
| `peakcap_r0p97_eta5_mpc_no_tes` | Peak-cap | mpc_no_tes | [cases/peakcap_r0p97_eta5_mpc_no_tes/report.md](cases/peakcap_r0p97_eta5_mpc_no_tes/report.md) |
| `peakcap_r0p97_eta5_mpc_tes` | Peak-cap | mpc | [cases/peakcap_r0p97_eta5_mpc_tes/report.md](cases/peakcap_r0p97_eta5_mpc_tes/report.md) |
| `peakcap_r0p99_eta10_mpc_no_tes` | Peak-cap | mpc_no_tes | [cases/peakcap_r0p99_eta10_mpc_no_tes/report.md](cases/peakcap_r0p99_eta10_mpc_no_tes/report.md) |
| `peakcap_r0p99_eta10_mpc_tes` | Peak-cap | mpc | [cases/peakcap_r0p99_eta10_mpc_tes/report.md](cases/peakcap_r0p99_eta10_mpc_tes/report.md) |
| `peakcap_r0p99_eta20_mpc_no_tes` | Peak-cap | mpc_no_tes | [cases/peakcap_r0p99_eta20_mpc_no_tes/report.md](cases/peakcap_r0p99_eta20_mpc_no_tes/report.md) |
| `peakcap_r0p99_eta20_mpc_tes` | Peak-cap | mpc | [cases/peakcap_r0p99_eta20_mpc_tes/report.md](cases/peakcap_r0p99_eta20_mpc_tes/report.md) |
| `peakcap_r0p99_eta5_mpc_no_tes` | Peak-cap | mpc_no_tes | [cases/peakcap_r0p99_eta5_mpc_no_tes/report.md](cases/peakcap_r0p99_eta5_mpc_no_tes/report.md) |
| `peakcap_r0p99_eta5_mpc_tes` | Peak-cap | mpc | [cases/peakcap_r0p99_eta5_mpc_tes/report.md](cases/peakcap_r0p99_eta5_mpc_tes/report.md) |
| `peakcap_r1_eta10_mpc_no_tes` | Peak-cap | mpc_no_tes | [cases/peakcap_r1_eta10_mpc_no_tes/report.md](cases/peakcap_r1_eta10_mpc_no_tes/report.md) |
| `peakcap_r1_eta10_mpc_tes` | Peak-cap | mpc | [cases/peakcap_r1_eta10_mpc_tes/report.md](cases/peakcap_r1_eta10_mpc_tes/report.md) |
| `peakcap_r1_eta20_mpc_no_tes` | Peak-cap | mpc_no_tes | [cases/peakcap_r1_eta20_mpc_no_tes/report.md](cases/peakcap_r1_eta20_mpc_no_tes/report.md) |
| `peakcap_r1_eta20_mpc_tes` | Peak-cap | mpc | [cases/peakcap_r1_eta20_mpc_tes/report.md](cases/peakcap_r1_eta20_mpc_tes/report.md) |
| `peakcap_r1_eta5_mpc_no_tes` | Peak-cap | mpc_no_tes | [cases/peakcap_r1_eta5_mpc_no_tes/report.md](cases/peakcap_r1_eta5_mpc_no_tes/report.md) |
| `peakcap_r1_eta5_mpc_tes` | Peak-cap | mpc | [cases/peakcap_r1_eta5_mpc_tes/report.md](cases/peakcap_r1_eta5_mpc_tes/report.md) |
| `robust_base_cp20_h12_mpc_no_tes` | Robustness | mpc_no_tes | [cases/robust_base_cp20_h12_mpc_no_tes/report.md](cases/robust_base_cp20_h12_mpc_no_tes/report.md) |
| `robust_base_cp20_h12_mpc_tes` | Robustness | mpc | [cases/robust_base_cp20_h12_mpc_tes/report.md](cases/robust_base_cp20_h12_mpc_tes/report.md) |
| `robust_base_cp20_h24_mpc_no_tes` | Robustness | mpc_no_tes | [cases/robust_base_cp20_h24_mpc_no_tes/report.md](cases/robust_base_cp20_h24_mpc_no_tes/report.md) |
| `robust_base_cp20_h24_mpc_tes` | Robustness | mpc | [cases/robust_base_cp20_h24_mpc_tes/report.md](cases/robust_base_cp20_h24_mpc_tes/report.md) |
| `robust_base_cp20_h6_mpc_no_tes` | Robustness | mpc_no_tes | [cases/robust_base_cp20_h6_mpc_no_tes/report.md](cases/robust_base_cp20_h6_mpc_no_tes/report.md) |
| `robust_base_cp20_h6_mpc_tes` | Robustness | mpc | [cases/robust_base_cp20_h6_mpc_tes/report.md](cases/robust_base_cp20_h6_mpc_tes/report.md) |
| `robust_base_cp20_soc0p2_mpc_no_tes` | Robustness | mpc_no_tes | [cases/robust_base_cp20_soc0p2_mpc_no_tes/report.md](cases/robust_base_cp20_soc0p2_mpc_no_tes/report.md) |
| `robust_base_cp20_soc0p2_mpc_tes` | Robustness | mpc | [cases/robust_base_cp20_soc0p2_mpc_tes/report.md](cases/robust_base_cp20_soc0p2_mpc_tes/report.md) |
| `robust_base_cp20_soc0p5_mpc_no_tes` | Robustness | mpc_no_tes | [cases/robust_base_cp20_soc0p5_mpc_no_tes/report.md](cases/robust_base_cp20_soc0p5_mpc_no_tes/report.md) |
| `robust_base_cp20_soc0p5_mpc_tes` | Robustness | mpc | [cases/robust_base_cp20_soc0p5_mpc_tes/report.md](cases/robust_base_cp20_soc0p5_mpc_tes/report.md) |
| `robust_base_cp20_soc0p8_mpc_no_tes` | Robustness | mpc_no_tes | [cases/robust_base_cp20_soc0p8_mpc_no_tes/report.md](cases/robust_base_cp20_soc0p8_mpc_no_tes/report.md) |
| `robust_base_cp20_soc0p8_mpc_tes` | Robustness | mpc | [cases/robust_base_cp20_soc0p8_mpc_tes/report.md](cases/robust_base_cp20_soc0p8_mpc_tes/report.md) |
| `robust_dr_day_ahead_10_h12_mpc_no_tes` | Robustness | mpc_no_tes | [cases/robust_dr_day_ahead_10_h12_mpc_no_tes/report.md](cases/robust_dr_day_ahead_10_h12_mpc_no_tes/report.md) |
| `robust_dr_day_ahead_10_h12_mpc_tes` | Robustness | mpc | [cases/robust_dr_day_ahead_10_h12_mpc_tes/report.md](cases/robust_dr_day_ahead_10_h12_mpc_tes/report.md) |
| `robust_dr_day_ahead_10_h24_mpc_no_tes` | Robustness | mpc_no_tes | [cases/robust_dr_day_ahead_10_h24_mpc_no_tes/report.md](cases/robust_dr_day_ahead_10_h24_mpc_no_tes/report.md) |
| `robust_dr_day_ahead_10_h24_mpc_tes` | Robustness | mpc | [cases/robust_dr_day_ahead_10_h24_mpc_tes/report.md](cases/robust_dr_day_ahead_10_h24_mpc_tes/report.md) |
| `robust_dr_day_ahead_10_h6_mpc_no_tes` | Robustness | mpc_no_tes | [cases/robust_dr_day_ahead_10_h6_mpc_no_tes/report.md](cases/robust_dr_day_ahead_10_h6_mpc_no_tes/report.md) |
| `robust_dr_day_ahead_10_h6_mpc_tes` | Robustness | mpc | [cases/robust_dr_day_ahead_10_h6_mpc_tes/report.md](cases/robust_dr_day_ahead_10_h6_mpc_tes/report.md) |
| `robust_dr_day_ahead_10_soc0p2_mpc_no_tes` | Robustness | mpc_no_tes | [cases/robust_dr_day_ahead_10_soc0p2_mpc_no_tes/report.md](cases/robust_dr_day_ahead_10_soc0p2_mpc_no_tes/report.md) |
| `robust_dr_day_ahead_10_soc0p2_mpc_tes` | Robustness | mpc | [cases/robust_dr_day_ahead_10_soc0p2_mpc_tes/report.md](cases/robust_dr_day_ahead_10_soc0p2_mpc_tes/report.md) |
| `robust_dr_day_ahead_10_soc0p5_mpc_no_tes` | Robustness | mpc_no_tes | [cases/robust_dr_day_ahead_10_soc0p5_mpc_no_tes/report.md](cases/robust_dr_day_ahead_10_soc0p5_mpc_no_tes/report.md) |
| `robust_dr_day_ahead_10_soc0p5_mpc_tes` | Robustness | mpc | [cases/robust_dr_day_ahead_10_soc0p5_mpc_tes/report.md](cases/robust_dr_day_ahead_10_soc0p5_mpc_tes/report.md) |
| `robust_dr_day_ahead_10_soc0p8_mpc_no_tes` | Robustness | mpc_no_tes | [cases/robust_dr_day_ahead_10_soc0p8_mpc_no_tes/report.md](cases/robust_dr_day_ahead_10_soc0p8_mpc_no_tes/report.md) |
| `robust_dr_day_ahead_10_soc0p8_mpc_tes` | Robustness | mpc | [cases/robust_dr_day_ahead_10_soc0p8_mpc_tes/report.md](cases/robust_dr_day_ahead_10_soc0p8_mpc_tes/report.md) |
| `tou_full_base_cp20_hot_direct_no_tes` | TOU full compare | no_tes | [cases/tou_full_base_cp20_hot_direct_no_tes/report.md](cases/tou_full_base_cp20_hot_direct_no_tes/report.md) |
| `tou_full_base_cp20_hot_mpc_no_tes` | TOU full compare | mpc_no_tes | [cases/tou_full_base_cp20_hot_mpc_no_tes/report.md](cases/tou_full_base_cp20_hot_mpc_no_tes/report.md) |
| `tou_full_base_cp20_hot_mpc_tes` | TOU full compare | mpc | [cases/tou_full_base_cp20_hot_mpc_tes/report.md](cases/tou_full_base_cp20_hot_mpc_tes/report.md) |
| `tou_full_base_cp20_hot_rbc_tes` | TOU full compare | rbc | [cases/tou_full_base_cp20_hot_rbc_tes/report.md](cases/tou_full_base_cp20_hot_rbc_tes/report.md) |
| `tou_full_base_cp20_mild_direct_no_tes` | TOU full compare | no_tes | [cases/tou_full_base_cp20_mild_direct_no_tes/report.md](cases/tou_full_base_cp20_mild_direct_no_tes/report.md) |
| `tou_full_base_cp20_mild_mpc_no_tes` | TOU full compare | mpc_no_tes | [cases/tou_full_base_cp20_mild_mpc_no_tes/report.md](cases/tou_full_base_cp20_mild_mpc_no_tes/report.md) |
| `tou_full_base_cp20_mild_mpc_tes` | TOU full compare | mpc | [cases/tou_full_base_cp20_mild_mpc_tes/report.md](cases/tou_full_base_cp20_mild_mpc_tes/report.md) |
| `tou_full_base_cp20_mild_rbc_tes` | TOU full compare | rbc | [cases/tou_full_base_cp20_mild_rbc_tes/report.md](cases/tou_full_base_cp20_mild_rbc_tes/report.md) |
| `tou_full_base_hot_direct_no_tes` | TOU full compare | no_tes | [cases/tou_full_base_hot_direct_no_tes/report.md](cases/tou_full_base_hot_direct_no_tes/report.md) |
| `tou_full_base_hot_mpc_no_tes` | TOU full compare | mpc_no_tes | [cases/tou_full_base_hot_mpc_no_tes/report.md](cases/tou_full_base_hot_mpc_no_tes/report.md) |
| `tou_full_base_hot_mpc_tes` | TOU full compare | mpc | [cases/tou_full_base_hot_mpc_tes/report.md](cases/tou_full_base_hot_mpc_tes/report.md) |
| `tou_full_base_hot_rbc_tes` | TOU full compare | rbc | [cases/tou_full_base_hot_rbc_tes/report.md](cases/tou_full_base_hot_rbc_tes/report.md) |
| `tou_full_base_mild_direct_no_tes` | TOU full compare | no_tes | [cases/tou_full_base_mild_direct_no_tes/report.md](cases/tou_full_base_mild_direct_no_tes/report.md) |
| `tou_full_base_mild_mpc_no_tes` | TOU full compare | mpc_no_tes | [cases/tou_full_base_mild_mpc_no_tes/report.md](cases/tou_full_base_mild_mpc_no_tes/report.md) |
| `tou_full_base_mild_mpc_tes` | TOU full compare | mpc | [cases/tou_full_base_mild_mpc_tes/report.md](cases/tou_full_base_mild_mpc_tes/report.md) |
| `tou_full_base_mild_rbc_tes` | TOU full compare | rbc | [cases/tou_full_base_mild_rbc_tes/report.md](cases/tou_full_base_mild_rbc_tes/report.md) |
| `tou_full_flat_hot_direct_no_tes` | TOU full compare | no_tes | [cases/tou_full_flat_hot_direct_no_tes/report.md](cases/tou_full_flat_hot_direct_no_tes/report.md) |
| `tou_full_flat_hot_mpc_no_tes` | TOU full compare | mpc_no_tes | [cases/tou_full_flat_hot_mpc_no_tes/report.md](cases/tou_full_flat_hot_mpc_no_tes/report.md) |
| `tou_full_flat_hot_mpc_tes` | TOU full compare | mpc | [cases/tou_full_flat_hot_mpc_tes/report.md](cases/tou_full_flat_hot_mpc_tes/report.md) |
| `tou_full_flat_hot_rbc_tes` | TOU full compare | rbc | [cases/tou_full_flat_hot_rbc_tes/report.md](cases/tou_full_flat_hot_rbc_tes/report.md) |
| `tou_full_flat_mild_direct_no_tes` | TOU full compare | no_tes | [cases/tou_full_flat_mild_direct_no_tes/report.md](cases/tou_full_flat_mild_direct_no_tes/report.md) |
| `tou_full_flat_mild_mpc_no_tes` | TOU full compare | mpc_no_tes | [cases/tou_full_flat_mild_mpc_no_tes/report.md](cases/tou_full_flat_mild_mpc_no_tes/report.md) |
| `tou_full_flat_mild_mpc_tes` | TOU full compare | mpc | [cases/tou_full_flat_mild_mpc_tes/report.md](cases/tou_full_flat_mild_mpc_tes/report.md) |
| `tou_full_flat_mild_rbc_tes` | TOU full compare | rbc | [cases/tou_full_flat_mild_rbc_tes/report.md](cases/tou_full_flat_mild_rbc_tes/report.md) |
| `tou_full_highspread_cp20_hot_direct_no_tes` | TOU full compare | no_tes | [cases/tou_full_highspread_cp20_hot_direct_no_tes/report.md](cases/tou_full_highspread_cp20_hot_direct_no_tes/report.md) |
| `tou_full_highspread_cp20_hot_mpc_no_tes` | TOU full compare | mpc_no_tes | [cases/tou_full_highspread_cp20_hot_mpc_no_tes/report.md](cases/tou_full_highspread_cp20_hot_mpc_no_tes/report.md) |
| `tou_full_highspread_cp20_hot_mpc_tes` | TOU full compare | mpc | [cases/tou_full_highspread_cp20_hot_mpc_tes/report.md](cases/tou_full_highspread_cp20_hot_mpc_tes/report.md) |
| `tou_full_highspread_cp20_hot_rbc_tes` | TOU full compare | rbc | [cases/tou_full_highspread_cp20_hot_rbc_tes/report.md](cases/tou_full_highspread_cp20_hot_rbc_tes/report.md) |
| `tou_full_highspread_cp20_mild_direct_no_tes` | TOU full compare | no_tes | [cases/tou_full_highspread_cp20_mild_direct_no_tes/report.md](cases/tou_full_highspread_cp20_mild_direct_no_tes/report.md) |
| `tou_full_highspread_cp20_mild_mpc_no_tes` | TOU full compare | mpc_no_tes | [cases/tou_full_highspread_cp20_mild_mpc_no_tes/report.md](cases/tou_full_highspread_cp20_mild_mpc_no_tes/report.md) |
| `tou_full_highspread_cp20_mild_mpc_tes` | TOU full compare | mpc | [cases/tou_full_highspread_cp20_mild_mpc_tes/report.md](cases/tou_full_highspread_cp20_mild_mpc_tes/report.md) |
| `tou_full_highspread_cp20_mild_rbc_tes` | TOU full compare | rbc | [cases/tou_full_highspread_cp20_mild_rbc_tes/report.md](cases/tou_full_highspread_cp20_mild_rbc_tes/report.md) |
| `tou_screen_g0_cp0_hot_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g0_cp0_hot_mpc_no_tes/report.md](cases/tou_screen_g0_cp0_hot_mpc_no_tes/report.md) |
| `tou_screen_g0_cp0_hot_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g0_cp0_hot_mpc_tes/report.md](cases/tou_screen_g0_cp0_hot_mpc_tes/report.md) |
| `tou_screen_g0_cp0_mild_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g0_cp0_mild_mpc_no_tes/report.md](cases/tou_screen_g0_cp0_mild_mpc_no_tes/report.md) |
| `tou_screen_g0_cp0_mild_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g0_cp0_mild_mpc_tes/report.md](cases/tou_screen_g0_cp0_mild_mpc_tes/report.md) |
| `tou_screen_g0_cp0p2_hot_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g0_cp0p2_hot_mpc_no_tes/report.md](cases/tou_screen_g0_cp0p2_hot_mpc_no_tes/report.md) |
| `tou_screen_g0_cp0p2_hot_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g0_cp0p2_hot_mpc_tes/report.md](cases/tou_screen_g0_cp0p2_hot_mpc_tes/report.md) |
| `tou_screen_g0_cp0p2_mild_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g0_cp0p2_mild_mpc_no_tes/report.md](cases/tou_screen_g0_cp0p2_mild_mpc_no_tes/report.md) |
| `tou_screen_g0_cp0p2_mild_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g0_cp0p2_mild_mpc_tes/report.md](cases/tou_screen_g0_cp0p2_mild_mpc_tes/report.md) |
| `tou_screen_g0p5_cp0_hot_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g0p5_cp0_hot_mpc_no_tes/report.md](cases/tou_screen_g0p5_cp0_hot_mpc_no_tes/report.md) |
| `tou_screen_g0p5_cp0_hot_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g0p5_cp0_hot_mpc_tes/report.md](cases/tou_screen_g0p5_cp0_hot_mpc_tes/report.md) |
| `tou_screen_g0p5_cp0_mild_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g0p5_cp0_mild_mpc_no_tes/report.md](cases/tou_screen_g0p5_cp0_mild_mpc_no_tes/report.md) |
| `tou_screen_g0p5_cp0_mild_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g0p5_cp0_mild_mpc_tes/report.md](cases/tou_screen_g0p5_cp0_mild_mpc_tes/report.md) |
| `tou_screen_g0p5_cp0p2_hot_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g0p5_cp0p2_hot_mpc_no_tes/report.md](cases/tou_screen_g0p5_cp0p2_hot_mpc_no_tes/report.md) |
| `tou_screen_g0p5_cp0p2_hot_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g0p5_cp0p2_hot_mpc_tes/report.md](cases/tou_screen_g0p5_cp0p2_hot_mpc_tes/report.md) |
| `tou_screen_g0p5_cp0p2_mild_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g0p5_cp0p2_mild_mpc_no_tes/report.md](cases/tou_screen_g0p5_cp0p2_mild_mpc_no_tes/report.md) |
| `tou_screen_g0p5_cp0p2_mild_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g0p5_cp0p2_mild_mpc_tes/report.md](cases/tou_screen_g0p5_cp0p2_mild_mpc_tes/report.md) |
| `tou_screen_g1_cp0_hot_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g1_cp0_hot_mpc_no_tes/report.md](cases/tou_screen_g1_cp0_hot_mpc_no_tes/report.md) |
| `tou_screen_g1_cp0_hot_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g1_cp0_hot_mpc_tes/report.md](cases/tou_screen_g1_cp0_hot_mpc_tes/report.md) |
| `tou_screen_g1_cp0_mild_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g1_cp0_mild_mpc_no_tes/report.md](cases/tou_screen_g1_cp0_mild_mpc_no_tes/report.md) |
| `tou_screen_g1_cp0_mild_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g1_cp0_mild_mpc_tes/report.md](cases/tou_screen_g1_cp0_mild_mpc_tes/report.md) |
| `tou_screen_g1_cp0p2_hot_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g1_cp0p2_hot_mpc_no_tes/report.md](cases/tou_screen_g1_cp0p2_hot_mpc_no_tes/report.md) |
| `tou_screen_g1_cp0p2_hot_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g1_cp0p2_hot_mpc_tes/report.md](cases/tou_screen_g1_cp0p2_hot_mpc_tes/report.md) |
| `tou_screen_g1_cp0p2_mild_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g1_cp0p2_mild_mpc_no_tes/report.md](cases/tou_screen_g1_cp0p2_mild_mpc_no_tes/report.md) |
| `tou_screen_g1_cp0p2_mild_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g1_cp0p2_mild_mpc_tes/report.md](cases/tou_screen_g1_cp0p2_mild_mpc_tes/report.md) |
| `tou_screen_g1p5_cp0_hot_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g1p5_cp0_hot_mpc_no_tes/report.md](cases/tou_screen_g1p5_cp0_hot_mpc_no_tes/report.md) |
| `tou_screen_g1p5_cp0_hot_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g1p5_cp0_hot_mpc_tes/report.md](cases/tou_screen_g1p5_cp0_hot_mpc_tes/report.md) |
| `tou_screen_g1p5_cp0_mild_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g1p5_cp0_mild_mpc_no_tes/report.md](cases/tou_screen_g1p5_cp0_mild_mpc_no_tes/report.md) |
| `tou_screen_g1p5_cp0_mild_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g1p5_cp0_mild_mpc_tes/report.md](cases/tou_screen_g1p5_cp0_mild_mpc_tes/report.md) |
| `tou_screen_g1p5_cp0p2_hot_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g1p5_cp0p2_hot_mpc_no_tes/report.md](cases/tou_screen_g1p5_cp0p2_hot_mpc_no_tes/report.md) |
| `tou_screen_g1p5_cp0p2_hot_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g1p5_cp0p2_hot_mpc_tes/report.md](cases/tou_screen_g1p5_cp0p2_hot_mpc_tes/report.md) |
| `tou_screen_g1p5_cp0p2_mild_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g1p5_cp0p2_mild_mpc_no_tes/report.md](cases/tou_screen_g1p5_cp0p2_mild_mpc_no_tes/report.md) |
| `tou_screen_g1p5_cp0p2_mild_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g1p5_cp0p2_mild_mpc_tes/report.md](cases/tou_screen_g1p5_cp0p2_mild_mpc_tes/report.md) |
| `tou_screen_g2_cp0_hot_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g2_cp0_hot_mpc_no_tes/report.md](cases/tou_screen_g2_cp0_hot_mpc_no_tes/report.md) |
| `tou_screen_g2_cp0_hot_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g2_cp0_hot_mpc_tes/report.md](cases/tou_screen_g2_cp0_hot_mpc_tes/report.md) |
| `tou_screen_g2_cp0_mild_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g2_cp0_mild_mpc_no_tes/report.md](cases/tou_screen_g2_cp0_mild_mpc_no_tes/report.md) |
| `tou_screen_g2_cp0_mild_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g2_cp0_mild_mpc_tes/report.md](cases/tou_screen_g2_cp0_mild_mpc_tes/report.md) |
| `tou_screen_g2_cp0p2_hot_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g2_cp0p2_hot_mpc_no_tes/report.md](cases/tou_screen_g2_cp0p2_hot_mpc_no_tes/report.md) |
| `tou_screen_g2_cp0p2_hot_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g2_cp0p2_hot_mpc_tes/report.md](cases/tou_screen_g2_cp0p2_hot_mpc_tes/report.md) |
| `tou_screen_g2_cp0p2_mild_mpc_no_tes` | TOU screening | mpc_no_tes | [cases/tou_screen_g2_cp0p2_mild_mpc_no_tes/report.md](cases/tou_screen_g2_cp0p2_mild_mpc_no_tes/report.md) |
| `tou_screen_g2_cp0p2_mild_mpc_tes` | TOU screening | mpc | [cases/tou_screen_g2_cp0p2_mild_mpc_tes/report.md](cases/tou_screen_g2_cp0p2_mild_mpc_tes/report.md) |
