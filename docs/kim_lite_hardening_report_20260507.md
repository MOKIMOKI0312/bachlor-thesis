# Kim-lite Hardening Report - 2026-05-07

## Purpose

This hardening pass improves the defensibility of the Kim-lite paper-like MPC results without changing the project into a new physical model. It keeps the signed-net TES proxy and focuses on comparison fairness, peak-cap solver reporting, and result auditing.

## Implemented Hardening

- Added `storage_priority_neutral_tes` as a deterministic SOC-neutral storage-priority baseline.
- Kept `storage_priority_tes` as a non-neutral diagnostic baseline.
- Changed Kim-lite MPC mode integrality into an explicit interface: `strict` by default, `relaxed` only when requested.
- Made SOC bounds hard constraints in the MILP; terminal SOC may still deviate through terminal penalty variables and is reported explicitly.
- Rebuilt Phase D peak-cap output as strict primary rows plus relaxed reference rows.
- Added `audit_kim_lite_results` to detect missing fields, non-neutral baseline drift, SOC/grid violations, relaxed rows mislabeled as strict, and fractional strict mode activation.

## Result Location

```text
results/kim_lite_hardened_20260507/
```

Generated result groups:

- `phase_b_attribution/summary.csv`
- `phase_b_attribution/attribution_table.csv`
- `phase_d_peakcap/summary.csv`
- `figures/fig_phase_b_cost_by_controller.png`
- `figures/fig_peak_reduction_cost_tradeoff.png`

## Phase B Hardened Attribution

Key cost and terminal SOC results:

```text
direct_no_tes                cost=19344.5688  final_soc=0.5000
mpc_no_tes                   cost=19344.5688  final_soc=0.5000
storage_priority_tes         cost=19219.3182  final_soc=0.8496
storage_priority_neutral_tes cost=19188.8389  final_soc=0.5000
paper_like_mpc_tes           cost=19162.4568  final_soc=0.5000
```

Attribution table:

```text
MPC_value           = 0.0000
TES_value           = 182.1120
RBC_gap_non_neutral = 56.8614
RBC_gap_neutral     = 26.3821
```

Interpretation:

- The original non-neutral storage-priority baseline overstated the RBC gap because it ended with a much higher SOC.
- The neutral baseline still shows a positive gap versus paper-like MPC, but the defensible value is smaller.

## Phase D Strict Peak-cap Status

Strict rows are the primary result. Relaxed rows are reference diagnostics only.

Strict status:

```text
strict_cap_1p0_mpc_no_tes          optimal
strict_cap_1p0_paper_like_mpc_tes  optimal
strict_cap_0p99_mpc_no_tes         optimal
strict_cap_0p99_paper_like_mpc_tes optimal
strict_cap_0p97_mpc_no_tes         optimal
strict_cap_0p97_paper_like_mpc_tes failed: time limit reached
strict_cap_0p95_mpc_no_tes         optimal
strict_cap_0p95_paper_like_mpc_tes failed: time limit reached
```

The failed strict TES peak-cap cases are not reported as valid strict results. Their relaxed counterparts remain in `summary.csv` with `mode_integrality=relaxed` and `solver_status=optimal_relaxed_modes`.

## Verification

Commands run:

```powershell
python -m pytest tests/test_kim_lite_storage_priority.py tests/test_kim_lite_peak_epigraph.py tests/test_kim_lite_audit.py -q
python -m mpc_v2.scripts.run_kim_lite_matrix --phase phase_b_attribution --output-root results/kim_lite_hardened_20260507
python -m mpc_v2.scripts.run_kim_lite_matrix --phase phase_d_peakcap --output-root results/kim_lite_hardened_20260507
python -m mpc_v2.scripts.audit_kim_lite_results --root results/kim_lite_hardened_20260507
```

Observed:

```text
Kim-lite targeted tests: 6 passed
Phase B matrix: completed
Phase D matrix: completed with strict diagnostic failures for two TES cap cases
Audit: passed
```

## Thesis Impact

No thesis source files were updated in this pass.

Reason: this pass strengthens result credibility and records hardened outputs, but it does not yet insert these results into the thesis正文. If the hardened Kim-lite results become thesis claims, the thesis must state that the result is a structural Kim-style reproduction with a signed-net TES proxy, not a numeric reproduction of Kim et al. 2022.

## Remaining Limits

- TES still uses a signed-net LTI proxy, not split charge/discharge efficiency.
- Phase D strict TES peak-cap at cap ratios `0.97` and `0.95` hits the solver time limit.
- Relaxed mode rows are useful only for screening and cannot support final integer plant-mode claims.
