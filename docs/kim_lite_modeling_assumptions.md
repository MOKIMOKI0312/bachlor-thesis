# Kim-lite Modeling Assumptions

Date: 2026-05-09

## Main Model Role

Kim-lite is a control-oriented proxy model for chiller-plant and TES scheduling. It is used to study the marginal value of TES under PV, TOU tariff, critical peak, signed valve ramp, and peak-cap scenarios.

The main economic results come from the Kim-lite proxy matrix under:

```text
results/kim_lite_mainline_hardening_20260509/
```

These results should be interpreted as mechanism and sensitivity results, not as a full physical EnergyPlus online savings claim.

## Relaxed Plant Dispatch

The main Kim-lite TES-MPC result is labeled:

```text
paper_like_mpc_tes_relaxed
```

The plant mode variables are relaxed to continuous dispatch weights in the main experiments. This relaxation approximates an aggregated chiller plant with continuous modulation capability and keeps the focus on TES scheduling rather than strict single-chiller startup/shutdown logic.

This means the main results are not strict binary chiller-mode MILP results. Strict integer mode selection is retained as a future extension.

The relaxed formulation can:

- underestimate fixed startup or fixed on-power effects;
- make chiller operation smoother than a fully discrete plant;
- overestimate economic savings relative to strict unit commitment.

For this reason each run keeps diagnostic fields:

```text
mode_integrality
mode_fractionality_max
mode_fractionality_mean
mode_fractionality_count
mode_fractionality_hours
```

## TES And Tariff Interpretation

The Kim-lite proxy treats cooling load as exogenous. Therefore, `mpc_no_tes` is expected to be close to `direct_no_tes`; the incremental value of `paper_like_mpc_tes_relaxed` comes from shifting chiller cooling relative to load through TES SOC.

China TOU and critical peak scenarios are engineering approximations. The floating component is transformed around its mean, the non-floating component is held constant, and critical peak periods come from explicit timestamp windows rather than price quantiles.

## Peak-Cap Interpretation

Peak-cap results must be interpreted with peak slack metrics:

```text
peak_slack_kwh
peak_slack_max_kw
TES_peak_cap_help_kwh
TES_peak_cap_help_max_kw
peak_cap_success_flag
```

Energy cost alone is not a valid peak-cap success criterion. TES can reduce total peak slack energy while still worsening maximum instantaneous slack under tighter caps.

## EnergyPlus I/O Diagnostic Role

EnergyPlus online results are used as I/O coupling diagnostics rather than final energy-saving evidence.

They verify:

- Runtime API handle resolution;
- `TES_Set` actuator writes and echoes;
- `Chiller_T_Set` actuator writes and echoes;
- fallback and safety-filter behavior;
- temperature risk relative to `no_mpc`.

The EnergyPlus controller matrix must keep:

```text
result_role = io_coupling_diagnostic
TES_Set echo mismatch
Chiller_T_Set echo mismatch
fallback_count
zone_temp_max_c
temp_violation_degree_hours_27c
cost_comparison_valid
```

When `cost_comparison_valid=false`, EnergyPlus rows must not be used as cost-saving evidence.
