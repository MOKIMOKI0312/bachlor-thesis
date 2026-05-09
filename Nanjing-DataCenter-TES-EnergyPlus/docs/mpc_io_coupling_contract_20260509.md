# EnergyPlus-MPC I/O Coupling Contract

Date: 2026-05-09

## Scope

This contract defines the first EnergyPlus online MPC control surface that is allowed for thesis-grade diagnostics in this repository. It does not modify the epJSON model and does not add pump, fan, or chiller availability control.

## Runtime Inputs

The online controller reads EnergyPlus runtime observations at each system timestep:

- `TES_SOC_Obs`
- `TES_Avg_Temp_Obs`
- `TES_Set` echo
- `Chiller_T_Set` echo
- TES use-side and source-side heat transfer
- chiller electricity and cooling rate
- facility electricity
- zone temperature
- outdoor dry-bulb and wet-bulb temperature

External economic and renewable inputs are aligned by timestamp:

- PV forecast CSV
- price CSV

Forecast values are still replay or identified-model based, but the first state in every solve is corrected from EnergyPlus observations.

## Runtime Outputs

Normal MPC controllers may write only these EnergyPlus actuators:

| MPC controller | TES_Set | Chiller_T_Set | ITE_Set |
| --- | --- | --- | --- |
| `no_mpc` | no | no | no |
| `tes_only_mpc` | yes | no | no |
| `io_coupled_mpc` | yes | yes | no |
| `io_coupled_measured_mpc` | yes | yes | no |

`ITE_Set` is reserved for parameter-identification sampling and is not a normal MPC output.

## Sign Convention

Kim-lite uses:

```text
Q_tes_net = Q_chiller - Q_load
Q_tes_net > 0 -> TES charge
Q_tes_net < 0 -> TES discharge
```

EnergyPlus uses:

```text
TES_Set < 0 -> source-side charge command
TES_Set > 0 -> use-side discharge command
```

The adapter therefore writes:

```text
TES_Set = -clip(Q_tes_net / q_abs_max, -1, 1)
```

`Chiller_T_Set` is a normalized schedule actuator in `[0, 1]` used by the model EMS to adjust the chilled-water setpoint inside the model-defined bounds.

## Echo Validation

Each runtime case must record command and echo values:

- `tes_set_written` and `tes_set_echo`
- `chiller_t_set_written` and `chiller_t_set_echo` for I/O-coupled controllers

Any nonzero mismatch count invalidates the case audit.

## Temperature Safety

The first I/O-coupled implementation applies a local safety filter:

- If `zone_temp_c >= 26.5`, TES charging is blocked.
- If `zone_temp_c >= 27.0`, `Chiller_T_Set` is forced to the lowest normalized level and TES charging remains blocked.
- Cost comparisons are valid only when temperature degree-hours and maximum zone temperature do not worsen relative to the same-season `no_mpc` case.

This is a diagnostic guard, not a full thermal comfort constraint inside the MILP.

## Unsupported Channels

The following channels remain unsupported in this version:

- CRAH fan control
- pump flow or pump availability control
- chiller availability control
- direct `ITE_Set` control in normal MPC cases
- epJSON structure edits
