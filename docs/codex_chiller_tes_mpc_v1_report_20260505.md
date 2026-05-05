# Codex Chiller + TES MPC v1.0 Implementation Report

Date: 2026-05-05  
Branch: `codex/55TES-MPC`  
Heartbeat: `chiller-tes-mpc-implementation-heartbeat` was created at execution start and paused during final cleanup.

## Changed Files

- `mpc_v2/config/base.yaml`
- `mpc_v2/config/scenario_sets.yaml`
- `mpc_v2/core/controller.py`
- `mpc_v2/core/facility_model.py`
- `mpc_v2/core/forecast.py`
- `mpc_v2/core/io_schemas.py`
- `mpc_v2/core/metrics.py`
- `mpc_v2/core/mpc_problem_milp.py`
- `mpc_v2/core/room_model.py`
- `mpc_v2/scripts/run_closed_loop.py`
- `mpc_v2/scripts/run_validation_matrix.py`
- `tests/`
- `README.md`
- `CHANGELOG.md`
- `docs/project_management/毕业设计论文/thesis_draft.tex`
- `docs/project_management/冷机TES联合MPC实施计划_20260505.md`

## Created Files

- `results/chiller_tes_mpc_v1_20260505/`
- `results/chiller_tes_mpc_v1_20260505/summary.md`
- `docs/codex_chiller_tes_mpc_v1_report_20260505.md`

## Exact Commands Run

```powershell
python -m pytest -q
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_chiller_no_tes --controller-mode no_tes --steps 96 --output-root runs/chiller_tes_v1_final_smoke
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_chiller_rbc --controller-mode rbc --steps 96 --output-root runs/chiller_tes_v1_final_smoke
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_chiller_tes_mpc --controller-mode mpc --steps 96 --output-root runs/chiller_tes_v1_final_smoke
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenario-set thesis_chiller_tes --steps 96 --output-dir runs/chiller_tes_v1_final_validation
```

## Test Results

```text
16 passed
```

## Smoke Output Paths

- `results/chiller_tes_mpc_v1_20260505/smoke/smoke_chiller_no_tes/`
- `results/chiller_tes_mpc_v1_20260505/smoke/smoke_chiller_rbc/`
- `results/chiller_tes_mpc_v1_20260505/smoke/smoke_chiller_tes_mpc/`

## Validation Output Path

- `results/chiller_tes_mpc_v1_20260505/final_validation/`

## Main Results

| Metric | no-TES | RBC | MPC |
|---|---:|---:|---:|
| Total cost | 4073.02 | 3973.24 | 3627.88 |
| Grid import kWh | 49648.43 | 33907.68 | 47442.19 |
| Peak grid kW | 3090.00 | 3090.00 | 3090.00 |
| PV spill kWh | 342.96 | 1742.03 | 342.96 |
| Cold-station energy kWh | 69649.07 | 52509.26 | 67442.83 |
| Temp violation degree-hours | 0.00 | 0.00 | 0.00 |
| TES equivalent cycles | 0.00 | 0.69 | 0.00 |
| Fallback count | 0 | 0 | 0 |

## Formula Assumptions

- Chiller plant power uses Kim-style switched affine modes.
- Wet-bulb temperature is proxied as dry-bulb minus `4.0 degC`.
- PV/grid balance is scoped to cold-station plant power, not total IT facility power.
- Facility energy and PUE are still reported by adding IT load back to cold-station power.
- Room temperature uses a linear first-order proxy with a tightened operating band of 23.5 to 27.0 degC.

## Unit Assumptions

- Thermal powers are `kW_th`.
- Electrical powers are `kW`.
- Energy price remains `currency/MWh`, following the input CSV header `price_usd_per_mwh`.
- Demand charge is `currency/kW-day`.

## Unresolved Issues

- Nominal MPC charges TES but does not discharge it in the 24 h smoke case.
- Peak demand is not reduced in the nominal or demand-charge validation cases.
- PV spill is not reduced in the nominal case.
- Hot validation triggers TES discharge, but also has one fallback and 0.19 degree-hours temperature violation.
- Chiller mode parameters are literature-scale defaults, not calibrated to a real南京冷站.

## Thesis Readiness

The version is thesis-ready as an implementation milestone and model-boundary discussion result. It is not thesis-ready as proof that nominal TES-MPC achieves peak shaving or PV-spill reduction.

