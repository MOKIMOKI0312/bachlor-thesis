# M2-F1 TES Action Semantics Predesign

Date: 2026-05-02

Scope: design only. This document does not implement training code, does not change EnergyPlus, does not change site/TOU/PV/workload assumptions, and does not change the main training chain.

## Decision Summary

The 672-step evidence says reward and entropy tuning are not solving the TES inventory behavior. The policy reliably discharges during high-price windows, but still often commands positive valve in low-price pre-peak charge windows. The next intervention should change the agent-facing TES action semantics so that "charge / idle / discharge" is represented as a first-class decision instead of being inferred from one continuous signed valve scalar.

Recommended minimum implementation: Scheme A-prime, a continuous direction-plus-amplitude TES semantic wrapper:

- Keep SB3/DSAC-T on a continuous `Box` action space.
- Replace the single TES scalar with two actor outputs: `tes_direction_raw` and `tes_amplitude_raw`.
- Map direction to mode with a deadband: charge, idle, discharge.
- Map amplitude to `[0, 1]`.
- Produce the existing signed TES target: negative = charge, positive = discharge.

This gives most of the action-semantics benefit without requiring native hybrid-action algorithm changes.

## Evidence Summary

The relevant gate is the 672-step `trainlike_soc05` evaluation with P0.2 mechanism metrics. A successful policy should show negative actual valve in low-price pre-peak charge windows, positive SOC lift before peak, positive valve in high-price windows, and SOC drawdown during peak. Across C1/C2/C2b/C3, the high-price discharge side is learned, but the low-price charge side remains weak or inverted.

| Experiment | Key 672-step evidence | Interpretation |
|---|---|---|
| C1 sparse PBRS reward-only | C1 seed1/4 `charge_window_sign_rate=0.068/0.068`, `low_price_discharge_fraction=0.909/0.886`, low-price valve means positive. | Removing neutral PBRS and widening the low-price window did not produce active low-price charging. |
| C2 short teacher | seed1 `charge_window_sign_rate=0.0`, `low_price_discharge_fraction=1.0`; seed4 improved only to `0.235/0.706`; charge-window valve mean remains positive. | Short teacher/curriculum did not persistently alter the low-price action semantics. |
| C2b state augmentation | seed1/4 `charge_window_sign_rate=0.255/0.357`, `low_price_discharge_fraction=0.706/0.562`; charge-window valve mean remains positive. | Extra TES state helps slightly but does not create reliable charge mode selection. |
| C3 entropy ablation | 672-step means: entropy `-4.0` charge sign `0.248`, low discharge `0.711`; entropy `-2.0` charge sign `0.227`, low discharge `0.723`; baseline `-1.333` charge sign `0.306`, low discharge `0.634`. All gate rows fail. | More or less entropy changes exploration but not the underlying mode mistake. |

The shared failure mode is not lack of high-price response. `discharge_window_sign_rate` is generally around `0.85-0.90`, so the agent can command discharge. The failure is directional selection in the low-price pre-peak window: the continuous TES scalar makes "less discharge" an easy local optimum, while true arbitrage requires a categorical sign flip into charge.

Therefore the next hypothesis is action semantics, not reward weighting.

## Goals and Non-Goals

Goals:

- Change only the agent-facing TES action semantics.
- Preserve EnergyPlus physics and existing TES wrapper execution.
- Preserve site, TOU tariff, PV, weather, and workload assumptions.
- Do not add workload action.
- Preserve fixed CRAH fan behavior.
- Keep reward/evaluation gates identical to C2b/C3 when testing the new action semantics.
- Keep old 32D/34D checkpoints clearly incompatible with any changed action dimension.

Non-goals:

- No runtime economic rule controller.
- No hand-coded price if-else that directly forces charge/discharge during deployment.
- No changes to EnergyPlus plant, schedules, or TES physical model.
- No new persistent teacher or alignment reward in final evaluation.

## Scheme A: Discrete Mode Plus Continuous Amplitude

Concept:

- `mode in {charge, idle, discharge}`
- `amp in [0, 1]`
- `tes_target = sign(mode) * amp`
- Sign convention remains fixed:
  - `charge -> negative`
  - `idle -> 0`
  - `discharge -> positive`

Ideal hybrid action:

- HVAC actions remain continuous.
- TES mode is discrete.
- TES amplitude is continuous.
- Full action could be:
  - `[CT_Pump_DRL, CRAH_T_DRL, Chiller_T_DRL, tes_mode, tes_amp]`

Engineering issue:

SB3 continuous actor-critic implementations and the current DSAC-T path are built around continuous `Box` actions. Native hybrid actions, such as `MultiDiscrete + Box`, are not a drop-in change. A true hybrid head would likely require algorithm-level work: separate policy distributions, entropy terms, replay encoding, target critics, and checkpoint/load changes.

Engineering-feasible alternative, Scheme A-prime:

