# mpc_v2 AGENTS.md

## Scope

- `mpc_v2/` is the rebuilt deterministic chiller + TES MPC validation package.
- Keep it independent from the EnergyPlus online runner. EnergyPlus inputs may feed replay data, but this package does not control EnergyPlus directly.
- Preserve the public data flow before adding features: config YAML -> `run_closed_loop.py` or `run_validation_matrix.py` -> standard CSV/JSON output files.

## Current v1 Contract

- Supported controller modes: `no_tes`, `rbc`, `mpc`, and compatibility alias `mpc_no_tes`.
- Supported timestep: 15 minutes.
- Supported validation target: fixed synthetic/replay closed loop with PV, price, IT load, outdoor temperature, TES SOC, chiller power, grid import, PV spill, and cost.
- Deferred features must fail explicitly instead of silently producing results:
  - China TOU/DR large matrix generation
  - DR events
  - peak-cap and demand-charge optimization
  - attribution/contribution report generation

## Output Files

Every closed-loop run must write:

- `monitor.csv`
- `timeseries.csv`
- `solver_log.csv`
- `events.csv`
- `episode_summary.json`
- `summary.csv`
- `config_effective.yaml`

Do not rename these files without updating `contracts/output_contract.md`, tests, and `CHANGELOG.md`.

## Validation

Before committing a rebuilt MPC change, run:

```powershell
python -m pytest -q
python -m mpc_v2.scripts.run_closed_loop --controller-mode no_tes --steps 96 --case-id smoke_no_tes
python -m mpc_v2.scripts.run_closed_loop --controller-mode rbc --steps 96 --case-id smoke_rbc
python -m mpc_v2.scripts.run_closed_loop --controller-mode mpc --steps 96 --case-id smoke_mpc --truncate-horizon-to-episode
```

Acceptance for the fixed MPC smoke case:

- `fallback_count = 0`
- `soc_violation_count = 0`
- no simultaneous charge/discharge
- `final_soc_after_last_update` is close to `soc_target`
- all standard output files exist
