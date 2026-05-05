# Chiller + TES MPC v1.0 Result Summary

Date: 2026-05-05  
Branch: `codex/55TES-MPC`  
Result root: `results/chiller_tes_mpc_v1_20260505/`

## Commands

```powershell
python -m pytest -q
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_chiller_no_tes --controller-mode no_tes --steps 96 --output-root runs/chiller_tes_v1_final_smoke
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_chiller_rbc --controller-mode rbc --steps 96 --output-root runs/chiller_tes_v1_final_smoke
python -m mpc_v2.scripts.run_closed_loop --config mpc_v2/config/base.yaml --case-id smoke_chiller_tes_mpc --controller-mode mpc --steps 96 --output-root runs/chiller_tes_v1_final_smoke
python -m mpc_v2.scripts.run_validation_matrix --config mpc_v2/config/base.yaml --scenario-set thesis_chiller_tes --steps 96 --output-dir runs/chiller_tes_v1_final_validation
```

## Smoke Result

Each smoke run covers:

```text
96 steps * 0.25 h = 24 h
```

The MPC prediction horizon is:

```text
192 steps * 0.25 h = 48 h
```

| Metric | no-TES | RBC | MPC |
|---|---:|---:|---:|
| Total cost | 4073.02 | 3973.24 | 3627.88 |
| Grid import kWh | 49648.43 | 33907.68 | 47442.19 |
| Peak grid kW | 3090.00 | 3090.00 | 3090.00 |
| PV spill kWh | 342.96 | 1742.03 | 342.96 |
| Cold-station energy kWh | 69649.07 | 52509.26 | 67442.83 |
| Facility energy kWh | 501649.07 | 484509.26 | 499442.83 |
| Temperature violation degree-hours | 0.00 | 0.00 | 0.00 |
| TES charge kWh_th | 0.00 | 8054.70 | 7458.63 |
| TES discharge kWh_th | 0.00 | 12395.65 | 0.00 |
| TES equivalent cycles | 0.00 | 0.69 | 0.00 |
| Fallback count | 0 | 0 | 0 |
| Feasible rate | 1.00 | 1.00 | 1.00 |
| Solve time p95 s | 0.90 | 0.00 | 2.27 |

## Interpretation

Relative to the fair no-TES baseline, the chiller+TES MPC base smoke run:

- reduced total cost by about 10.93%;
- reduced cold-station grid import by about 4.44%;
- reduced cold-station energy by about 3.17%;
- kept temperature violations at zero;
- did not reduce peak grid demand;
- did not improve PV spill in the base case;
- charged TES but did not discharge TES in the base 24 h case.

The result is therefore **not** a clean proof that TES is already being used as intended in the nominal MPC case. It is a stronger proof that the new chiller+TES MILP boundary is operational and that chiller scheduling, mode selection, and room-temperature constraints materially change the economics. TES discharge appears in the RBC case and in the hot validation case, but base-case MPC still hoards SOC because the linear proxy and 48 h receding horizon make future flexibility more valuable than immediate discharge.

## Validation Matrix Notes

The validation matrix is saved under:

```text
results/chiller_tes_mpc_v1_20260505/final_validation/
```

Key observations:

- `chiller_tes_mpc_base` improves cost and cold-station energy relative to `chiller_no_tes_base`.
- `chiller_tes_demand_high` applies the demand charge but does not reduce peak because the current mode structure still reaches the same 3090 kW plant peak.
- `chiller_tes_hot` is the only MPC validation case with material TES discharge: 5067.20 kWh_th, or 0.28 equivalent cycles. It also has one fallback and 0.19 degree-hours of temperature violation.
- High PV scale reduces grid import but increases PV spill because cold-station load is smaller than PV availability for many steps.

## Thesis Readiness

This version is thesis-usable as an implementation milestone and as a discussion case for model-boundary effects. It should not be used to claim that TES-MPC definitively improves PV self-consumption or peak demand in the nominal case.

The strongest thesis statement supported by this run is:

```text
The chiller+TES MILP-MPC implementation is feasible, reproducible, and improves nominal operating cost and cold-station energy relative to a fair no-TES baseline, but the current linear proxy still requires further tuning before nominal TES discharge and peak shaving are demonstrated.
```

