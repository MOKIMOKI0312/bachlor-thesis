# Chiller TES MPC Attribution Results - 2026-05-05

## Verification

- Five 7-day attribution cases completed with `steps=672` and `horizon_steps=48` (12 h receding horizon).
- PV/grid main accounting is whole-facility behind-the-meter: `grid = max(0, IT + cold_station - PV)`.
- Cold-station-only proxy cost/grid/PV metrics are retained only as auxiliary attribution diagnostics.
- All included cases have zero fallback, zero temperature degree-hour violation, zero physical consistency violation, and zero signed-valve violation.

## Attribution Matrix

| case                                 | controller_type   |   total_cost |   cold_station_proxy_total_cost |   grid_import_kwh |   cold_station_proxy_grid_import_kwh |   pv_spill_kwh |   cold_station_proxy_pv_spill_kwh |   peak_grid_kw |   cold_station_energy_kwh |   tes_charge_kwh_th |   tes_discharge_kwh_th |   final_soc_after_last_update |   soc_delta |   tes_arbitrage_price_spread |   weighted_avg_chiller_cop |
|:-------------------------------------|:------------------|-------------:|--------------------------------:|------------------:|-------------------------------------:|---------------:|----------------------------------:|---------------:|--------------------------:|--------------------:|-----------------------:|------------------------------:|------------:|-----------------------------:|---------------------------:|
| attribution_7day_no_tes_direct       | no_tes            |   303552.687 |                       24213.078 |       3251529.468 |                           247424.854 |          0.000 |                         19895.386 |      20633.250 |                336516.588 |               0.000 |                  0.000 |                         0.500 |       0.000 |                      nan     |                      6.698 |
| attribution_7day_mpc_no_tes          | mpc_no_tes        |   289706.517 |                       14245.199 |       3239731.916 |                           251182.718 |          0.000 |                         35450.802 |      21090.000 |                324719.036 |               0.000 |                  0.000 |                         0.500 |       0.000 |                      nan     |                      7.049 |
| attribution_7day_rbc_tes             | rbc               |   303263.150 |                       23954.473 |       3255772.891 |                           251392.030 |          0.000 |                         19619.140 |      20576.550 |                340760.011 |           37012.500 |              27562.500 |                         0.555 |       0.055 |                      121.990 |                      6.701 |
| attribution_7day_mpc_tes             | mpc               |   289447.586 |                       13981.368 |       3238814.270 |                           250206.029 |          0.000 |                         35391.759 |      21090.000 |                323801.390 |           21676.868 |              22821.691 |                         0.150 |      -0.350 |                      157.205 |                      7.050 |
| attribution_7day_mpc_tes_soc_neutral | mpc               |   289400.137 |                       13968.870 |       3238582.226 |                           250395.082 |          0.000 |                         35812.856 |      21090.000 |                323569.346 |           43477.064 |              41014.600 |                         0.150 |      -0.350 |                      160.780 |                      7.047 |

## Key Deltas

- `mpc_no_tes` vs direct no-TES total-cost delta: -13846.170 (-4.56%).
- `mpc_tes` incremental total-cost delta vs `mpc_no_tes`: -258.931 (-0.09%).
- SOC-neutral attempt cost delta vs inventory-using MPC: -47.449 (-0.02%).
- SOC-neutral attempt final SOC error: 0.3500, so it did not meet the `abs(final SOC - initial SOC) <= 0.03` target.

## Interpretation

- The new `mpc_no_tes` baseline separates economic chiller scheduling from TES contribution.
- The TES contribution should be read from `mpc_tes` relative to `mpc_no_tes`, not from `mpc_tes` relative to direct no-TES.
- Whole-facility PV/grid accounting makes nominal PV spill zero because IT load dominates the 6 MWp PV profile; PV absorption claims should not be made from this nominal attribution matrix.
- The inventory-using MPC still draws SOC down. The nominal SOC-neutral attempt also ends at SOC 0.15, which shows that the current receding-horizon terminal penalty does not enforce episode-end inventory neutrality.

## Thesis Boundary

- Do not claim TES alone caused the full MPC-vs-direct-baseline cost reduction.
- It is valid to claim the framework now supports a scientific attribution split: direct baseline, price-aware no-TES MPC, RBC TES, MPC TES, and a documented failed SOC-neutral attempt.
- It is valid to state that the final candidate horizon used here is 12 h, with 48 h prediction horizon retained only as a 192-step slow/manual extension.
