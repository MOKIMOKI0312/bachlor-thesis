# M2 F1 RL-Cost 30ep Failed Evidence - 2026-04-28

## Scope

This note records the failed M2 F1 RL-Cost 30-episode ablation and the
stochastic-vs-deterministic diagnostic. It is evidence for failure analysis
and tuning, not a thesis success result.

Configuration:

- Scenario: M2 without workload action.
- Observation/action interface: 32 observations, 5 actions.
- Reward: RL-Cost.
- Seeds/length: 4 seeds x 30 annual episodes.
- TES shaping: PBRS-only, `tes_teacher_weight=0`.
- Legacy DPBA shaping: `kappa-shape=0`.
- Evaluation: deterministic policy evaluation unless explicitly noted.

## Upstream Gates

The upstream plant/control gates passed before this RL run, so this failure
should be interpreted as a learned-policy/reward-shaping failure, not as
evidence that the plant audit or safe rule baseline was broken.

| Gate | Result | Key numbers |
|---|---|---|
| Audit / plant validation | PASS | E+ 7-day run `returncode=0`, `severe=0`, `fatal=0`, warnings=112; branch integrity passed; TES charge source-side max 192 kW; TES discharge use-side max 1.51 MW with 99% steps >1 kW; EMS objects present: 21 Actuator, 25 Sensor, 5 Program, 3 ProgramCallingManager. |
| Safe TOU rule baseline | PASS | PUE 1.2367; comfort violation 1.732%; SOC daily amplitude mean 0.5438; valve saturation 0.000; charge/discharge fraction 0.143/0.114; price response high-low 0.3286; TES activated=True. |

## Deterministic 30ep Evaluation

Source files:

- `runs/eval_m2/m2f1_rlcost_30ep_seed1/result.json`
- `runs/eval_m2/m2f1_rlcost_30ep_seed2/result.json`
- `runs/eval_m2/m2f1_rlcost_30ep_seed3/result.json`
- `runs/eval_m2/m2f1_rlcost_30ep_seed4/result.json`

| Seed | PUE | Comfort % | Cost USD annual | SOC daily amp | Valve sat | Price response high-low | TES activated |
|---|---:|---:|---:|---:|---:|---:|---|
| seed1 | 1.2109 | 0.0599 | 14,191,839 | 0.0429 | 0.8765 | 0.0452 | false |
| seed2 | 1.2100 | 0.0200 | 14,204,131 | 0.0021 | 0.9463 | -0.0037 | false |
| seed3 | 1.2113 | 0.0200 | 14,199,491 | 0.0006 | 0.9989 | 0.0003 | false |
| seed4 | 1.2159 | 100.0000 | 14,320,142 | 0.7170 | 0.4508 | -0.3710 | true |
| Average | 1.2120 | 25.0250 | 14,228,901 | 0.1906 | 0.8181 | -0.0823 | 1/4 |

30ep gate targets from the M2-F1 plan:

- `avg_price_response_high_minus_low > 0.10`: FAIL, observed -0.0823.
- At least 2/4 seeds with price response > 0.10: FAIL, observed 0/4.
- `avg_soc_daily_amplitude_mean > 0.20`: FAIL, observed 0.1906.
- `avg_valve_saturation_fraction < 0.80`: FAIL, observed 0.8181.
- `avg_comfort_violation_pct < 5%`: FAIL, observed 25.0250 due to seed4 collapse.

Verdict: deterministic 30ep evaluation fails the intended M2-F1 gates. Do not
report this run as a successful RL-Cost result.

## Stochastic-vs-Deterministic Diagnostic

Diagnostic files:

- `analysis/m2_f1_rlcost_30ep_stochastic_diagnostic_20260428.md`
- `analysis/m2_f1_rlcost_30ep_stochastic_diagnostic_20260428.json`

| Seed | Policy | Price response | SOC daily amp | Valve sat | Comfort % |
|---|---|---:|---:|---:|---:|
| seed1 | deterministic | 0.0452 | 0.0429 | 0.8765 | 0.0599 |
| seed1 | stochastic | 0.0459 | 0.0537 | 0.8757 | 0.0742 |
| seed3 | deterministic | 0.0003 | 0.0006 | 0.9989 | 0.0200 |
| seed3 | stochastic | 0.0003 | 0.0006 | 0.9989 | 0.0200 |
| seed4 | deterministic | -0.3710 | 0.7170 | 0.4508 | 100.0000 |
| seed4 | stochastic | -0.4001 | 0.7250 | 0.4444 | 100.0000 |

Conclusion: stochastic evaluation does not rescue the run. Seed1 and seed3
remain effectively the same saturated policies, and seed4 remains a 100%
comfort-violation policy. The failure is therefore not a deterministic-only
evaluation artifact. The learned distributions are already concentrated around
the same unsafe or non-arbitrage actions.

Do not change reported evaluation to stochastic as a workaround. It would add
variance without changing the pass/fail conclusion.

## Failure Mode

- seed1: TES valve is negatively saturated most of the year
  (`valve_saturation_fraction=0.8765`, `charge_fraction=0.9678`), while SOC
  daily amplitude stays small (`0.0429`). This is mostly persistent charging,
  not useful arbitrage.
- seed2: same broad pattern as seed1, with even weaker SOC movement
  (`SOC amp=0.0021`) and negative price response (`-0.0037`).
- seed3: strongest negative saturation (`valve_saturation_fraction=0.9989`,
  `charge_fraction=0.9999`) and essentially frozen SOC (`SOC amp=0.0006`).
- seed4: the valve moves, but the learned direction is opposite to the desired
  TOU arbitrage (`price_response=-0.3710`) and the HVAC/action policy collapses
  comfort (`comfort_violation_pct=100%`, mean temperature 44.49 C).

Overall pattern: seeds 1-3 fail by negative TES saturation with little useful
SOC motion; seed4 fails by unsafe direction/comfort collapse. This is not a
stable success hidden behind one unlucky seed.

## Next Steps

- Run short teacher experiments instead of continuing the same PBRS-only
  30ep configuration.
- Test stronger valve saturation penalty and/or explicit valve behavior
  regularization.
- Test beta/comfort-safety handling before optimizing arbitrage metrics.
- Keep deterministic validation gates for model selection.
- Do not spend more compute on the unchanged same-config 30ep setup.
- Do not switch the evaluation protocol to stochastic to mask the failure.

This round should be cited only as failed ablation/tuning evidence.