- Keep a continuous `Box` action.
- Replace current TES scalar with two continuous outputs:
  - `tes_direction_raw in [-1, 1]`
  - `tes_amplitude_raw in [-1, 1]`
- Convert direction to mode in a wrapper:
  - `tes_direction_raw < -deadband -> charge`
  - `abs(tes_direction_raw) <= deadband -> idle`
  - `tes_direction_raw > deadband -> discharge`
- Convert amplitude:
  - `amp = clip((tes_amplitude_raw + 1) / 2, 0, 1)`
- Produce target:
  - charge: `tes_target = -amp`
  - idle: `tes_target = 0`
  - discharge: `tes_target = +amp`

Suggested defaults:

- `deadband = 0.20`
- `amp_min_when_active = 0.05` optional, only if near-zero active modes behave like idle
- preserve current actual-valve rate limiting and SOC guard rails downstream

Why this is still not a rule controller:

The actor chooses both direction and amplitude. The wrapper only changes action interpretation. It does not inspect price, SOC target, or TOU phase to choose charge/discharge.

## Scheme B: Hourly Option / Mode Hold

Concept:

- Actor chooses a TES mode that is held for 4 simulation steps.
- Each step is 15 minutes, so the mode persists for 1 hour.
- Mode can change only when `step_index % 4 == 0`.
- Amplitude can either:
  - be held with mode for the same hour, or
  - be refreshed every 15-minute step while mode is held.

Important boundary:

Mode hold must not use runtime price rules. The wrapper should hold the actor's selected mode. It must not override mode based on TOU phase, price, PV, or SOC target.

Relationship to existing `TESTargetValveWrapper` rate limit:

- `TESTargetValveWrapper` smooths actual target-valve movement, currently limiting target changes such as `0.25/step`.
- Hourly option hold operates one level above that. It stabilizes the actor's intended sign/mode.
- Rate limiting still applies below it, preventing abrupt physical valve changes.
- The two mechanisms are complementary:
  - option hold reduces sign chattering;
  - target-valve rate limit controls execution smoothness.

Risk:

If introduced first, mode hold can hide whether the main issue is sign representation or temporal abstraction. It also changes decision frequency, so attribution becomes less clean than Scheme A-prime.

## Minimum Implementation Recommendation

Implement Scheme A-prime first: continuous direction plus amplitude mapping.

Reasons:

- It addresses the observed failure directly: the agent needs a clearer charge/idle/discharge decision.
- It avoids algorithm-level hybrid-action surgery.
- It keeps SB3/DSAC-T actor and replay machinery continuous.
- It is easy to ablate against C2b/C3 because reward, observation, EnergyPlus, and evaluation gates can stay fixed.
- It makes checkpoint incompatibility explicit through `action_dim`.

Suggested minimum action layout:

- Existing C2b action dimension: 4
  - `[CT_Pump_DRL, CRAH_T_DRL, Chiller_T_DRL, TES_DRL]`
- Proposed A-prime action dimension: 5
  - `[CT_Pump_DRL, CRAH_T_DRL, Chiller_T_DRL, TES_direction_DRL, TES_amplitude_DRL]`

The wrapper maps the last two fields into the existing downstream `TES_DRL` target. Downstream wrappers and EnergyPlus still see one signed TES target.

## Interface Sketch

CLI flags:

- `--tes-action-semantics {signed_scalar,direction_amp}`
- default: `signed_scalar`
- `--tes-direction-deadband 0.20`
- optional later: `--tes-active-amp-min 0.0`

Action dimensions:

- `signed_scalar`: current 4D action, compatible with existing checkpoints.
- `direction_amp`: 5D action, incompatible with old 4D checkpoints.

Wrapper order:

1. Base EnergyPlus environment.
2. Reward class swap, if used.
3. Existing observation normalization path.
4. Fixed fan action wrapper.
5. New TES action semantics wrapper:
   - accepts agent action;
   - maps 5D direction/amplitude action into the existing signed TES scalar.
6. Existing TES target valve wrapper and guard rails:
   - rate limit;
   - SOC charge/discharge clipping;
   - actual valve monitor fields.
7. Existing logging/monitor wrapper.

The exact order should follow current local wrapper construction. The key invariant is that the semantic wrapper must run before `TESTargetValveWrapper`, because `TESTargetValveWrapper` should continue receiving one signed TES target.

Checkpoint compatibility:

- Store `tes_action_semantics` in training `status.json`, eval manifest, and monitor metadata.
- Refuse or clearly error when loading a 4D checkpoint into a 5D action env.
- Keep C2b 34D observation normalization separate from any 5D-action checkpoint.

Monitor fields:

- `tes_action_semantics`
- `tes_mode_raw`
- `tes_amp_raw`
- `tes_mode_selected`
- `tes_amp_selected`
- `tes_target_from_semantics`
- existing `tes_valve_target`
- existing `TES_valve_wrapper_position`
- existing P0.2 fields remain unchanged

Evaluation tools to sync:

