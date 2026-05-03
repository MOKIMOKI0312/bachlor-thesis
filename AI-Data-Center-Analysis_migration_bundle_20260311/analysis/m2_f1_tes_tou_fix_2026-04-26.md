# M2-F1 TES TOU Fix

Date: 2026-04-26

## Problem

The 4-seed M2-E3b 30-episode run finished without runtime failure, but
deterministic evaluation showed the learned TES policy did not use storage
for time-of-use arbitrage.  The policy saturated the TES valve almost all
year and had near-zero price response:

- `avg_valve_saturation_fraction`: approximately `0.9999`
- `avg_price_response_high_minus_low`: approximately `0`
- `tes_activated_count`: `0/4`

One implementation issue was also found during this fix: training used
`EnergyScaleWrapper`, while `tools/evaluate_m2.py` did not.  M2-F1 keeps the
training and evaluation wrapper stacks aligned.

## Action Semantics

M2-F1 now exposes a 4-dimensional agent action.  There is still no workload
action.  The underlying EnergyPlus environment keeps the 5-dimensional full
action, with `CRAH_Fan_DRL` fixed at 1.0 by `FixedActionInsertWrapper`.

The TES action changes from an incremental command to a target valve command:

```text
v_target = exposed_action[3]  # expands to full_action[4] = TES_DRL
v_next = v_prev + clip(v_target - v_prev, -0.25, 0.25)
```

The sign convention is unchanged:

```text
v > 0: discharge/use TES
v < 0: charge/source TES
```

SOC guard rails are applied before rate limiting:

```text
SOC >= 0.90 and v_target < 0 -> v_target = 0
SOC <= 0.10 and v_target > 0 -> v_target = 0
```

This prevents physically pointless charge/discharge commands near tank
limits, without changing the EnergyPlus TES topology.

## TOU Shaping

M2-F1 adds a training-only TES price-shaping wrapper before observation
normalization.

Target-SOC PBRS:

```text
Phi(s, t) = -kappa * (TES_SOC - SOC_target(t))^2
F_t = gamma * Phi(s_{t+1}, t+1) - Phi(s_t, t)
```

Defaults:

```text
kappa = 1.0
gamma = 0.99
high price target: price_current_norm >= 0.75 -> SOC_target = 0.30
low price near peak target: price_current_norm <= -0.50 and hours_to_peak_norm <= 0.40 -> SOC_target = 0.85
neutral target: SOC_target = 0.50
```

Optional short-term teacher reward:

```text
high price and SOC > 0.20 -> reward positive valve
low price near peak and SOC < 0.85 -> reward negative valve
initial weight = 0.00 by default
linear decay to 0 over 15 annual episodes
```

The teacher term is not strict PBRS and changes the optimization target while
it is active.  M2-F1 therefore defaults to PBRS-only training and keeps the
teacher term only as an explicit curriculum experiment via
`--tes-teacher-weight`.

Valve regularization:

```text
r_valve = -0.02 * valve^2
```

SOC-aware invalid-action shaping (off by default):

```text
if TES_SOC >= tes_soc_charge_limit and v_target_raw < 0:
    r_invalid = -w_invalid * abs(v_target_raw)
elif TES_SOC <= tes_soc_discharge_limit and v_target_raw > 0:
    r_invalid = -w_invalid * abs(v_target_raw)
else:
    r_invalid = 0
```

This is separate from `tes_valve_penalty`.  `tes_valve_penalty` remains only
the quadratic regularizer on the actual rate-limited valve position.  The
invalid-action term penalizes the raw policy intent before the SOC guard clips
physically pointless charge/discharge commands.  The CLI default is
`--tes-invalid-action-penalty-weight 0.0` for compatibility; M2-F1 invalid-
action shaping experiments should pass `0.05`.

The shaping wrapper emits:

- `tes_soc_target`
- `tes_pbrs_term`
- `tes_teacher_term`
- `tes_teacher_weight`
- `tes_valve_penalty`
- `tes_invalid_action_penalty`
- `tes_shaping_total`

The legacy DPBA potential inside `RL_Cost_Reward` is retained for ablations
but is disabled by default in M2-F1 with `--kappa-shape 0.0`.  This avoids
stacking two independent PBRS signals.  Use `--kappa-shape 0.8` only when
explicitly testing the older DPBA design.

## Validation Gates

## Evaluation Protocol Update (2026-05-01)

M2-F1's primary success gate is now trainlike / in-distribution evaluation:

```text
building_file = DRL_DC_training.epJSON
evaluation_flag = 0
ITE_Set = 0.45
obs_dim = 32
action_dim = 4
```

The previous default `DRL_DC_evaluation.epJSON` uses `ITE_Set=1.0`.  That is a
2.22x high-load shift relative to training (`0.45 -> 1.0`), so it is now
reported as `official_ood` stress testing instead of the M2-F1 learning gate.
The observed official failure should be described as workload/load-level OOD,
not as evidence that TES physics or the trainlike TES policy is invalid.

First run: `4 seed x 10ep` from scratch.

Proceed to `4 seed x 30ep` only if deterministic evaluation of the 10ep
models satisfies:

```text
avg_valve_saturation_fraction < 0.80
avg_price_response_high_minus_low > 0.05
avg_soc_daily_amplitude_mean > 0.05
all 4 seeds complete without severe/fatal failures
```

30ep success target:

```text
avg_price_response_high_minus_low > 0.10
at least 2/4 seeds have price_response_high_minus_low > 0.10
avg_soc_daily_amplitude_mean > 0.20
avg_valve_saturation_fraction < 0.80
avg_comfort_violation_pct < 5%
```

## Commands

Compile and smoke:

```powershell
python -m py_compile sinergym\envs\tes_wrapper.py sinergym\utils\logger.py tools\run_m2_training.py tools\evaluate_m2.py tools\smoke_m2_env.py
python tools\smoke_m2_env.py --reward-cls rl_cost --steps 3
python tools\smoke_m2_env.py --reward-cls rl_cost --steps 3 --disable-tes-tou-shaping
```

Training uses CPU, `lr=5e-5`, 4 parallel seeds, and 20 second stagger between
seed launches.
