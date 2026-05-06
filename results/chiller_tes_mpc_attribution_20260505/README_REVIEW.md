# Review Notes

This folder freezes the attribution rerun after switching main PV/grid accounting to whole-facility behind-the-meter accounting.

Required files per case: `monitor.csv`, `solver_log.csv`, `episode_summary.json`, `config_effective.yaml`.

Primary CSV: `attribution_matrix.csv`.
Summary: `summary.md`.

The main scientific comparison is `attribution_7day_mpc_tes` versus `attribution_7day_mpc_no_tes`.

`attribution_7day_mpc_tes_soc_neutral` is an attempted SOC-neutral case, but it does not meet the final-SOC tolerance in the current receding-horizon implementation. Treat it as a diagnostic result, not as a successful inventory-neutral candidate.