- `tools/run_m2_training.py`
- `tools/smoke_m2_env.py`
- `tools/evaluate_m2.py`
- `tools/m2_validate_tes_failure_modes.py`
- `tools/evaluate_m2_rule_baseline.py` only if a rule baseline needs to instantiate the new action semantics

Eval command must pass the same `--tes-action-semantics direction_amp` flag used in training. P0.2 summary fields do not need new definitions because they evaluate actual valve and SOC behavior after semantic mapping.

## Test and Experiment Matrix

Short mechanism test:

| ID | Config | Seeds | Episodes | Eval | Gate |
|---|---|---:|---:|---|---|
| C2b baseline | state augmentation, signed scalar TES action, target entropy `-1.3333333333333333` | 1, 4 | 5 | 96 and 672 `trainlike_soc05` | existing baseline |
| A1-min | C2b base + `tes_action_semantics=direction_amp` | 1, 4 | 5 | 96 and 672 `trainlike_soc05` | P0.2 mechanism gate |

Hold everything else fixed:

- reward class `rl_cost`
- neutral PBRS mode `zero`
- low threshold `-0.10`
- near-peak threshold `0.60`
- target SOC high `0.90`
- target SOC low `0.25`
- target SOC kappa `1.0`
- valve penalty `0.001`
- teacher weight `0.10` with decay 2 only if matching C2b/C2 short-teacher base is intended; otherwise use the exact C2b baseline chosen for comparison
- TOU alignment `0.0`
- `--enable-tes-state-augmentation`

Primary gate:

- 96-step must be healthy before 672-step.
- 672-step pass should require:
  - high `charge_window_sign_rate`
  - low `low_price_discharge_fraction`
  - high `discharge_window_sign_rate`
  - positive `delta_soc_prepeak`
  - negative `delta_soc_peak`
  - negative `charge_window_valve_mean`
  - positive `discharge_window_valve_mean`
  - no severe/fatal/traceback/NaN
  - no comfort regression large enough to invalidate the mechanism result

Suggested follow-up only if A1-min partially works:

- A1-deadband ablation: deadband `0.10`, `0.20`, `0.30`.
- O1 mode hold: add 4-step mode hold after A1-min establishes the direction/amplitude representation helps.

## Scientific Boundaries

The action semantic wrapper must not become a rule controller.

Allowed:

- Mapping actor outputs into a structured TES command.
- SOC safety projection or clipping already present in wrappers.
- Rule controller as an evaluation baseline.
- Training-time curriculum if explicitly removable and disabled in final evaluation.

Not allowed for final learned-policy evidence:

- Runtime economic if-else such as "if low price then charge" or "if high price then discharge".
- Persistent teacher/alignment reward presented as the final controller.
- Price-conditioned mode override inside the action wrapper.

The scientific claim should remain: with the same physical plant and tariff, a learned policy can or cannot discover inventory-style TES arbitrage under a particular action representation.

## Risks

- Non-smooth deadband can create learning instability near idle. Mitigation: log raw direction and selected mode; consider soft mode probabilities only if needed.
- 5D action checkpoints are incompatible with 4D checkpoints. Mitigation: explicit status/manifest fields and hard eval checks.
- Direction/amplitude may still learn persistent discharge if reward/credit assignment remains dominant. Mitigation: compare against unchanged C2b baseline and use P0.2 gate, not only cost.
- More action dimensions can slow short 5ep learning. Mitigation: keep C2b state augmentation and use identical seed/eval protocol.
- If amplitude collapses to near zero, sign metrics may look poor even with correct mode. Mitigation: monitor `tes_mode_selected` and `tes_amp_selected` separately.
- Option hold can over-smooth and delay transitions. Mitigation: test only after A1-min, not as first implementation.

## Stop Conditions

Stop A1-min and do not proceed to 10ep if, after 2 seeds x 5ep:

- 672-step `charge_window_sign_rate` remains below C2b baseline mean, or
- `low_price_discharge_fraction` remains above `0.50`, or
- `charge_window_valve_mean` remains positive in both seeds, or
- 96-step or 672-step eval has severe/fatal/traceback/NaN, or
- comfort violations materially regress while mechanism metrics do not improve.

If A1-min improves mode choice but not timing, proceed to Scheme B hourly option/mode hold. If A1-min does not improve mode choice, stop action-semantics tuning and consider a planner/projection route with a clear scientific framing.

## Handoff

Recommended next code task: implement Scheme A-prime behind a default-off feature flag:

`--tes-action-semantics {signed_scalar,direction_amp}`

Do not change defaults. The first implementation should include smoke tests proving:

- default action dimension remains 4;
- `direction_amp` action dimension is 5;
- fixed fan remains active;
- actual TES target sign convention remains negative charge, positive discharge;
- monitor emits raw direction, raw amplitude, selected mode, selected amplitude, and mapped TES target;
- paired eval can load 5D checkpoints only when `--tes-action-semantics direction_amp` is supplied.
