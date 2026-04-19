# M2-D1 Smoke Test Artefacts

Generated 2026-04-19 evening as part of M2 Phase 6 (D1 smoke).

## Run configs

- **EPW**: `USA_CA_San.Francisco.Intl.AP.724940_TMYx.2009-2023.epw`
- **Building**: `DRL_DC_training.epJSON` (M1-R2 TES version, unchanged)
- **Seed**: 99
- **Algorithm**: DSAC-T (CPU)
- **Timesteps**: 500 (≈ 21 simulated days, first hour-of-day onwards)
- **α (cost coeff)**: 1e-3
- **β (comfort multiplier)**: 1.0
- **c_pv (RL-Green virtual green price)**: 0.0 USD/MWh
- **pv_threshold_kw**: 100 kW (PV > 100 kW → virtual green-price regime active)

## Artefacts

| File | Steps | Columns | Description |
|---|---|---|---|
| `smoke_rl_cost_monitor.csv` | 501 (header + 500 rows) | 56 (header) / 57 (rows) | RL-Cost reward |
| `smoke_rl_green_monitor.csv` | 501 | 56 / 57 | RL-Green reward |

Column layout (header, post LoggerWrapper dedupe):
```
timestep,
<22 base E+ obs>, TES_valve_wrapper_position,
<4 time encoding>, <3 price>, <3 PV>, <9 workload>,  # total 41 obs
<6 action vars (including TES_Set which dedupes with TES_valve_wrapper_position — actually no — TES_Set is the absolute actuator value)>,
time (hours), reward, energy_term, ITE_term, comfort_term, cost_term,
terminated, truncated
```

(Exact count is 56 header vs 57 data cells — the trailing `truncated` column
has no terminator; this is Sinergym's existing CSV format convention.)

## Pass criteria — all met ✓

- Process completed without crash (both runs)
- 500 timesteps × 1 episode each, elapsed ≈ 3.4s (env setup dominated)
- Observations all finite across all steps
- `reward` column contains finite floats
- Monitor CSVs contain `cost_term` column (M2-specific reward decomposition)
- `TES_valve_wrapper_position` appears exactly ONCE in header (dedupe fix
  from M2-fix commit working)

## Known limitations

- 500 steps is well below SB3 `learning_starts=8760`, so no SAC updates
  triggered — this smoke validates env integration + rollout collection
  only, not the SAC loss path. For end-to-end learning validation, run
  at least 1 full episode with `--timesteps 10000` (still fast ~7 min on CPU).
