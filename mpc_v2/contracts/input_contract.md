# MPC v1 Input Contract

`mpc_v2` rebuild v1 keeps one stable config entry point: `mpc_v2/config/base.yaml`.

## Required Config Groups

- `time.dt_hours`: must be `0.25`.
- `time.horizon_steps`: positive integer forecast horizon.
- `time.default_closed_loop_steps`: default episode length.
- `paths.pv_csv`: hourly CSV with `timestamp` and one numeric PV column.
- `paths.price_csv`: hourly CSV with `timestamp` and one numeric price column. Columns containing `mwh` are converted to currency per kWh.
- `paths.output_root`: default run output root.
- `tes`: capacity, charge/discharge efficiencies, loss rate, power limits, initial SOC, physical/planning SOC bounds, and `soc_target`.
- `facility.cop_charge`: chiller electric COP proxy.
- `room.alpha_it_to_cooling`: IT load to cooling-load proxy.
- `synthetic`: start timestamp, fixed IT load, outdoor sinusoid parameters, wet-bulb depression, and seed.

## Supported Runtime Overrides

`run_closed_loop.py` supports:

- `--controller-mode {no_tes,rbc,mpc,mpc_no_tes}`
- `--steps`
- `--horizon-steps`
- `--pv-error-sigma`
- `--seed`
- `--tariff-multiplier`
- `--outdoor-offset-c`
- `--pv-scale`
- `--initial-soc`
- `--soc-target`
- `--w-terminal`
- `--w-spill`
- `--w-cycle`
- `--truncate-horizon-to-episode`

Old advanced China TOU/DR matrix, peak-cap, demand-charge, and attribution options are intentionally unsupported in v1 and must raise a clear unsupported-feature error.
