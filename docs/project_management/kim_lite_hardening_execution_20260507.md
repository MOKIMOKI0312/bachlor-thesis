# Kim-lite hardening execution - 2026-05-07

## Task Status

- Task ID: `kim_lite_hardening_20260507`
- Status: `completed`
- Branch: `codex/kim-lite-hardening`
- Baseline branch: `codex/kim-lite-paper-mpc`
- Output root: `results/kim_lite_hardened_20260507/`

## Goal

Strengthen the existing Kim-lite results by fixing comparison fairness and preventing relaxed peak-cap results from being reported as strict MILP evidence.

## Completed Work

- Added SOC-neutral storage-priority baseline: `storage_priority_neutral_tes`.
- Preserved non-neutral `storage_priority_tes` as diagnostic output.
- Added explicit `mode_integrality` control with default `strict`.
- Removed automatic relaxed mode behavior from peak-cap solves.
- Made SOC bounds hard constraints while retaining terminal SOC error reporting.
- Added strict plus relaxed Phase D output rows.
- Added result audit CLI:

```powershell
python -m mpc_v2.scripts.audit_kim_lite_results --root results/kim_lite_hardened_20260507
```

## Acceptance Evidence

- `storage_priority_neutral_tes` final SOC error: approximately `4.44e-16`.
- Phase B attribution includes `RBC_gap_neutral` and `RBC_gap_non_neutral`.
- Strict Phase D rows no longer report `optimal_relaxed_modes`.
- Strict successful rows have `mode_fractionality_max <= 1e-6`.
- Strict failed rows include solver timeout text in `fallback_reason`.
- Audit command passed.

## Result Summary

Phase B:

```text
TES_value           = 182.1120
RBC_gap_non_neutral = 56.8614
RBC_gap_neutral     = 26.3821
```

Phase D:

```text
strict cap 1.00 TES: optimal
strict cap 0.99 TES: optimal
strict cap 0.97 TES: failed, time limit reached
strict cap 0.95 TES: failed, time limit reached
```

## Stop Conditions Checked

- No silent relaxed-to-strict substitution.
- No SOC bound violation in successful audited rows.
- No grid balance violation in successful audited rows.
- No PPT modified.
- No thesis claim added without thesis update.

## Next Technical Step

If continuing technical hardening, the next narrow task should be solver diagnostics for strict TES peak-cap at cap ratios `0.97` and `0.95`: either tune the MILP formulation to solve within time or record a smaller horizon/diagnostic infeasibility study.
